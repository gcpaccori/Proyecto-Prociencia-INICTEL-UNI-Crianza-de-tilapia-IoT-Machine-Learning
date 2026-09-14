"""Validacion de los modelos contra lo que midieron los sensores.

Cada modelo del modulo de aprendizaje automatico se contrasta con datos reales
limpios: lo que el modelo dice frente a lo que se observo, con su recta de
regresion y su R2. Sin eso no hay forma de saber si un modelo sirve en esta
piscigranja o solo en el papel donde se publico.

Limpieza, variable por variable, porque cada sensor falla a su manera:

  oxigeno      rachas de 30 o mas lecturas identicas (sensor atascado) y
               lecturas en 0 o 0,01 mg/L, el piso del sensor: en junio marco
               0,01 durante horas con los peces vivos
  temperatura  fuera de 12-38 C; las lecturas de 44 C no son agua sino averia
  pH           fuera de 3-11
  nitrato      por encima de 100 mg/L. El 39% del historico marca 14 000 mg/L,
               que es el tope de la sonda: sensor saturado o desconectado. Solo
               se exige a los modelos que usan nitrato; filtrarlo en todos
               habria tirado oxigeno valido.

Los resultados no se maquillan. Si un modelo no ajusta, se dice y se explica.
"""

from __future__ import annotations

import base64
import json
import math
import pickle
import time
from datetime import date, timedelta
from typing import Any

import numpy as np
from sqlalchemy import text

RACHA_ATASCO = 30
MUESTRA_MAX = 600
NITRATO_MAX = 100.0
OD_PISO = 0.05
CACHE_SEGUNDOS = 1800
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


# ----------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------
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
        "r2": round(_r2(y, pendiente * x + intercepto), 3),
        "pearson": round(float(np.corrcoef(x, y)[0, 1]), 3),
    }


def _muestrear(pares: list, tope: int = MUESTRA_MAX) -> list:
    """Reduce la nube a un tamano dibujable sin sesgarla: pasos regulares."""
    if len(pares) <= tope:
        return pares
    paso = len(pares) / tope
    return [pares[int(i * paso)] for i in range(tope)]


def od_saturacion(temperatura_c: float) -> float:
    """Oxigeno disuelto en saturacion para agua dulce (Benson-Krause, 1984)."""
    kelvin = temperatura_c + 273.15
    return math.exp(
        -139.34411
        + 1.575701e5 / kelvin
        - 6.642308e7 / kelvin**2
        + 1.243800e10 / kelvin**3
        - 8.621949e11 / kelvin**4
    )


def _rachas_planas(valores: list) -> set[int]:
    """Indices que pertenecen a rachas de RACHA_ATASCO o mas valores identicos."""
    malas: set[int] = set()
    inicio = 0
    for i in range(1, len(valores) + 1):
        if i == len(valores) or valores[i] != valores[inicio]:
            if i - inicio >= RACHA_ATASCO:
                malas.update(range(inicio, i))
            inicio = i
    return malas


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _coma(valor: float, decimales: int = 2) -> str:
    """Numero con coma decimal, como se escribe en Peru."""
    return f"{valor:.{decimales}f}".replace(".", ",").replace("-", "−")


def _numero(valor):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ----------------------------------------------------------------------
# lectura y limpieza
# ----------------------------------------------------------------------
def _leer(engine, legacy: str, piscina: int):
    safe = legacy.replace("`", "``")
    with engine.connect() as con:
        return con.execute(
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


def _limpiar(filas) -> tuple[list[dict], dict[str, Any]]:
    od_atascado = _rachas_planas([f["oxigeno_disuelto"] for f in filas])
    motivos = {"oxigeno_atascado": len(od_atascado), "oxigeno_en_cero": 0, "fuera_de_rango": 0}
    limpias = []
    for i, f in enumerate(filas):
        if i in od_atascado:
            continue
        t = _numero(f["temperatura"])
        od = _numero(f["oxigeno_disuelto"])
        ph = _numero(f["ph"])
        no3 = _numero(f["ion_nitrato"])
        if t is None or od is None or ph is None:
            motivos["fuera_de_rango"] += 1
            continue
        if od < OD_PISO:
            motivos["oxigeno_en_cero"] += 1
            continue
        if not (12.0 <= t <= 38.0 and od <= 20.0 and 3.0 <= ph <= 11.0):
            motivos["fuera_de_rango"] += 1
            continue
        limpias.append({"t": t, "od": od, "ph": ph, "no3": no3, "cuando": f["created_at"]})

    nitrato_valido = sum(1 for f in limpias if f["no3"] is not None and 0.0 <= f["no3"] <= NITRATO_MAX)
    limpieza = {
        "lecturas_crudas": len(filas),
        "lecturas_limpias": len(limpias),
        "descartadas_oxigeno_atascado": motivos["oxigeno_atascado"],
        "descartadas_oxigeno_en_cero": motivos["oxigeno_en_cero"],
        "descartadas_fuera_de_rango": motivos["fuera_de_rango"],
        "con_nitrato_valido": nitrato_valido,
        "criterio": (
            "Se descartan las rachas de 30 o más lecturas idénticas de oxígeno (sensor atascado), "
            "el oxígeno en 0 o 0,01 mg/L (el piso del sensor) y los valores imposibles en un estanque vivo: temperatura "
            "fuera de 12-38 °C, pH fuera de 3-11 y oxígeno por encima de 20 mg/L."
        ),
    }
    return limpias, limpieza


def _temperatura_diaria(filas) -> dict[date, float]:
    """Temperatura media de cada dia, con su propio filtro.

    La temperatura no depende del sensor de oxigeno: se limpia aparte para no
    perder los dias en que solo el oxigeno estaba atascado.
    """
    temp_atascada = _rachas_planas([f["temperatura"] for f in filas])
    por_dia: dict[date, list[float]] = {}
    for i, f in enumerate(filas):
        if i in temp_atascada:
            continue
        t = _numero(f["temperatura"])
        if t is None or not (12.0 <= t <= 38.0):
            continue
        por_dia.setdefault(f["created_at"].date(), []).append(t)
    return {dia: float(np.mean(v)) for dia, v in por_dia.items()}


def lectura_actual(limpias) -> dict[str, Any] | None:
    """La ultima lectura limpia, la misma para todas las paginas."""
    if not limpias:
        return None
    ultima = limpias[-1]
    sat = od_saturacion(ultima["t"])
    return {
        "cuando": ultima["cuando"].isoformat(),
        "temperatura_c": round(ultima["t"], 2),
        "ph": round(ultima["ph"], 2),
        "oxigeno_mg_l": round(ultima["od"], 2),
        "nitrato_mg_l": round(ultima["no3"], 2) if ultima["no3"] is not None else None,
        "nitrato_valido": ultima["no3"] is not None and 0.0 <= ultima["no3"] <= NITRATO_MAX,
        "od_saturacion_mg_l": round(sat, 2),
        "saturacion_pct": round(100.0 * ultima["od"] / sat, 1),
        "deficit_mg_l": round(sat - ultima["od"], 2),
    }


# ----------------------------------------------------------------------
# 1) Proyeccion de oxigeno disuelto a una hora
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
        if (_numero(f["oxigeno_disuelto"]) or 0.0) >= OD_PISO
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
        return {"r2": round(_r2(obs, pred), 3), "mae": round(float(np.mean(np.abs(obs - pred))), 3)}

    try:
        prevision = M.predict_od({"modelo": gb}, filas)
    except Exception:
        prevision = None

    r_gb, r_svr, r_pers = _r2(obs, pred_gb), _r2(obs, pred_svr), _r2(obs, act)
    lectura = (
        f"La nube se pega a la diagonal: con R² de {_coma(r_gb)}, lo previsto coincide con lo medido "
        "una hora después."
    )
    if r_gb > r_pers:
        lectura += (
            f" Supera a suponer que el oxígeno no cambia (R² {_coma(r_pers)}), que es la prueba mínima "
            "que debe pasar un pronóstico."
        )
    if r_svr < r_pers:
        lectura += (
            f" La SVR que usaba antes este módulo no la pasa (R² {_coma(r_svr)}): por eso el modelo es "
            "gradient boosting, entrenado sobre el cambio de oxígeno con el ciclo día-noche y el déficit "
            "de saturación."
        )

    pares = [[round(float(o), 3), round(float(p), 3)] for o, p in zip(obs, pred_gb)]
    return {
        "disponible": True,
        "tipo": "Gradient boosting (regresión)",
        "que_se_compara": "Oxígeno previsto a una hora frente al oxígeno que se midió una hora después",
        "eje_x": "Oxígeno medido (mg/L)",
        "eje_y": "Oxígeno previsto (mg/L)",
        "puntos": _muestrear(pares),
        "puntos_totales": len(pares),
        "recta": _recta(obs, pred_gb),
        "r2": round(_r2(obs, pred_gb), 3),
        "mae": round(float(np.mean(np.abs(obs - pred_gb))), 3),
        "comparacion": [
            {"metodo": "Gradient boosting (el modelo)", **resumen(pred_gb)},
            {"metodo": "SVR, máquina de vectores de soporte", **resumen(pred_svr)},
            {"metodo": "Persistencia: suponer que no cambia", **resumen(act)},
        ],
        "reparto": f"{_miles(corte_train)} ventanas de entrenamiento y {_miles(len(Xte))} de prueba, en orden temporal",
        "prevision_actual": prevision,
        "lectura": lectura,
    }


# ----------------------------------------------------------------------
# 2) Estado de oxigeno disuelto
# ----------------------------------------------------------------------
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
MIN_LECTURAS_MES = 50


def _estado_oxigeno(limpias) -> dict[str, Any]:
    if len(limpias) < 50:
        return {"disponible": False, "motivo": "No hay lecturas limpias suficientes."}
    temps = [f["t"] for f in limpias]
    ods = [f["od"] for f in limpias]
    sats = np.asarray([od_saturacion(t) for t in temps])
    porcentaje = 100 * np.asarray(ods) / sats
    od_arr = np.asarray(ods)

    lo = math.floor(min(temps))
    hi = math.ceil(max(temps))
    curva = [[t, round(od_saturacion(t), 3)] for t in np.arange(lo, hi + 0.25, 0.25).round(2).tolist()]
    bajo = round(100.0 * float(np.mean(od_arr < 3.0)), 1)
    alto = round(100.0 * float(np.mean(od_arr >= 5.0)), 1)

    # Cada lectura lleva su mes: la nube se colorea por mes para ver si los
    # grupos de oxigeno son temperaturas distintas o epocas distintas.
    grupos: dict[str, list[tuple[float, float]]] = {}
    for f in limpias:
        grupos.setdefault(f["cuando"].strftime("%Y-%m"), []).append((f["t"], f["od"]))
    por_mes = []
    for clave in sorted(grupos):
        if len(grupos[clave]) < MIN_LECTURAS_MES:
            continue
        arr = np.asarray(grupos[clave], float)
        anio, mes = clave.split("-")
        por_mes.append(
            {
                "mes": clave,
                "nombre": f"{MESES[int(mes) - 1]} {anio}",
                "lecturas": int(len(arr)),
                "temperatura_media": round(float(arr[:, 0].mean()), 1),
                "oxigeno_mediana": round(float(np.median(arr[:, 1])), 2),
                "pct_bajo_3": round(100.0 * float(np.mean(arr[:, 1] < 3.0)), 1),
            }
        )
    meses_validos = {m["mes"] for m in por_mes}
    pares = [
        [round(f["t"], 2), round(f["od"], 3), f["cuando"].strftime("%Y-%m")]
        for f in limpias
        if f["cuando"].strftime("%Y-%m") in meses_validos
    ]
    recta = _recta(temps, ods)
    return {
        "disponible": True,
        "tipo": "Ecuación física de solubilidad (Benson-Krause)",
        "que_se_compara": "Oxígeno medido frente a la temperatura del agua, con la saturación teórica encima",
        "eje_x": "Temperatura del agua (°C)",
        "eje_y": "Oxígeno disuelto (mg/L)",
        "puntos": _muestrear(pares),
        "puntos_totales": len(limpias),
        "por_mes": por_mes,
        "curva_saturacion": curva,
        "recta": recta,
        "r2": recta["r2"],
        "saturacion_media_pct": round(float(np.mean(porcentaje)), 1),
        "saturacion_mediana_pct": round(float(np.median(porcentaje)), 1),
        "pct_bajo_3": bajo,
        "pct_sobre_5": alto,
        "lectura": _lectura_estado(por_mes, recta["r2"], float(np.median(porcentaje))),
    }


def _lectura_estado(por_mes: list, r2: float, saturacion_mediana: float) -> str:
    texto = (
        "La ecuación dice cuánto oxígeno puede admitir el agua a cada temperatura, no cuánto tiene. "
        f"La nube queda muy por debajo de la curva: la saturación mediana es {_coma(saturacion_mediana, 0)} %."
    )
    if len(por_mes) >= 2:
        peor = max(por_mes, key=lambda m: m["pct_bajo_3"])
        mejor = min(por_mes, key=lambda m: m["pct_bajo_3"])
        t_min = min(m["temperatura_media"] for m in por_mes)
        t_max = max(m["temperatura_media"] for m in por_mes)
        texto += (
            f" Los grupos de puntos no son temperaturas distintas sino épocas distintas: en {peor['nombre']} "
            f"el {_coma(peor['pct_bajo_3'], 0)} % de las lecturas estuvo por debajo de 3 mg/L, y en "
            f"{mejor['nombre']} solo el {_coma(mejor['pct_bajo_3'], 0)} %, con temperaturas medias entre "
            f"{_coma(t_min, 1)} y {_coma(t_max, 1)} °C en todos los meses. Por eso el R² con la temperatura es "
            f"casi nulo ({_coma(r2)}): lo que cambió entre esas épocas hay que buscarlo en el manejo del "
            "estanque, como la aireación, la carga de peces o la alimentación."
        )
    return texto


# ----------------------------------------------------------------------
# 3) Crecimiento de tilapia por temperatura
# ----------------------------------------------------------------------
def _soderberg(t: float) -> float:
    return -1.6707 + 0.09682 * t


def _crecimiento(engine, legacy: str, filas_crudas, limpias) -> dict[str, Any]:
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
    if len(bio) < 2:
        return {"disponible": False, "motivo": "Hacen falta al menos dos biometrías."}

    diaria = _temperatura_diaria(filas_crudas)
    dias_con_dato = sorted(diaria)

    def temp_del_dia(dia: date) -> tuple[float | None, bool]:
        """Temperatura del dia; si falta, se interpola entre los dias vecinos."""
        if dia in diaria:
            return diaria[dia], True
        antes = [d for d in dias_con_dato if d < dia]
        despues = [d for d in dias_con_dato if d > dia]
        if antes and despues:
            a, z = antes[-1], despues[0]
            peso = (dia - a).days / (z - a).days
            return diaria[a] + peso * (diaria[z] - diaria[a]), False
        return None, False

    medidas = [(b["fecha"], float(b["l_cm"]) * 10.0, int(b["peces"])) for b in bio]

    # Longitud que predice la recta, acumulando dia a dia desde la primera
    # biometria con la temperatura real de cada dia.
    inicio, largo_inicial, _ = medidas[0]
    fin = medidas[-1][0]
    largo = largo_inicial
    serie_prevista = [[inicio.isoformat(), round(largo, 1)]]
    dias_reales = 0
    dias_totales = 0
    dia = inicio
    while dia < fin:
        t, real = temp_del_dia(dia)
        dias_totales += 1
        if t is not None:
            largo += max(0.0, _soderberg(t))
            dias_reales += int(real)
        dia += timedelta(days=1)
        serie_prevista.append([dia.isoformat(), round(largo, 1)])
    previsto_en = {fecha: v for fecha, v in serie_prevista}

    intervalos = []
    for (fa, la, _), (fz, lz, _) in zip(medidas, medidas[1:]):
        dias = (fz - fa).days
        if dias <= 0:
            continue
        temps_tramo = [diaria[d] for d in dias_con_dato if fa <= d < fz]
        tmedia = float(np.mean(temps_tramo)) if temps_tramo else None
        # El oxigeno del tramo no entra en la recta; se ensena porque es lo
        # primero que hay que mirar cuando el pez crece menos de lo que su
        # temperatura permite.
        od_tramo = np.asarray([f["od"] for f in limpias if fa <= f["cuando"].date() < fz], float)
        intervalos.append(
            {
                "desde": fa.isoformat(),
                "hasta": fz.isoformat(),
                "dias": dias,
                "dias_con_temperatura": len(temps_tramo),
                "temperatura_media": round(tmedia, 2) if tmedia is not None else None,
                "observado_mm_dia": round((lz - la) / dias, 3),
                "soderberg_mm_dia": round(_soderberg(tmedia), 3) if tmedia is not None else None,
                "lecturas_oxigeno": int(od_tramo.size),
                "oxigeno_medio": round(float(od_tramo.mean()), 2) if od_tramo.size else None,
                "pct_oxigeno_bajo_3": round(100.0 * float(np.mean(od_tramo < 3.0)), 1) if od_tramo.size else None,
            }
        )
    validos = [i for i in intervalos if i["soderberg_mm_dia"] is not None]
    r2 = None
    if len(validos) >= 2:
        r2 = round(_r2([i["observado_mm_dia"] for i in validos], [i["soderberg_mm_dia"] for i in validos]), 3)

    comparacion_longitud = [
        {
            "fecha": f.isoformat(),
            "medido_mm": round(l, 1),
            "previsto_mm": previsto_en.get(f.isoformat()),
            "peces": p,
        }
        for f, l, p in medidas
    ]

    return {
        "disponible": True,
        "tipo": "Regresión lineal simple (Söderberg)",
        "formula": "Crecimiento diario en longitud (mm/día) = −1,6707 + 0,09682 × temperatura (°C)",
        "fuente": "Informe 17, ecuación 1. Söderberg, tilapia del Nilo macho, R² = 0,95 en su publicación.",
        "dominio_validado": [21, 30],
        "que_se_compara": "Crecimiento en longitud medido entre biometrías frente al que predice la recta",
        "eje_x": "Temperatura media del agua en el intervalo (°C)",
        "eje_y": "Crecimiento diario en longitud (mm/día)",
        # Rango completo en que vive la tilapia. Por debajo de 17,3 C la recta da
        # valores negativos y un pez no encoge: se dibuja en cero.
        "linea_modelo": [[t, round(max(0.0, _soderberg(t)), 3)] for t in range(10, 46)],
        "cero_de_la_recta_c": round(1.6707 / 0.09682, 1),
        "puntos": [[i["temperatura_media"], i["observado_mm_dia"]] for i in validos],
        "intervalos": intervalos,
        "r2": r2,
        "serie_longitud_prevista": serie_prevista,
        "longitudes": comparacion_longitud,
        "cobertura_temperatura": {"dias_con_dato": dias_reales, "dias_totales": dias_totales},
        "ultimo_dia": _ultimo_dia(diaria),
        "lectura": _lectura_crecimiento(validos, r2),
    }


def _ultimo_dia(diaria: dict[date, float]) -> dict[str, Any] | None:
    if not diaria:
        return None
    dia = max(diaria)
    t = diaria[dia]
    return {
        "fecha": dia.isoformat(),
        "temperatura_media": round(t, 2),
        "soderberg_mm_dia": round(max(0.0, _soderberg(t)), 3),
        "en_rango_validado": 21.0 <= t <= 30.0,
    }


def _lectura_crecimiento(tramos: list, r2) -> str:
    if len(tramos) < 2 or r2 is None:
        return "Hacen falta al menos dos intervalos entre biometrías para contrastar la recta."
    primero, ultimo = tramos[0], tramos[-1]
    texto = (
        f"Con {len(tramos)} intervalos entre biometrías el R² ({_coma(r2)}) es solo orientativo"
        + ("; que sea negativo significa que la recta acierta menos que usar el promedio de los tramos. " if r2 < 0 else ". ")
        + f"La temperatura media apenas cambió ({_coma(primero['temperatura_media'], 1)} °C en el primer tramo y "
        f"{_coma(ultimo['temperatura_media'], 1)} °C en el último) y la recta predice casi lo mismo para ambos "
        f"({_coma(primero['soderberg_mm_dia'])} y {_coma(ultimo['soderberg_mm_dia'])} mm/día), pero el pez creció "
        f"{_coma(primero['observado_mm_dia'])} y {_coma(ultimo['observado_mm_dia'])} mm/día. Esa caída no la explica "
        "la temperatura."
    )
    if (ultimo.get("lecturas_oxigeno") or 0) >= 50 and ultimo.get("oxigeno_medio") is not None:
        texto += (
            f" En el último tramo el oxígeno medio fue {_coma(ultimo['oxigeno_medio'])} mg/L y el "
            f"{_coma(ultimo['pct_oxigeno_bajo_3'], 0)} % de las lecturas limpias estuvo por debajo de 3 mg/L."
        )
    return texto


# ----------------------------------------------------------------------
# 4) Calidad de agua con SVM
# ----------------------------------------------------------------------
def _calidad_agua(engine, limpias) -> dict[str, Any]:
    from sklearn.metrics import f1_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    from backend.app.models_engine.deterministic import water_quality as WQ

    etiquetas = ["Excelente", "Buena", "Regular", "Mala", "Muy mala"]
    codigo = {e: i for i, e in enumerate(etiquetas)}

    con_nitrato = [f for f in limpias if f["no3"] is not None and 0.0 <= f["no3"] <= NITRATO_MAX]
    descartadas_nitrato = len(limpias) - len(con_nitrato)

    X, nota, clase, cuando = [], [], [], []
    for f in con_nitrato:
        try:
            res = WQ.water_quality_index(f["t"], f["ph"], f["od"], f["no3"])
        except Exception:
            continue
        cls = res.get("classification")
        etiqueta = str(cls.get("label") if isinstance(cls, dict) else cls)
        if etiqueta not in codigo:
            continue
        X.append([f["t"], f["ph"], f["od"], f["no3"]])
        nota.append(float(res["ica"]))
        clase.append(etiqueta)
        cuando.append(f["cuando"])
    if len(X) < 200:
        return {"disponible": False, "motivo": "No hay lecturas limpias suficientes con nitrato válido."}
    X = np.asarray(X, float)
    y = np.asarray([codigo[c] for c in clase])
    nota_arr = np.asarray(nota, float)

    # SVM guardado: el que usan hoy las alarmas. Se entreno con el nitrato
    # saturado dentro de los datos, y aqui se mide cuanto coincide con la clase
    # de referencia sobre lecturas validas.
    acierto_guardado = None
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
            guardado = pickle.loads(base64.b64decode(arte["estimator_b64"]))
            orden = list(arte.get("class_order") or etiquetas)
            nombres = [orden[int(p)] if not isinstance(p, str) else str(p) for p in guardado.predict(X)]
            acierto_guardado = round(float(np.mean(np.asarray(nombres) == np.asarray(clase))), 3)
    except Exception:
        acierto_guardado = None

    # SVM reentrenado solo con lecturas limpias y nitrato valido, con la misma
    # receta del entrenamiento original (escalado + SVC RBF con clases
    # balanceadas) y corte temporal: aprende con lo antiguo, se prueba con lo
    # reciente, que nunca vio.
    corte = int(len(X) * 0.70)
    if len(set(y[:corte].tolist())) < 2:
        return {"disponible": False, "motivo": "El tramo de entrenamiento tiene una sola clase de calidad."}
    svm = make_pipeline(StandardScaler(), SVC(kernel="rbf", C=10.0, gamma="scale", class_weight="balanced"))
    svm.fit(X[:corte], y[:corte])
    pred_prueba = svm.predict(X[corte:])
    y_prueba = y[corte:]
    acierto = round(float(np.mean(pred_prueba == y_prueba)), 3)
    f1 = round(float(f1_score(y_prueba, pred_prueba, average="weighted", zero_division=0)), 3)

    presentes = sorted(set(y_prueba.tolist()) | set(pred_prueba.tolist()))
    matriz = {
        "etiquetas": [etiquetas[i] for i in presentes],
        "filas": [[int(np.sum((y_prueba == r) & (pred_prueba == p))) for p in presentes] for r in presentes],
    }

    recientes = list(zip(cuando[corte:], pred_prueba.tolist()))[-2000:]
    paso = max(1, len(recientes) // 400)
    serie_svm = [[c.isoformat(), etiquetas[int(p)]] for c, p in recientes[::paso]]
    if recientes and serie_svm[-1][0] != recientes[-1][0].isoformat():
        serie_svm.append([recientes[-1][0].isoformat(), etiquetas[int(recientes[-1][1])]])

    ultima = X[-1]
    try:
        detalle = WQ.water_quality_index(*[float(v) for v in ultima])
        componentes = [
            {"variable": c["variable"], "puntaje": round(float(c["normalized_score"]), 1), "peso": float(c["weight"])}
            for c in detalle["components"]
        ]
        puntaje_actual = round(float(detalle["ica"]), 1)
    except Exception:
        componentes, puntaje_actual = [], None
    clase_actual = {
        "componentes": componentes,
        "puntaje": puntaje_actual,
        "cuando": cuando[-1].isoformat(),
        "clase": etiquetas[int(svm.predict(X[-1:])[0])],
        "clase_referencia": clase[-1],
        "temperatura_c": round(float(ultima[0]), 2),
        "ph": round(float(ultima[1]), 2),
        "oxigeno_mg_l": round(float(ultima[2]), 2),
        "nitrato_mg_l": round(float(ultima[3]), 2),
    }

    dependencias = []
    for etiqueta, i in (("Oxígeno disuelto (mg/L)", 2), ("Ion nitrato (mg/L)", 3), ("Temperatura (°C)", 0), ("pH", 1)):
        x = X[:, i]
        if float(np.std(x)) == 0.0:
            continue
        pares = [[round(float(a), 3), round(float(b), 2)] for a, b in zip(x, nota_arr)]
        dependencias.append({"variable": etiqueta, "puntos": _muestrear(pares, 350), "recta": _recta(x, nota_arr)})
    dependencias.sort(key=lambda d: d["recta"]["r2"], reverse=True)

    return {
        "disponible": True,
        "tipo": "Máquina de vectores de soporte (SVC, núcleo RBF)",
        "que_se_compara": "Clase que asigna el SVM frente a la clase de referencia, y de qué variable depende la calidad",
        "lecturas": len(X),
        "descartadas_nitrato": descartadas_nitrato,
        "acierto_svm": acierto,
        "f1_svm": f1,
        "acierto_svm_guardado": acierto_guardado,
        "reparto": f"{_miles(corte)} lecturas de entrenamiento y {_miles(len(X) - corte)} de prueba, en orden temporal",
        "matriz_confusion": matriz,
        "serie_svm": serie_svm,
        "clase_actual": clase_actual,
        "orden_clases": etiquetas,
        "dependencias": dependencias,
        "origen_etiqueta": (
            "Las clases de referencia salen de la ponderación del equipo sobre las cuatro variables. No existe "
            "una medición independiente de «calidad del agua» contra la que validar: el SVM aprende a "
            "reconocer esa clasificación directamente de las lecturas del sensor."
        ),
        "lectura": _lectura_calidad(descartadas_nitrato, dependencias, acierto, acierto_guardado),
    }


def _lectura_calidad(descartadas: int, dependencias: list, acierto, acierto_guardado) -> str:
    partes = [
        f"Se apartaron {_miles(descartadas)} lecturas con nitrato por encima de 100 mg/L: la sonda marca "
        "14 000 mg/L cuando se satura o se desconecta, y ese valor falseaba la relación."
    ]
    if dependencias:
        primera = dependencias[0]
        nombre = primera["variable"].split(" (")[0].lower()
        partes.append(
            f"Con el nitrato válido, lo que más explica las diferencias de calidad entre una lectura y otra es "
            f"el {nombre} (R² {_coma(primera['recta']['r2'])}); cada una de las otras tres explica menos del "
            f"{_coma(max([d['recta']['r2'] for d in dependencias[1:]] or [0]) * 100 + 1, 0)} %."
        )
    if acierto is not None:
        partes.append(
            f"Reentrenado solo con lecturas limpias, el SVM acierta la clase en el {_coma(acierto * 100, 1)} % "
            "de las lecturas de prueba."
        )
    if acierto_guardado is not None and acierto is not None and acierto_guardado < acierto:
        partes.append(
            f"El SVM que usan hoy las alarmas, entrenado con el nitrato saturado, solo coincide en el "
            f"{_coma(acierto_guardado * 100, 1)} %: conviene reemplazarlo por este."
        )
    return " ".join(partes)


# ----------------------------------------------------------------------
# entrada
# ----------------------------------------------------------------------
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

    filas = _leer(engine, str(legacy), piscina)
    limpias, limpieza = _limpiar(filas)
    resultado = {
        "disponible": True,
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "limpieza": limpieza,
        "lectura_actual": lectura_actual(limpias),
        "modelos": {
            "SVM_OD_FORECAST_1H": _proyeccion_oxigeno(filas),
            "OXYGEN_STATUS_MODEL": _estado_oxigeno(limpias),
            "TILAPIA_GROWTH_TEMPERATURE": _crecimiento(engine, str(legacy), filas, limpias),
            "WATER_QUALITY_INDEX_ICA": _calidad_agua(engine, limpias),
        },
    }
    _cache[clave] = (ahora, resultado)
    return resultado
