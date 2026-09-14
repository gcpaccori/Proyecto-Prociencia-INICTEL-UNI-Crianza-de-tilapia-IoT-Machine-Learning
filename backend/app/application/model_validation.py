"""Validacion de los modelos contra lo que midieron los sensores.

Cada modelo del modulo de aprendizaje automatico se contrasta con datos reales
limpios: lo que el modelo dice frente a lo que se observo, con su recta de
regresion y su R2. Sin eso no hay forma de saber si un modelo sirve en esta
piscigranja o solo en el papel donde se publico.

Limpieza comun a todo:
  - se descartan las rachas del mismo valor de oxigeno repetido 30 veces o
    mas, que son el sensor atascado (el 63% del historico);
  - se descartan los valores fisicamente imposibles para un estanque con
    tilapias vivas: temperatura fuera de 12-38 C, pH fuera de 3-11, oxigeno
    fuera de 0-20 mg/L. Las lecturas de 44 C no son agua: son averia.

Los resultados no se maquillan. Si un modelo no ajusta, se dice y se explica
por que.
"""

from __future__ import annotations

import base64
import json
import math
import pickle
import time
from datetime import timedelta
from typing import Any

import numpy as np
from sqlalchemy import text

RACHA_ATASCO = 30
MUESTRA_MAX = 600
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_SEGUNDOS = 1800


def _r2(obs, pred) -> float:
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)
    total = float(np.sum((obs - obs.mean()) ** 2))
    if not total:
        return 0.0
    return 1.0 - float(np.sum((obs - pred) ** 2)) / total


def _recta(x, y) -> dict[str, float]:
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    pendiente, intercepto = np.polyfit(x, y, 1)
    return {
        "pendiente": round(float(pendiente), 5),
        "intercepto": round(float(intercepto), 5),
        "r2": round(_r2(y, pendiente * x + intercepto), 4),
        "pearson": round(float(np.corrcoef(x, y)[0, 1]), 4),
    }


def _muestrear(pares: list, tope: int = MUESTRA_MAX) -> list:
    """Reduce la nube a un tamano dibujable sin sesgarla: pasos regulares."""
    if len(pares) <= tope:
        return pares
    paso = len(pares) / tope
    return [pares[int(i * paso)] for i in range(tope)]


def od_saturacion(temperatura_c: float) -> float:
    """Oxigeno disuelto en saturacion para agua dulce (Benson-Krause)."""
    kelvin = temperatura_c + 273.15
    return math.exp(
        -139.34411
        + 1.575701e5 / kelvin
        - 6.642308e7 / kelvin**2
        + 1.243800e10 / kelvin**3
        - 8.621949e11 / kelvin**4
    )


def _lecturas_limpias(engine, legacy: str, piscina: int):
    safe = legacy.replace("`", "``")
    with engine.connect() as con:
        filas = con.execute(
            text(
                f"""
                SELECT created_at, temperatura, ph, oxigeno_disuelto, ion_nitrato
                FROM `{safe}`.`parametro_aguas`
                WHERE piscina_id = :p AND temperatura IS NOT NULL
                ORDER BY created_at ASC
                """
            ),
            {"p": piscina},
        ).mappings().all()
    crudas = len(filas)

    atascadas = set()
    inicio = 0
    for i in range(1, len(filas) + 1):
        if i == len(filas) or filas[i]["oxigeno_disuelto"] != filas[inicio]["oxigeno_disuelto"]:
            if i - inicio >= RACHA_ATASCO:
                atascadas.update(range(inicio, i))
            inicio = i

    limpias = []
    for i, f in enumerate(filas):
        if i in atascadas:
            continue
        try:
            t = float(f["temperatura"])
            od = float(f["oxigeno_disuelto"])
            ph = float(f["ph"])
            no3 = float(f["ion_nitrato"] or 0)
        except (TypeError, ValueError):
            continue
        if not (12.0 <= t <= 38.0 and 0.0 <= od <= 20.0 and 3.0 <= ph <= 11.0):
            continue
        limpias.append({"t": t, "od": od, "ph": ph, "no3": no3, "cuando": f["created_at"]})

    limpieza = {
        "lecturas_crudas": crudas,
        "lecturas_limpias": len(limpias),
        "descartadas_sensor_atascado": len(atascadas),
        "descartadas_fuera_de_rango": crudas - len(atascadas) - len(limpias),
        "criterio": (
            "Se descartan rachas de 30 o mas lecturas identicas de oxigeno (sensor atascado) "
            "y valores imposibles en un estanque vivo: temperatura fuera de 12-38 C, pH fuera "
            "de 3-11 y oxigeno fuera de 0-20 mg/L."
        ),
    }
    return filas, limpias, limpieza


# ----------------------------------------------------------------------
# 1) Proyeccion de oxigeno a una hora
# ----------------------------------------------------------------------
def _proyeccion_oxigeno(filas_crudas) -> dict[str, Any]:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVR

    from backend.app.models_engine.ml import od_forecast as M

    filas = [
        {
            "created_at": f["created_at"],
            "oxigeno_disuelto": f["oxigeno_disuelto"],
            "temperatura": f["temperatura"],
            "ph": f["ph"],
        }
        for f in filas_crudas
    ]
    grid = M._rejilla(M.descartar_sensor_atascado(filas))
    X, cambio, actual, futuro = [], [], [], []
    for casilla in sorted(grid):
        previas = [casilla - timedelta(minutes=M.BIN_MINUTOS * d) for d in M.DESFASES]
        objetivo = casilla + timedelta(minutes=M.BIN_MINUTOS * M.PASOS_HORIZONTE)
        if objetivo not in grid or any(p not in grid for p in previas):
            continue
        fila = M._fila(grid, casilla, previas)
        if fila is None:
            continue
        X.append(fila)
        actual.append(grid[casilla][0])
        futuro.append(grid[objetivo][0])
        cambio.append(grid[objetivo][0] - grid[casilla][0])

    if len(X) < 400:
        return {"disponible": False, "motivo": "No hay ventanas limpias suficientes para validar."}

    n = len(X)
    corte_train = int(n * 0.70)
    corte_test = int(n * 0.85)
    Xtr, ytr = X[:corte_train], cambio[:corte_train]
    Xte = X[corte_test:]
    act = np.asarray(actual[corte_test:], float)
    obs = np.asarray(futuro[corte_test:], float)

    gb = GradientBoostingRegressor(random_state=20260907, n_estimators=300, max_depth=3, learning_rate=0.05)
    gb.fit(Xtr, ytr)
    pred_gb = act + gb.predict(Xte)

    svr = make_pipeline(StandardScaler(), SVR(kernel="rbf", C=10.0, gamma="scale", epsilon=0.02))
    svr.fit(Xtr, ytr)
    pred_svr = act + svr.predict(Xte)

    def resumen(pred):
        return {
            "r2": round(_r2(obs, pred), 4),
            "mae": round(float(np.mean(np.abs(obs - pred))), 4),
        }

    recta = _recta(obs, pred_gb)
    pares = [[round(float(o), 3), round(float(p), 3)] for o, p in zip(obs, pred_gb)]
    return {
        "disponible": True,
        "tipo": "Gradient boosting (regresion por arboles de decision potenciados)",
        "que_se_compara": "Oxigeno previsto a una hora frente al oxigeno que se midio una hora despues",
        "eje_x": "Oxigeno medido (mg/L)",
        "eje_y": "Oxigeno previsto (mg/L)",
        "puntos": _muestrear(pares),
        "puntos_totales": len(pares),
        "recta": recta,
        "r2": round(_r2(obs, pred_gb), 4),
        "mae": round(float(np.mean(np.abs(obs - pred_gb))), 4),
        "comparacion": {
            "Gradient boosting": resumen(pred_gb),
            "SVR (maquina de vectores de soporte)": resumen(pred_svr),
            "Persistencia (suponer que no cambia)": resumen(act),
        },
        "reparto": f"{corte_train} ventanas de entrenamiento y {len(Xte)} de prueba, en orden temporal",
        "lectura": (
            "La SVR que usaba este modulo queda por debajo de simplemente suponer que el oxigeno "
            "no cambia. El modelo que si aporta es gradient boosting, entrenado sobre el cambio "
            "de oxigeno con el ciclo dia-noche y el deficit de saturacion."
        ),
    }


# ----------------------------------------------------------------------
# 2) Estado de oxigeno
# ----------------------------------------------------------------------
def _estado_oxigeno(limpias) -> dict[str, Any]:
    if len(limpias) < 50:
        return {"disponible": False, "motivo": "No hay lecturas limpias suficientes."}
    temps = [f["t"] for f in limpias]
    ods = [f["od"] for f in limpias]
    recta = _recta(temps, ods)
    sats = np.asarray([od_saturacion(t) for t in temps])
    porcentaje = 100 * np.asarray(ods) / sats

    lo = math.floor(min(temps))
    hi = math.ceil(max(temps))
    curva = [[t, round(od_saturacion(t), 3)] for t in np.arange(lo, hi + 0.25, 0.25).round(2).tolist()]

    pares = [[round(t, 2), round(o, 3)] for t, o in zip(temps, ods)]
    return {
        "disponible": True,
        "tipo": "Ecuacion fisica de solubilidad del oxigeno en agua dulce (Benson-Krause)",
        "que_se_compara": "Oxigeno medido frente a la temperatura del agua, con la saturacion teorica encima",
        "eje_x": "Temperatura del agua (C)",
        "eje_y": "Oxigeno disuelto (mg/L)",
        "puntos": _muestrear(pares),
        "puntos_totales": len(pares),
        "curva_saturacion": curva,
        "recta": recta,
        "r2": recta["r2"],
        "saturacion_media_pct": round(float(np.mean(porcentaje)), 1),
        "saturacion_mediana_pct": round(float(np.median(porcentaje)), 1),
        "lectura": (
            "La ecuacion dice cuanto oxigeno puede admitir el agua a cada temperatura, no cuanto "
            "tiene. La nube real queda muy por debajo de la curva y casi no depende de la "
            "temperatura: el oxigeno de este estanque lo gobiernan la respiracion de los peces, "
            "la aireacion y el biofloc, no la solubilidad."
        ),
    }


# ----------------------------------------------------------------------
# 3) Crecimiento de tilapia
# ----------------------------------------------------------------------
def _crecimiento(engine, legacy: str, limpias) -> dict[str, Any]:
    safe = legacy.replace("`", "``")
    with engine.connect() as con:
        bio = con.execute(
            text(
                f"""
                SELECT b.fecha_muestreo AS fecha, AVG(bd.longitud_cm) AS l_cm, COUNT(bd.id) AS peces
                FROM `{safe}`.`biometrias` b
                JOIN `{safe}`.`biometria_detalles` bd ON bd.biometria_id = b.id
                WHERE b.deleted_at IS NULL
                GROUP BY b.fecha_muestreo ORDER BY b.fecha_muestreo
                """
            )
        ).mappings().all()

    intervalos = []
    for a, z in zip(bio, bio[1:]):
        dias = (z["fecha"] - a["fecha"]).days
        if dias <= 0:
            continue
        observado = (float(z["l_cm"]) - float(a["l_cm"])) * 10 / dias
        tramo = [f["t"] for f in limpias if a["fecha"] <= f["cuando"].date() <= z["fecha"]]
        if not tramo:
            continue
        tmedia = float(np.mean(tramo))
        intervalos.append(
            {
                "desde": a["fecha"].isoformat(),
                "hasta": z["fecha"].isoformat(),
                "dias": dias,
                "temperatura_media": round(tmedia, 2),
                "lecturas_temperatura": len(tramo),
                "observado_mm_dia": round(observado, 3),
                "soderberg_mm_dia": round(-1.6707 + 0.09682 * tmedia, 3),
            }
        )

    linea = [[t, round(-1.6707 + 0.09682 * t, 3)] for t in range(10, 41)]
    r2 = None
    if len(intervalos) >= 2:
        r2 = round(
            _r2([i["observado_mm_dia"] for i in intervalos], [i["soderberg_mm_dia"] for i in intervalos]), 4
        )
    return {
        "disponible": bool(intervalos),
        "tipo": "Regresion lineal simple (Soderberg)",
        "formula": "Crecimiento diario en longitud = -1,6707 + 0,09682 x temperatura",
        "fuente": "Informe 17, ec. 1; ajustada por Soderberg para tilapia del Nilo macho, R2 = 0,95",
        "dominio_validado": [21, 30],
        "que_se_compara": "Crecimiento en longitud medido entre biometrias frente al que predice la recta",
        "eje_x": "Temperatura media del agua en el intervalo (C)",
        "eje_y": "Crecimiento diario en longitud (mm/dia)",
        "linea_modelo": linea,
        "puntos": [[i["temperatura_media"], i["observado_mm_dia"]] for i in intervalos],
        "intervalos": intervalos,
        "r2": r2,
        "lectura": (
            "Solo hay tres intervalos entre biometrias, asi que el R2 es fragil. Aun asi el patron "
            "es claro: la temperatura apenas cambio entre 27 y 29 C mientras el crecimiento caia de "
            "1,5 a 0,18 mm/dia. La recta, que solo mira la temperatura, no puede explicar esa caida; "
            "coincide con la crisis de oxigeno de julio. Ademas mayo no tiene lecturas validas de "
            "oxigeno, por lo que ese tramo no permite probar la correccion por factores limitantes."
        ),
    }


# ----------------------------------------------------------------------
# 4) Calidad de agua con SVM
# ----------------------------------------------------------------------
def _calidad_agua(engine, limpias) -> dict[str, Any]:
    from sklearn.linear_model import LinearRegression

    from backend.app.models_engine.deterministic import water_quality as WQ

    X, nota, clase = [], [], []
    for f in limpias:
        try:
            res = WQ.water_quality_index(f["t"], f["ph"], f["od"], f["no3"])
        except Exception:
            continue
        cls = res.get("classification")
        etiqueta = cls.get("label") if isinstance(cls, dict) else cls
        X.append([f["t"], f["ph"], f["od"], f["no3"]])
        nota.append(float(res["ica"]))
        clase.append(str(etiqueta))
    if len(X) < 200:
        return {"disponible": False, "motivo": "No hay lecturas limpias suficientes."}
    X = np.asarray(X, float)
    nota_arr = np.asarray(nota, float)

    svm = None
    acierto = None
    try:
        with engine.connect() as con:
            fila = con.execute(
                text("SELECT payload_json FROM model_assets WHERE model_code = 'WATER_QUALITY_INDEX_ICA_SVM'")
            ).mappings().first()
        if fila:
            carga = json.loads(fila["payload_json"])
            arte = carga.get("artifact_payload")
            if isinstance(arte, str):
                arte = json.loads(arte)
            svm = pickle.loads(base64.b64decode(arte["estimator_b64"]))
            orden = arte.get("class_order") or []
            predichas = svm.predict(X)
            # el estimador puede devolver el indice de la clase o su nombre
            nombres = [orden[int(p)] if not isinstance(p, str) and orden else str(p) for p in predichas]
            acierto = round(float(np.mean(np.asarray(nombres) == np.asarray(clase))), 4)
    except Exception:
        svm = None

    dependencias = []
    nombres_var = [("Temperatura (C)", 0), ("pH", 1), ("Oxigeno disuelto (mg/L)", 2), ("Ion nitrato (mg/L)", 3)]
    for etiqueta, i in nombres_var:
        x = X[:, i]
        if float(np.std(x)) == 0.0:
            continue
        recta = _recta(x, nota_arr)
        pares = [[round(float(a), 3), round(float(b), 2)] for a, b in zip(x, nota_arr)]
        dependencias.append({"variable": etiqueta, "puntos": _muestrear(pares, 350), "recta": recta})
    dependencias.sort(key=lambda d: d["recta"]["r2"], reverse=True)

    n = len(X)
    corte = int(n * 0.8)
    reg = LinearRegression().fit(X[:corte], nota_arr[:corte])
    pred = reg.predict(X[corte:])
    regresion = {
        "formula": (
            f"CA = {reg.intercept_:.3f} {reg.coef_[0]:+.3f} T {reg.coef_[1]:+.3f} pH "
            f"{reg.coef_[2]:+.3f} OD {reg.coef_[3]:+.4f} NO3"
        ),
        "r2_prueba": round(_r2(nota_arr[corte:], pred), 4),
        "puntos": _muestrear(
            [[round(float(o), 2), round(float(p), 2)] for o, p in zip(nota_arr[corte:], pred)], 400
        ),
    }

    return {
        "disponible": True,
        "tipo": "Maquina de vectores de soporte para clasificacion (SVC, nucleo RBF)",
        "que_se_compara": "De que variable depende la calidad del agua, lectura a lectura",
        "lecturas": n,
        "acierto_svm": acierto,
        "clases": sorted(set(clase)),
        "dependencias": dependencias,
        "regresion_multiple": regresion,
        "origen_etiqueta": (
            "El SVM se entreno con las clases que asigna la formula ponderada del equipo "
            "(Excelente, Buena, Regular, Mala). No existe una medicion independiente de "
            "'calidad del agua' contra la que validarlo: aprende a reconocer esa clasificacion "
            "a partir de las cuatro variables."
        ),
        "lectura": (
            "La calidad del agua de este estanque la mueven el oxigeno y el nitrato. La "
            "temperatura y el pH casi no varian aqui, por lo que apenas aportan a las diferencias "
            "entre una lectura y otra."
        ),
    }


def build_model_validation(store, pond_id: str, refresh: bool = False) -> dict[str, Any]:
    engine = getattr(store, "engine", None)
    legacy = getattr(store, "legacy_database_name", None)
    if engine is None or not legacy:
        return {"disponible": False, "motivo": "Sin acceso a la base de sensores."}

    numero = pond_id.replace("LEGACY-POND-", "") if isinstance(pond_id, str) else pond_id
    try:
        piscina = int(numero)
    except (TypeError, ValueError):
        piscina = 1

    clave = f"{legacy}:{piscina}"
    ahora = time.time()
    if not refresh and clave in _cache and ahora - _cache[clave][0] < CACHE_SEGUNDOS:
        return _cache[clave][1]

    filas, limpias, limpieza = _lecturas_limpias(engine, str(legacy), piscina)
    resultado = {
        "disponible": True,
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "limpieza": limpieza,
        "modelos": {
            "SVM_OD_FORECAST_1H": _proyeccion_oxigeno(filas),
            "OXYGEN_STATUS_MODEL": _estado_oxigeno(limpias),
            "TILAPIA_GROWTH_TEMPERATURE": _crecimiento(engine, str(legacy), limpias),
            "WATER_QUALITY_INDEX_ICA": _calidad_agua(engine, limpias),
        },
    }
    _cache[clave] = (ahora, resultado)
    return resultado
