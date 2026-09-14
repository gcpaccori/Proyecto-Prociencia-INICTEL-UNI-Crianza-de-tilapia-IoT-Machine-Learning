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
from functools import lru_cache
from typing import Any

import numpy as np
from sqlalchemy import text

from backend.app.application import model_projection as P

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
    X, cambio, actual, futuro, momentos = [], [], [], [], []
    for casilla in sorted(grid):
        previas = [casilla - timedelta(minutes=M.BIN_MINUTOS * d) for d in M.DESFASES]
        objetivo = casilla + timedelta(minutes=M.BIN_MINUTOS * M.PASOS_HORIZONTE)
        if objetivo not in grid or any(p not in grid for p in previas):
            continue
        fila = M._fila(grid, casilla, previas)
        if fila is None:
            continue
        X.append(fila)
        momentos.append(casilla)
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
        "horizontes": P.proyeccion_oxigeno_gb(gb, X, momentos, actual, grid, momentos[corte_train], M._rejilla(filas), M),
        "lectura": lectura,
    }


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]
MIN_LECTURAS_MES = 50
HORAS_PREVIAS_MIN = 18


def _hora_texto(h: float) -> str:
    minutos = int(round(h * 4)) * 15 % 1440
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _fecha_texto(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]}"


def _mae(obs, pred) -> float:
    return float(np.mean(np.abs(np.asarray(obs, float) - np.asarray(pred, float))))


# ----------------------------------------------------------------------
# 2) Estado de oxigeno disuelto: saturacion y ciclo diario
# ----------------------------------------------------------------------
def _horarias(limpias) -> list[dict[str, Any]]:
    grupos: dict = {}
    for f in limpias:
        grupos.setdefault(f["cuando"].replace(minute=0, second=0, microsecond=0), []).append(f)
    return [
        {"hora": h, "od": float(np.mean([f["od"] for f in v])), "t": float(np.mean([f["t"] for f in v]))}
        for h, v in sorted(grupos.items())
        if len(v) >= 2
    ]


def _con_nivel(horas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cada hora con el nivel de oxigeno de las 24 horas anteriores.

    El nivel sale solo del pasado: es lo que el estanque viene teniendo, y el
    ciclo diario dice cuanto se aparta de ese nivel a cada hora del dia.
    """
    indice = {x["hora"]: x for x in horas}
    salida = []
    for x in horas:
        previas = [indice[x["hora"] - timedelta(hours=k)] for k in range(1, 25) if x["hora"] - timedelta(hours=k) in indice]
        if len(previas) < HORAS_PREVIAS_MIN:
            continue
        w = 2 * math.pi * (x["hora"].hour + 0.5) / 24
        nivel = float(np.mean([p["od"] for p in previas]))
        salida.append({**x, "nivel": nivel, "sen": math.sin(w), "cos": math.cos(w), "deficit": od_saturacion(x["t"]) - nivel})
    return salida


def _ajuste(filas, columnas, desde=0, hasta=None):
    sel = filas[desde:hasta]
    A = np.column_stack([np.ones(len(sel))] + [[f[c] for f in sel] for c in columnas])
    y = np.asarray([f["od"] - f["nivel"] for f in sel])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef


def _predice(filas, columnas, coef):
    A = np.column_stack([np.ones(len(filas))] + [[f[c] for f in filas] for c in columnas])
    return np.asarray([f["nivel"] for f in filas]) + A @ coef


def _estado_oxigeno(limpias) -> dict[str, Any]:
    horas = _con_nivel(_horarias(limpias))
    if len(horas) < 24 * 14:
        return {"disponible": False, "motivo": "Hacen falta al menos dos semanas de horas con lecturas limpias."}

    ciclo = ["sen", "cos"]
    corte = int(len(horas) * 0.70)
    prueba = horas[corte:]
    obs = np.asarray([f["od"] for f in prueba])

    comparacion = []
    predicciones = {}
    for nombre, columnas in (
        ("Nivel de las 24 h previas + ciclo diario (el modelo)", ciclo),
        ("Solo el nivel de las 24 h previas, sin ciclo", []),
        ("Nivel + ciclo + déficit de saturación (intercambio con el aire)", ciclo + ["deficit"]),
    ):
        coef = _ajuste(horas, columnas, 0, corte)
        pred = _predice(prueba, columnas, coef)
        predicciones[nombre] = pred
        comparacion.append({"metodo": nombre, "r2": round(_r2(obs, pred), 3), "mae": round(_mae(obs, pred), 3)})
    pred_modelo = predicciones[comparacion[0]["metodo"]]

    # Modelo final con todo el historico, para la curva del ciclo y la proyeccion.
    a, b_sen, b_cos = _ajuste(horas, ciclo)
    horizontes = P.proyeccion_oxigeno_diaria(
        _horarias(limpias), _ajuste(horas, ciclo, 0, corte), (a, b_sen, b_cos), horas[corte]["hora"]
    )
    amplitud = math.hypot(b_sen, b_cos)
    hora_max = (math.degrees(math.atan2(b_sen, b_cos)) % 360) / 15
    hora_min = (hora_max + 12) % 24
    onda = lambda h: a + b_sen * math.sin(2 * math.pi * h / 24) + b_cos * math.cos(2 * math.pi * h / 24)

    anomalias = [[round(f["hora"].hour + 0.5, 2), round(f["od"] - f["nivel"], 3)] for f in horas]
    por_hora = []
    for h in range(24):
        v = [f["od"] - f["nivel"] for f in horas if f["hora"].hour == h]
        if v:
            por_hora.append([h + 0.5, round(float(np.mean(v)), 3), len(v)])
    todas = np.asarray([f["od"] - f["nivel"] for f in horas])
    ajuste_ciclo = np.asarray([onda(f["hora"].hour + 0.5) for f in horas])

    # Ultimos 7 dias: lo medido y lo que el modelo esperaba para cada hora.
    ultima = horas[-1]["hora"]
    recientes = [f for f in horas if f["hora"] > ultima - timedelta(days=7)]
    serie = [[f["hora"].isoformat(), round(f["od"], 3), round(f["nivel"] + onda(f["hora"].hour + 0.5), 3)] for f in recientes]

    # Proximas 24 h desde la ultima hora medida.
    ultimas24 = [f["od"] for f in _horarias(limpias) if f["hora"] > ultima - timedelta(hours=24)]
    nivel_actual = float(np.mean(ultimas24)) if ultimas24 else horas[-1]["nivel"]
    proyeccion = []
    for k in range(1, 25):
        hk = ultima + timedelta(hours=k)
        proyeccion.append([hk.isoformat(), round(nivel_actual + onda(hk.hour + 0.5), 3)])
    minimo = min(proyeccion, key=lambda p: p[1])
    maximo = max(proyeccion, key=lambda p: p[1])

    return {
        "disponible": True,
        "tipo": "Regresión armónica del ciclo diario, con saturación de Benson-Krause",
        "que_se_compara": "Oxígeno que el modelo esperaba a cada hora frente al que se midió, en semanas que el ajuste no vio",
        "formula": "OD(h) = nivel de las 24 h previas + a + b·sen(2πh/24) + c·cos(2πh/24)",
        "coeficientes": {"a": round(float(a), 4), "b": round(float(b_sen), 4), "c": round(float(b_cos), 4)},
        "eje_x": "Oxígeno medido (mg/L)",
        "eje_y": "Oxígeno esperado por el modelo (mg/L)",
        "puntos": _muestrear([[round(float(o), 3), round(float(p), 3)] for o, p in zip(obs, pred_modelo)]),
        "puntos_totales": len(prueba),
        "recta": _recta(obs, pred_modelo),
        "r2": round(_r2(obs, pred_modelo), 3),
        "mae": round(_mae(obs, pred_modelo), 3),
        "comparacion": comparacion,
        "reparto": f"{_miles(corte)} horas de ajuste y {_miles(len(prueba))} de prueba, en orden temporal",
        "ciclo": {
            "puntos": _muestrear(anomalias, 700),
            "por_hora": por_hora,
            "curva": [[round(h, 2), round(onda(h), 3)] for h in np.arange(0, 24.01, 0.25).tolist()],
            "r2": round(_r2(todas, ajuste_ciclo), 3),
            "amplitud_mg_l": round(amplitud, 2),
            "hora_maximo": _hora_texto(hora_max),
            "hora_minimo": _hora_texto(hora_min),
        },
        "serie": serie,
        "proyeccion": proyeccion,
        "nivel_actual_mg_l": round(nivel_actual, 2),
        "minimo_esperado": {"cuando": minimo[0], "od_mg_l": minimo[1]},
        "maximo_esperado": {"cuando": maximo[0], "od_mg_l": maximo[1]},
        "temperatura": _oxigeno_y_temperatura(limpias),
        "horizontes": horizontes,
        "lectura": _lectura_estado(comparacion, amplitud, hora_max, hora_min),
    }


def _lectura_estado(comparacion, amplitud, hora_max, hora_min) -> str:
    modelo, sin_ciclo, con_deficit = comparacion
    texto = (
        f"En semanas que el ajuste no vio, el modelo explica el {_coma(modelo['r2'] * 100, 0)} % de la variación del "
        f"oxígeno hora a hora, con un error medio de {_coma(modelo['mae'])} mg/L. Sin el ciclo diario, usando solo "
        f"el nivel de las 24 h previas, se explica el {_coma(sin_ciclo['r2'] * 100, 0)} %: el ciclo aporta la diferencia. "
        f"El oxígeno de este estanque sube hasta las {_hora_texto(hora_max)} y baja hasta las {_hora_texto(hora_min)}, "
        f"{_coma(amplitud)} mg/L por encima y por debajo de su nivel."
    )
    if con_deficit["r2"] <= modelo["r2"] + 0.01:
        texto += (
            " Agregar el déficit de saturación, que es el intercambio con el aire del balance de masas, no mejora el "
            f"ajuste (R² {_coma(con_deficit['r2'])}): en este estanque el intercambio con el aire no explica los cambios hora a hora."
        )
    return texto


def _oxigeno_y_temperatura(limpias) -> dict[str, Any]:
    """Oxigeno frente a temperatura, por mes: por que la temperatura no entra."""
    temps = [f["t"] for f in limpias]
    ods = [f["od"] for f in limpias]
    lo, hi = math.floor(min(temps)), math.ceil(max(temps))
    grupos: dict[str, list] = {}
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
    validos = {m["mes"] for m in por_mes}
    pares = [[round(f["t"], 2), round(f["od"], 3), f["cuando"].strftime("%Y-%m")] for f in limpias if f["cuando"].strftime("%Y-%m") in validos]
    sats = np.asarray([od_saturacion(t) for t in temps])
    porcentaje = 100 * np.asarray(ods) / sats
    return {
        "eje_x": "Temperatura del agua (°C)",
        "eje_y": "Oxígeno disuelto (mg/L)",
        "puntos": _muestrear(pares),
        "curva_saturacion": [[t, round(od_saturacion(t), 3)] for t in np.arange(lo, hi + 0.25, 0.25).round(2).tolist()],
        "recta": _recta(temps, ods),
        "por_mes": por_mes,
        "saturacion_mediana_pct": round(float(np.median(porcentaje)), 1),
    }


# ----------------------------------------------------------------------
# 3) Crecimiento de tilapia por temperatura y oxigeno
# ----------------------------------------------------------------------
# Modelo bioenergetico de Yi (1998), ecuacion 12 del Informe 16:
#
#   dW/dt = h·b(1−a)·ρ·τ(T)·δ(OD)·f·W^m − kmin·exp[j(T − Tmin)]·W^n
#
# El primer termino es el anabolismo (lo que el pez come y asimila) y el
# segundo el catabolismo en ayunas. Los coeficientes son los publicados por Yi
# para tilapia del Nilo, tal como los tabulan Chahid et al. (2021):
# h·b(1−a) = 0,8 × 0,62 × 0,47 = 0,233, el mismo 0,2919 × 0,81 = 0,236 de la
# tabla 1 del Informe 16. La tabla del Informe 16 da ademas los umbrales de
# oxigeno (critico 5, minimo 3 mg/L, Khater et al. 2021); su Kmin = 0,25 no se
# usa porque con el peso en gramos el catabolismo supera al anabolismo desde el
# primer dia. Nada de esto se ajusta con los datos del estanque: las
# biometrias solo sirven para comprobar.
YI = {"h": 0.8, "b": 0.62, "a": 0.53, "m": 0.67, "n": 0.81, "kmin": 0.00133, "j": 0.0132,
      "t_min": 24.0, "t_opt": 33.0, "t_max": 40.0}
OD_CRITICO = 5.0
OD_MINIMO = 3.0
OD_CRITICO_YI = 3.0
OD_MINIMO_YI = 0.3
LATITUD = -12.05  # Lima


def _soderberg(t: float) -> float:
    return -1.6707 + 0.09682 * t


def factor_temperatura(t: float) -> float:
    """τ de Yi (1998), ecuaciones 13 y 14 del Informe 16."""
    if t < YI["t_opt"]:
        return math.exp(-4.6 * ((YI["t_opt"] - t) / (YI["t_opt"] - YI["t_min"])) ** 4)
    return math.exp(-4.6 * ((t - YI["t_opt"]) / (YI["t_max"] - YI["t_opt"])) ** 4)


def factor_oxigeno(od: float, critico: float = OD_CRITICO, minimo: float = OD_MINIMO) -> float:
    """δ, ecuaciones 16 y 17 del Informe 16: 1 sobre el critico, 0 bajo el minimo."""
    return min(1.0, max(0.0, (od - minimo) / (critico - minimo)))


@lru_cache(maxsize=4096)
def fotoperiodo_horas(dia: date, latitud: float = LATITUD) -> float:
    """Horas de luz del dia, modelo CBM de Forsythe et al. (1995)."""
    J = dia.timetuple().tm_yday
    theta = 0.2163108 + 2 * math.atan(0.9671396 * math.tan(0.00860 * (J - 186)))
    phi = math.asin(0.39795 * math.cos(theta))
    lat = math.radians(latitud)
    x = (math.sin(math.radians(0.8333)) + math.sin(lat) * math.sin(phi)) / (math.cos(lat) * math.cos(phi))
    return 24 - (24 / math.pi) * math.acos(max(-1.0, min(1.0, x)))


def _paso_yi(w: float, t: float, delta: float, rho: float, f: float = 1.0) -> tuple[float, float]:
    anabolismo = YI["h"] * YI["b"] * (1 - YI["a"]) * rho * factor_temperatura(t) * delta * f * w ** YI["m"]
    catabolismo = YI["kmin"] * math.exp(YI["j"] * (t - YI["t_min"])) * w ** YI["n"]
    return anabolismo, catabolismo


def _crecimiento(engine, legacy: str, filas_crudas, limpias) -> dict[str, Any]:
    safe = legacy.replace("`", "``")
    with engine.connect() as con:
        bio = con.execute(
            text(
                f"""
                SELECT fecha_inicial, fecha_muestreo, cantidad_muestreo, cantidad_peces_iniciales, cantidad_peces_actuales,
                       bi_kg, bf_kg, prom_longitud_cm, prom_peso_g, tasa_crecimiento_g_dia AS tasa_guardada,
                       total_alimento_consumido_kg AS alimento, tasa_supervivencia_porcentaje AS supervivencia,
                       conversion_alimenticia AS conversion, observaciones AS observacion
                FROM `{safe}`.`biometrias`
                WHERE deleted_at IS NULL
                ORDER BY fecha_muestreo
                """
            )
        ).mappings().all()
        peces = con.execute(
            text(
                f"""
                SELECT b.fecha_muestreo AS fecha, bd.peso_g AS peso, bd.longitud_cm AS l_cm
                FROM `{safe}`.`biometrias` b
                JOIN `{safe}`.`biometria_detalles` bd ON bd.biometria_id = b.id
                WHERE b.deleted_at IS NULL AND bd.peso_g IS NOT NULL
                ORDER BY b.fecha_muestreo
                """
            )
        ).mappings().all()
        documento = con.execute(
            text(
                f"""
                SELECT ce.fecha_inicio AS etapa_inicio, ce.fecha_fin AS etapa_fin, ce.peso_final_gr AS etapa_peso_final,
                       e.nombre AS etapa, ce.volumen_piscigranja_m3 AS volumen, ces.fecha_siembra, ces.cantidad_siembra,
                       ces.peso_inicial_gr AS siembra_peso, ces.peso_final_gr AS peso_final_objetivo,
                       c.nombre AS campania, c.fecha_fin_estimada, c.estado
                FROM `{safe}`.`biometrias` b
                JOIN `{safe}`.`campania_etapas` ce ON ce.id = b.campania_etapa_id
                LEFT JOIN `{safe}`.`etapas` e ON e.id = ce.etapa_id
                JOIN `{safe}`.`campania_especies` ces ON ces.id = ce.campania_especie_id
                JOIN `{safe}`.`campanias` c ON c.id = ces.campania_id
                WHERE b.deleted_at IS NULL
                ORDER BY b.fecha_muestreo DESC
                LIMIT 1
                """
            )
        ).mappings().first()
    documento = dict(documento) if documento else {}
    pesos: dict[date, list[float]] = {}
    largos: dict[date, list[float]] = {}
    for p in peces:
        pesos.setdefault(p["fecha"], []).append(float(p["peso"]))
        if p["l_cm"] is not None:
            largos.setdefault(p["fecha"], []).append(float(p["l_cm"]) * 10.0)
    if len(pesos) < 2 or not bio:
        return {"disponible": False, "motivo": "Hacen falta al menos dos biometrías con pesos."}

    # Punto de partida: la siembra registrada en la primera biometria (biomasa
    # inicial entre peces sembrados); si no esta, la primera biometria medida.
    medias = {f: float(np.mean(v)) for f, v in pesos.items()}
    primera = bio[0]
    if primera["bi_kg"] and primera["cantidad_peces_iniciales"] and primera["fecha_inicial"]:
        siembra = primera["fecha_inicial"]
        medias.setdefault(siembra, float(primera["bi_kg"]) * 1000.0 / float(primera["cantidad_peces_iniciales"]))
    fechas = sorted(medias)
    inicio, fin = fechas[0], fechas[-1]
    info = {b["fecha_muestreo"]: b for b in bio}

    # Relacion peso-talla de los peces medidos (W = a·L^b, L en mm). Es la
    # forma de la ecuacion 2 del Informe 17, con el coeficiente de este
    # estanque. Sirve para pasar de peso a talla y de talla a peso.
    lw = np.asarray([(float(p["l_cm"]) * 10.0, float(p["peso"])) for p in peces if p["l_cm"] and p["peso"]])
    b_alo, ln_a = np.polyfit(np.log(lw[:, 0]), np.log(lw[:, 1]), 1)
    a_alo = math.exp(ln_a)
    talla_de_peso = lambda w: (w / a_alo) ** (1.0 / b_alo)
    peso_de_talla = lambda l: a_alo * l ** b_alo
    tallas = {f: float(np.mean(v)) for f, v in largos.items()}
    if inicio not in tallas:
        tallas[inicio] = talla_de_peso(medias[inicio])

    diaria = _temperatura_diaria(filas_crudas)
    dias_con_dato = sorted(diaria)
    od_dia: dict[date, list[float]] = {}
    for f in limpias:
        od_dia.setdefault(f["cuando"].date(), []).append(f["od"])
    ph_atascado = _rachas_planas([f["ph"] for f in filas_crudas])
    ph_dia: dict[date, list[float]] = {}
    for i, f in enumerate(filas_crudas):
        ph = _numero(f["ph"])
        if i not in ph_atascado and ph is not None and 3.0 <= ph <= 11.0:
            ph_dia.setdefault(f["created_at"].date(), []).append(ph)

    memoria_temp: dict = {}

    def temp_del_dia(dia: date) -> float:
        if dia not in memoria_temp:
            memoria_temp[dia] = _temp_del_dia(dia)
        return memoria_temp[dia]

    def _temp_del_dia(dia: date) -> float:
        if dia in diaria:
            return diaria[dia]
        antes = [d for d in dias_con_dato if d < dia]
        despues = [d for d in dias_con_dato if d > dia]
        if antes and despues:
            a, z = antes[-1], despues[0]
            return diaria[a] + (dia - a).days / (z - a).days * (diaria[z] - diaria[a])
        return diaria[antes[-1]] if antes else diaria[despues[0]]

    memoria_delta: dict = {}

    def delta_del_dia(dia: date, critico=OD_CRITICO, minimo=OD_MINIMO) -> float | None:
        clave = (dia, critico, minimo)
        if clave not in memoria_delta:
            v = od_dia.get(dia, [])
            memoria_delta[clave] = float(np.mean([factor_oxigeno(x, critico, minimo) for x in v])) if len(v) >= 20 else None
        return memoria_delta[clave]

    variantes = {
        "modelo": lambda d: delta_del_dia(d),
        "od_yi": lambda d: delta_del_dia(d, OD_CRITICO_YI, OD_MINIMO_YI),
        "sin_od": lambda d: 1.0,
    }

    volumen = float(documento["volumen"]) if documento.get("volumen") else None

    def peces_en(dia: date) -> float | None:
        """Peces en el estanque ese dia, entre los conteos de cada biometria."""
        for b in bio:
            if b["fecha_inicial"] and b["fecha_inicial"] <= dia < b["fecha_muestreo"]:
                ini, act = b["cantidad_peces_iniciales"], b["cantidad_peces_actuales"]
                if ini is None or act is None:
                    return None
                frac = (dia - b["fecha_inicial"]).days / (b["fecha_muestreo"] - b["fecha_inicial"]).days
                return float(ini) + frac * (float(act) - float(ini))
        ultimo = bio[-1]["cantidad_peces_actuales"]
        return float(ultimo) if ultimo is not None else None

    def alimento_disponible(w: float, dia: date, critica: float | None) -> float:
        """f de Yi (1998): 1 bajo la biomasa critica y critica/biomasa encima."""
        n = peces_en(dia)
        if critica is None or not volumen or not n:
            return 1.0
        biomasa = n * w / 1000.0 / volumen
        return 1.0 if biomasa <= critica else critica / biomasa

    def simular(w0: float, desde: date, hasta: date, variante: str = "modelo", critica: float | None = None) -> dict[date, float]:
        critica = criticas.get(variante) if critica is None else critica
        w, dia, salida = w0, desde, {desde: w0}
        while dia < hasta:
            d = variantes[variante](dia)
            anab, cat = _paso_yi(w, temp_del_dia(dia), 1.0 if d is None else d, fotoperiodo_horas(dia) / 12.0, alimento_disponible(w, dia, critica))
            w = max(0.01, w + anab - cat)
            dia += timedelta(days=1)
            salida[dia] = w
        return salida

    # Unico parametro que se calibra: la biomasa critica del estanque, con la
    # siembra y las biometrias anteriores a las lecturas validas de oxigeno.
    # Las biometrias posteriores quedan fuera y sirven de prueba.
    medidas_peso = [f for f in fechas if f in pesos]
    primer_od = next((d for d in sorted(od_dia) if len(od_dia[d]) >= 20), None)
    calibracion = [f for f in medidas_peso if primer_od is None or f <= primer_od + timedelta(days=7)]
    if len(calibracion) < 2:
        calibracion = medidas_peso[:2]
    criticas: dict[str, float | None] = {}
    for v in variantes:
        mejor = None
        if volumen:
            for x in np.arange(0.2, 8.0, 0.02):
                recorrido = simular(medias[inicio], inicio, calibracion[-1], v, float(x))
                error = sum((math.log(recorrido[f]) - math.log(medias[f])) ** 2 for f in calibracion)
                if mejor is None or error < mejor[0]:
                    mejor = (error, float(x))
        criticas[v] = round(mejor[1], 2) if mejor else None

    # Trayectoria continua desde la siembra: el modelo no vuelve a mirar las
    # biometrias en el camino.
    trayectoria = {v: simular(medias[inicio], inicio, fin, v) for v in variantes}

    soderberg_talla = {inicio: tallas[inicio]}
    largo, dia = tallas[inicio], inicio
    while dia < fin:
        largo += max(0.0, _soderberg(temp_del_dia(dia)))
        dia += timedelta(days=1)
        soderberg_talla[dia] = largo

    # Cada tramo, arrancando del peso medido al inicio del tramo.
    tramos = []
    for fa, fz in zip(fechas, fechas[1:]):
        dias = [fa + timedelta(days=k) for k in range((fz - fa).days)]
        if not dias:
            continue
        pred = {v: (simular(medias[fa], fa, fz, v)[fz] - medias[fa]) / len(dias) for v in variantes}
        deltas = [delta_del_dia(x) for x in dias]
        conocidos = [x for x in deltas if x is not None]
        ods = [v for x in dias for v in od_dia.get(x, [])]
        phs = [v for x in dias for v in ph_dia.get(x, [])]
        temps = [temp_del_dia(x) for x in dias]
        b = info.get(fz, {})
        observacion = (b.get("observacion") or "").strip()
        tramos.append(
            {
                "desde": fa.isoformat(),
                "hasta": fz.isoformat(),
                "dias": len(dias),
                "peso_inicial_g": round(medias[fa], 2),
                "peso_final_g": round(medias[fz], 2),
                "talla_inicial_mm": round(tallas[fa], 1),
                "talla_final_mm": round(tallas[fz], 1),
                "observado_mm_dia": round((tallas[fz] - tallas[fa]) / len(dias), 3),
                "inicio_es_siembra": fa not in pesos,
                "temperatura_media": round(float(np.mean(temps)), 2),
                "tau_medio": round(float(np.mean([factor_temperatura(t) for t in temps])), 2),
                "oxigeno_medio": round(float(np.mean(ods)), 2) if ods else None,
                "pct_oxigeno_bajo_3": round(100.0 * float(np.mean(np.asarray(ods) < 3.0)), 1) if ods else None,
                "delta_medio": round(float(np.mean(conocidos)), 2) if conocidos else None,
                "dias_sin_oxigeno": len(dias) - len(conocidos),
                "fotoperiodo_h": round(float(np.mean([fotoperiodo_horas(x) for x in dias])), 2),
                "ph_medio": round(float(np.mean(phs)), 2) if phs else None,
                "observado_g_dia": round((medias[fz] - medias[fa]) / len(dias), 3),
                "predicho_g_dia": round(pred["modelo"], 3),
                "predicho_od_yi_g_dia": round(pred["od_yi"], 3),
                "predicho_sin_od_g_dia": round(pred["sin_od"], 3),
                "supervivencia_pct": float(b["supervivencia"]) if b.get("supervivencia") is not None else None,
                "conversion_alimenticia": float(b["conversion"]) if b.get("conversion") is not None else None,
                "observacion": observacion if observacion and observacion.lower() != "sin observaciones" else None,
            }
        )

    obs_t = [t["observado_g_dia"] for t in tramos]

    fechas_peces = [f for f in fechas if f in pesos]
    fechas_tallas = [f for f in fechas if f in largos]
    obs_peso = [x for f in fechas_peces for x in pesos[f]]
    obs_talla = [x for f in fechas_tallas for x in largos[f]]

    def maximo_posible(grupos: dict, fechas_usadas: list) -> float:
        """R2 que lograria un modelo que acertara exacto el promedio de cada fecha."""
        todos = [x for f in fechas_usadas for x in grupos[f]]
        dentro = sum((x - np.mean(grupos[f])) ** 2 for f in fechas_usadas for x in grupos[f])
        total = float(np.sum((np.asarray(todos) - np.mean(todos)) ** 2))
        return 1.0 - dentro / total if total else 0.0

    def resumen_yi(clave: str, campo: str) -> dict[str, Any]:
        pred_t = [t[campo] for t in tramos]
        return {
            "r2_peces": round(_r2(obs_peso, [trayectoria[clave][f] for f in fechas_peces for _ in pesos[f]]), 3),
            "r2_talla": round(_r2(obs_talla, [talla_de_peso(trayectoria[clave][f]) for f in fechas_tallas for _ in largos[f]]), 3),
            "r2": round(_r2(obs_t, pred_t), 3),
            "mae": round(_mae(obs_t, pred_t), 3),
            "unidad_tramo": "g/día",
        }

    modelo = resumen_yi("modelo", "predicho_g_dia")
    obs_mm = [t["observado_mm_dia"] for t in tramos]
    pred_mm = [(soderberg_talla[date.fromisoformat(t["hasta"])] - soderberg_talla[date.fromisoformat(t["desde"])]) / t["dias"] for t in tramos]
    for t, v in zip(tramos, pred_mm):
        t["soderberg_mm_dia"] = round(v, 3)
    comparacion = [
        {"metodo": "Yi con OD crítico 5 y mínimo 3 mg/L, del Informe 16 (el modelo)", "mide": "peso", **modelo},
        {"metodo": "Yi con sus propios umbrales de OD, 3,0 y 0,3 mg/L", "mide": "peso", **resumen_yi("od_yi", "predicho_od_yi_g_dia")},
        {"metodo": "Yi sin factor de oxígeno (δ = 1)", "mide": "peso", **resumen_yi("sin_od", "predicho_sin_od_g_dia")},
        {
            "metodo": "Söderberg por temperatura (Informe 17)",
            "mide": "talla",
            "r2_peces": round(_r2(obs_peso, [peso_de_talla(soderberg_talla[f]) for f in fechas_peces for _ in pesos[f]]), 3),
            "r2_talla": round(_r2(obs_talla, [soderberg_talla[f] for f in fechas_tallas for _ in largos[f]]), 3),
            "r2": round(_r2(obs_mm, pred_mm), 3),
            "mae": round(_mae(obs_mm, pred_mm), 3),
            "unidad_tramo": "mm/día",
        },
        {
            "metodo": "Máximo posible: acertar exacto el promedio de cada biometría",
            "mide": "referencia",
            "r2_peces": round(maximo_posible(pesos, fechas_peces), 3),
            "r2_talla": round(maximo_posible(largos, fechas_tallas), 3),
            "r2": None,
            "mae": None,
            "unidad_tramo": None,
        },
    ]

    pares = [[round(x, 2), round(trayectoria["modelo"][f], 2), f.isoformat()] for f in fechas_peces for x in pesos[f]]
    obs_p = [p[0] for p in pares]
    pred_p = [p[1] for p in pares]

    # Ventana con oxigeno medido: desde la primera biometria a partir de la cual
    # los tramos tienen lecturas validas, sin volver a mirar los pesos.
    ventana = None
    con_od = [t for t in tramos if t["dias_sin_oxigeno"] < t["dias"] / 2]
    if con_od:
        arranque = date.fromisoformat(con_od[0]["desde"])
        recorrido = simular(medias[arranque], arranque, fin)
        ventana = {
            "desde": arranque.isoformat(),
            "peso_inicial_g": round(medias[arranque], 2),
            "puntos": [
                {
                    "fecha": f.isoformat(),
                    "medido_g": round(medias[f], 2),
                    "predicho_g": round(recorrido[f], 2),
                    "error_pct": round(100.0 * (recorrido[f] - medias[f]) / medias[f], 1),
                }
                for f in fechas
                if f > arranque
            ],
            "serie": [[d.isoformat(), round(w, 2)] for d, w in sorted(recorrido.items())],
        }

    registro = []
    for b in bio:
        f = b["fecha_muestreo"]
        if f not in pesos:
            continue
        w = np.asarray(pesos[f])
        l_cm = np.asarray(largos.get(f, []), float) / 10.0
        k = 100.0 * w / l_cm ** 3 if len(l_cm) == len(w) and len(w) else np.asarray([])
        dias = (f - b["fecha_inicial"]).days if b["fecha_inicial"] else None
        anterior = medias.get(b["fecha_inicial"])
        registro.append(
            {
                "fecha": f.isoformat(),
                "peces_medidos": int(len(w)),
                "peces_registrados": int(b["cantidad_muestreo"]) if b["cantidad_muestreo"] is not None else None,
                "talla_media_mm": round(float(np.mean(largos[f])), 1) if f in largos else None,
                "talla_de_mm": round(float(np.std(largos[f], ddof=1)), 1) if f in largos and len(largos[f]) > 1 else None,
                "peso_medio_g": round(float(w.mean()), 2),
                "peso_de_g": round(float(w.std(ddof=1)), 2) if len(w) > 1 else None,
                "promedio_guardado_ok": b["prom_peso_g"] is not None and abs(float(b["prom_peso_g"]) - float(w.mean())) < 0.05,
                "factor_condicion": round(float(k.mean()), 2) if len(k) else None,
                "biomasa_kg": float(b["bf_kg"]) if b["bf_kg"] is not None else None,
                "peces_en_estanque": float(b["cantidad_peces_actuales"]) if b["cantidad_peces_actuales"] is not None else None,
                "supervivencia_pct": float(b["supervivencia"]) if b["supervivencia"] is not None else None,
                "alimento_kg": float(b["alimento"]) if b["alimento"] is not None else None,
                "conversion_alimenticia": float(b["conversion"]) if b["conversion"] is not None else None,
                "tasa_guardada_g_dia": float(b["tasa_guardada"]) if b["tasa_guardada"] is not None else None,
                "tasa_por_pez_g_dia": round((float(w.mean()) - anterior) / dias, 3) if anterior is not None and dias else None,
            }
        )
    rango_l = np.arange(math.floor(lw[:, 0].min() / 10) * 10 - 10, math.ceil(lw[:, 0].max() / 10) * 10 + 11, 2.0)
    alometria = {
        "a": float(f"{a_alo:.4e}"),
        "b": round(float(b_alo), 3),
        "r2": round(_r2(lw[:, 1], a_alo * lw[:, 0] ** b_alo), 3),
        "n": int(len(lw)),
        "a_con_b3": float(f"{float(np.sum(lw[:, 1] * lw[:, 0] ** 3) / np.sum(lw[:, 0] ** 6)):.4e}"),
        "puntos": [[round(float(l), 1), round(float(w), 2), f.isoformat()] for f in fechas_peces for l, w in zip(largos.get(f, []), pesos[f])],
        "curva": [[round(float(l), 1), round(peso_de_talla(float(l)), 2)] for l in rango_l],
        "curva_informe17": [[round(float(l), 1), round(1.861e-5 * float(l) ** 3, 2)] for l in rango_l],
        "talla_siembra_mm": round(tallas[inicio], 1) if inicio not in largos else None,
    }

    # Condicion de hoy: los factores del modelo con la temperatura y el oxigeno
    # de hoy, para un pez del peso de la ultima biometria. No se estima el peso
    # actual del lote: desde esa biometria no hay pesos que lo comprueben.
    hoy = max(diaria) if diaria else fin
    t_hoy = temp_del_dia(hoy)
    d_hoy = delta_del_dia(hoy)
    anab_hoy, cat_hoy = _paso_yi(medias[fin], t_hoy, 1.0 if d_hoy is None else d_hoy, fotoperiodo_horas(hoy) / 12.0, alimento_disponible(medias[fin], hoy, criticas["modelo"]))

    horizontes = _proyeccion_crecimiento(
        documento, inicio, fin, hoy, medias, pesos, diaria, od_dia, temp_del_dia, delta_del_dia, talla_de_peso, simular,
        lambda w, dia: alimento_disponible(w, dia, criticas["modelo"]),
    )

    return {
        "disponible": True,
        "tipo": "Modelo bioenergético de crecimiento (Yi, 1998)",
        "formula": "dW/dt = 0,233 · ρ · τ(T) · δ(OD) · f · W^0,67 − 0,00133 · e^(0,0132·(T − 24)) · W^0,81",
        "formula_delta": (
            "δ = 1 si OD > 5;  δ = (OD − 3) ÷ 2 entre 3 y 5;  δ = 0 si OD < 3 mg/L.   τ = e^(−4,6·((33 − T) ÷ 9)^4) bajo 33 °C.   "
            f"ρ = horas de luz ÷ 12.   f = 1 bajo {_coma(criticas['modelo'] or 0, 2)} kg/m³ de biomasa y {_coma(criticas['modelo'] or 0, 2)} ÷ biomasa encima"
        ),
        "biomasa_critica_kg_m3": criticas["modelo"],
        "calibrado_con": [f.isoformat() for f in calibracion],
        "volumen_m3": volumen,
        "que_se_compara": "Peso y crecimiento que predice el modelo frente a lo medido en las biometrías",
        "eje_x": "Peso medido (g)",
        "eje_y": "Peso que predice el modelo (g)",
        "puntos": pares,
        "puntos_totales": len(pares),
        "recta": _recta(obs_p, pred_p),
        "r2": modelo["r2_peces"],
        "r2_tasas": modelo["r2"],
        "mae": modelo["mae"],
        "comparacion": comparacion,
        "intervalos": tramos,
        "ventana_con_oxigeno": ventana,
        "peces": [[f.isoformat(), round(x, 2)] for f in fechas_peces for x in pesos[f]],
        "peces_talla": [[f.isoformat(), round(x, 1)] for f in fechas_tallas for x in largos[f]],
        "medias": [
            {
                "fecha": f.isoformat(),
                "peso_g": round(medias[f], 2),
                "talla_mm": round(tallas[f], 1),
                "medido": f in pesos,
                "previsto_g": round(trayectoria["modelo"][f], 2),
                "previsto_talla_mm": round(talla_de_peso(trayectoria["modelo"][f]), 1),
                "soderberg_mm": round(soderberg_talla[f], 1),
            }
            for f in fechas
        ],
        "serie_talla_modelo": [[d.isoformat(), round(talla_de_peso(w), 1)] for d, w in sorted(trayectoria["modelo"].items())],
        "serie_talla_soderberg": [[d.isoformat(), round(l, 1)] for d, l in sorted(soderberg_talla.items())],
        "biometrias": registro,
        "alometria": alometria,
        "serie_peso_modelo": [[d.isoformat(), round(w, 2)] for d, w in sorted(trayectoria["modelo"].items())],
        "serie_peso_sin_od": [[d.isoformat(), round(w, 2)] for d, w in sorted(trayectoria["sin_od"].items())],
        "curva_tau": [[t, round(factor_temperatura(t), 3)] for t in np.arange(20, 42.01, 0.5).round(1).tolist()],
        "curva_delta": [[o, round(factor_oxigeno(o), 3)] for o in np.arange(0, 8.01, 0.1).round(1).tolist()],
        "dias_temperatura": [[round(temp_del_dia(inicio + timedelta(days=k)), 2), round(factor_temperatura(temp_del_dia(inicio + timedelta(days=k))), 3)] for k in range((hoy - inicio).days + 1)],
        "dias_oxigeno": [[round(float(np.mean(v)), 2), round(float(np.mean([factor_oxigeno(x) for x in v])), 3)] for d, v in sorted(od_dia.items()) if len(v) >= 20 and inicio <= d],
        "hoy": {
            "fecha": hoy.isoformat(),
            "temperatura_media": round(t_hoy, 2),
            "tau": round(factor_temperatura(t_hoy), 2),
            "oxigeno_medio": round(float(np.mean(od_dia[hoy])), 2) if od_dia.get(hoy) else None,
            "delta": round(d_hoy, 2) if d_hoy is not None else None,
            "fotoperiodo_h": round(fotoperiodo_horas(hoy), 2),
            "crecimiento_referencia_g_dia": round(anab_hoy - cat_hoy, 3),
            "ultima_biometria": fin.isoformat(),
            "peso_ultima_biometria_g": round(medias[fin], 2),
        },
        "horizontes": horizontes,
        "parametros": {**YI, "od_critico": OD_CRITICO, "od_minimo": OD_MINIMO, "latitud": LATITUD, "biomasa_critica_kg_m3": criticas["modelo"], "phi_amoniaco": 1.0},
        "lectura": _lectura_crecimiento(tramos, modelo, comparacion, ventana, criticas["modelo"], calibracion),
    }


# Ciclo comercial de referencia del Informe 18 (Aguilar et al., 2010, alimento
# extruido): peso y talla total al sembrar y al final de cada fase.
CICLO_REFERENCIA = [
    {"dia": 0, "fase": "Siembra de alevines", "peso_g": 0.805, "talla_mm": 36.5},
    {"dia": 45, "fase": "Fin de alevinaje", "peso_g": 40.0, "talla_mm": 130.0},
    {"dia": 77, "fase": "Fin de crecimiento 1", "peso_g": 118.0, "talla_mm": 184.3},
    {"dia": 177, "fase": "Fin de crecimiento 2", "peso_g": 445.0, "talla_mm": 280.0},
    {"dia": 249, "fase": "Fin de finalización", "peso_g": 606.0, "talla_mm": 320.0},
]


def _proyeccion_crecimiento(doc, inicio, fin, hoy, medias, pesos, diaria, od_dia, temp_del_dia, delta_del_dia, talla_de_peso, simular, alimento) -> dict[str, Any]:
    """Proyeccion del peso desde la ultima biometria, por escenarios de oxigeno.

    Hasta hoy se usan la temperatura y el oxigeno medidos; desde hoy, la
    temperatura del mismo dia del anio anterior (o la media de los ultimos 30
    dias si no hay registro) y un oxigeno segun el escenario.
    """
    siembra = doc.get("fecha_siembra") or inicio
    fin_ciclo = siembra + timedelta(days=CICLO_REFERENCIA[-1]["dia"])
    fin_proyeccion = max(hoy + timedelta(days=P.HORIZONTES_DIAS[-1]["dias"]), fin_ciclo)

    recientes = [d for d in diaria if hoy - timedelta(days=30) < d <= hoy]
    t_reciente = float(np.mean([diaria[d] for d in recientes])) if recientes else temp_del_dia(hoy)
    deltas = [x for x in (delta_del_dia(d) for d in recientes) if x is not None]
    delta_reciente = float(np.mean(deltas)) if deltas else 1.0
    meses: dict[str, list] = {}
    for d in od_dia:
        x = delta_del_dia(d)
        if x is not None:
            meses.setdefault(d.strftime("%Y-%m"), []).append(x)
    meses = {m: float(np.mean(v)) for m, v in meses.items() if len(v) >= 10}
    peor = min(meses.items(), key=lambda x: x[1]) if meses else None

    def temp_futura(d):
        anterior = d - timedelta(days=365)
        return diaria.get(anterior, t_reciente)

    def recorrer(delta_futuro: float):
        w, d = medias[fin], fin
        serie = [[d.isoformat(), round(w, 2), round(talla_de_peso(w), 1)]]
        while d < fin_proyeccion:
            if d < hoy:
                t = temp_del_dia(d)
                dl = delta_del_dia(d)
                dl = 1.0 if dl is None else dl
            else:
                t, dl = temp_futura(d), delta_futuro
            anab, cat = _paso_yi(w, t, dl, fotoperiodo_horas(d) / 12.0, alimento(w, d))
            w = max(0.01, w + anab - cat)
            d += timedelta(days=1)
            serie.append([d.isoformat(), round(w, 2), round(talla_de_peso(w), 1)])
        return serie

    escenarios = [
        {
            "id": "reciente",
            "nombre": "Si siguen las condiciones de los últimos 30 días",
            "delta": round(delta_reciente, 2),
            "serie": recorrer(delta_reciente),
        },
        {"id": "sin_limite", "nombre": "Con el oxígeno siempre sobre 5 mg/L", "delta": 1.0, "serie": recorrer(1.0)},
    ]
    if peor is not None:
        anio, mes = peor[0].split("-")
        escenarios.append(
            {
                "id": "peor_mes",
                "nombre": f"Con el oxígeno de {MESES[int(mes) - 1]} {anio}, el peor mes medido",
                "delta": round(peor[1], 2),
                "serie": recorrer(peor[1]),
            }
        )

    opciones = [{**h, "hasta": (hoy + timedelta(days=h["dias"])).isoformat()} for h in P.HORIZONTES_DIAS]
    if fin_ciclo > hoy:
        opciones.append({"id": "ciclo", "dias": (fin_ciclo - hoy).days, "nombre": f"Hasta el fin del ciclo (día {CICLO_REFERENCIA[-1]['dia']})", "hasta": fin_ciclo.isoformat()})
    fin_campania = doc.get("fecha_fin_estimada")
    if fin_campania and fin_campania > hoy:
        opciones.append({"id": "campania", "dias": (fin_campania - hoy).days, "nombre": "Hasta el fin estimado de la campaña", "hasta": fin_campania.isoformat()})

    # Cuanto acierta proyectar desde una biometria hasta las siguientes, con
    # las condiciones medidas en el camino.
    medidas = [f for f in sorted(medias) if f in pesos]
    comprobacion = []
    for i, fa in enumerate(medidas):
        for fz in medidas[i + 1:]:
            recorrido = simular(medias[fa], fa, fz)
            dias = [fa + timedelta(days=k) for k in range((fz - fa).days)]
            con_od = sum(1 for x in dias if delta_del_dia(x) is not None) >= len(dias) / 2
            comprobacion.append(
                {
                    "desde": fa.isoformat(),
                    "hasta": fz.isoformat(),
                    "dias": len(dias),
                    "medido_g": round(medias[fz], 2),
                    "predicho_g": round(recorrido[fz], 2),
                    "error_pct": round(100.0 * (recorrido[fz] - medias[fz]) / medias[fz], 1),
                    "oxigeno_medido": con_od,
                }
            )

    return {
        "opciones": opciones,
        "hoy": hoy.isoformat(),
        "desde_biometria": fin.isoformat(),
        "peso_desde_g": round(medias[fin], 2),
        "temperatura_futura": round(t_reciente, 2),
        "escenarios": escenarios,
        "ciclo": {
            "campania": doc.get("campania"),
            "estado": doc.get("estado"),
            "siembra": siembra.isoformat(),
            "alevines": int(doc["cantidad_siembra"]) if doc.get("cantidad_siembra") else None,
            "peso_siembra_g": float(doc["siembra_peso"]) if doc.get("siembra_peso") is not None else round(medias[inicio], 2),
            "talla_siembra_mm": round(talla_de_peso(float(doc["siembra_peso"]) if doc.get("siembra_peso") is not None else medias[inicio]), 1),
            "peso_final_objetivo_g": float(doc["peso_final_objetivo"]) if doc.get("peso_final_objetivo") is not None else None,
            "fin_campania": fin_campania.isoformat() if fin_campania else None,
            "etapa": doc.get("etapa"),
            "fin_etapa": doc["etapa_fin"].isoformat() if doc.get("etapa_fin") else None,
            "peso_final_etapa_g": float(doc["etapa_peso_final"]) if doc.get("etapa_peso_final") is not None else None,
            "fin_ciclo_referencia": fin_ciclo.isoformat(),
            "referencia": [{**r, "fecha": (siembra + timedelta(days=r["dia"])).isoformat()} for r in CICLO_REFERENCIA],
        },
        "comprobacion": comprobacion,
        "supuestos": (
            f"Desde la última biometría ({_fecha_texto(fin.isoformat())}, {_coma(medias[fin], 1)} g) hasta hoy el modelo usa la "
            "temperatura, el oxígeno y las horas de luz medidos. Desde hoy usa la temperatura del mismo día del año anterior "
            f"cuando existe registro (si no, {_coma(t_reciente, 1)} °C, la media de los últimos 30 días), las horas de luz "
            "calculadas para cada fecha y un oxígeno según el escenario. La talla sale del peso con la relación peso–talla "
            "del estanque. La biomasa usa el último conteo de peces; si hay mortalidad, cosecha parcial o enfermedad, el lote "
            "crecerá distinto."
        ),
    }


def _lectura_crecimiento(tramos: list, modelo: dict, comparacion: list, ventana: dict | None, critica: float | None, calibracion: list) -> str:
    od_yi, sin_od = comparacion[1], comparacion[2]
    maximo = next((c for c in comparacion if c.get("mide") == "referencia"), None)
    soderberg = next((c for c in comparacion if c.get("mide") == "talla"), None)
    texto = ""
    if critica is not None and calibracion:
        texto += (
            f"El único parámetro calibrado con este estanque es la biomasa crítica ({_coma(critica, 2)} kg/m³), usando la "
            f"siembra y las biometrías hasta el {_fecha_texto(calibracion[-1].isoformat())}: sobre esa biomasa la comida "
            "por pez deja de alcanzar y el crecimiento se frena, como en el modelo de Yi. "
        )
    if ventana and ventana["puntos"]:
        detalle = "; ".join(
            f"el {_fecha_texto(x['fecha'])} predice {_coma(x['predicho_g'], 1)} g y se midieron {_coma(x['medido_g'], 1)} g ({'+' if x['error_pct'] >= 0 else ''}{_coma(x['error_pct'], 1)} %)"
            for x in ventana["puntos"]
        )
        texto += f"En las biometrías que no entraron en la calibración, partiendo del peso medido el {_fecha_texto(ventana['desde'])}, {detalle}. "
    texto += (
        f"Sobre toda la campaña explica el {_coma(modelo['r2_peces'] * 100, 0)} % del peso de los peces medidos"
        + (f" (lo máximo posible con peces de distinto tamaño en cada fecha es {_coma(maximo['r2_peces'] * 100, 0)} %)" if maximo else "")
        + f" y el {_coma(modelo['r2_talla'] * 100, 0)} % de su talla"
        + (f"; Söderberg, que calcula talla directamente, llega a {_coma(soderberg['r2_talla'])}" if soderberg else "")
        + ". "
        f"El oxígeno se nota sobre todo tramo a tramo: el R² del crecimiento por tramo es {_coma(modelo['r2'])} con los umbrales "
        f"del Informe 16, {_coma(od_yi['r2'])} con los del propio Yi (3,0 y 0,3 mg/L) y {_coma(sin_od['r2'])} sin factor de oxígeno."
    )
    critico = [t for t in tramos if t.get("pct_oxigeno_bajo_3") is not None and t["pct_oxigeno_bajo_3"] >= 90]
    if critico:
        t = critico[0]
        texto += (
            f" Del {_fecha_texto(t['desde'])} al {_fecha_texto(t['hasta'])} el {_coma(t['pct_oxigeno_bajo_3'], 0)} % de las "
            f"lecturas estuvo bajo 3 mg/L y el lote ganó {_coma(t['observado_g_dia'])} g/día"
        )
        if t.get("conversion_alimenticia") and t["conversion_alimenticia"] > 3:
            texto += f" con una conversión alimenticia de {_coma(t['conversion_alimenticia'], 0)}: comió pero no creció"
        texto += "."
    sin_dato = [t for t in tramos if t["dias_sin_oxigeno"] >= t["dias"] * 0.5]
    if sin_dato:
        texto += f" Hasta el {_fecha_texto(sin_dato[-1]['hasta'])} no hay lecturas válidas de oxígeno y se toma δ = 1."
    texto += " No hay sensor de amoníaco, así que su factor se toma como 1."
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

    horas_d = _con_nivel(_horarias(limpias))
    corte_d = int(len(horas_d) * 0.70)
    horizontes = None
    if len(horas_d) >= 48:
        corte_tiempo = max(cuando[corte], horas_d[corte_d]["hora"])
        horizontes = P.proyeccion_calidad(
            svm, etiquetas, WQ, _horarias(limpias), _ajuste(horas_d, ["sen", "cos"], 0, corte_d),
            _ajuste(horas_d, ["sen", "cos"]), con_nitrato, corte_tiempo,
        )

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
        "horizontes": horizontes,
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
