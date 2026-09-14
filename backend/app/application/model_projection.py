"""Proyecciones de los modelos a los horizontes del modulo.

El modulo de modelos ofrecio desde el inicio horizontes de 1 hora, 24 y 72
horas, 7 y 30 dias para el agua y el oxigeno, y de 1 a 180 dias para la
biometria. Cada modelo proyecta a todos ellos con su propia mecanica, y cada
proyeccion lleva al lado cuanto acerto ese mismo calculo en el pasado: a una
hora un modelo puede ser fiable y a treinta dias no decir nada util, y eso se
muestra en vez de esconderse.

Supuestos, porque el futuro de las entradas no se mide:

  oxigeno a 1 h       un gradient boosting por horizonte (estrategia directa)
  ciclo diario        nivel de las ultimas 24 horas mas el ciclo ajustado
  calidad de agua     oxigeno del ciclo diario, temperatura de la misma hora en
                      los ultimos 7 dias, pH y nitrato de las ultimas 24 horas
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import numpy as np

HORIZONTES_HORAS = [
    {"id": "1h", "horas": 1, "nombre": "1 hora"},
    {"id": "24h", "horas": 24, "nombre": "24 horas"},
    {"id": "72h", "horas": 72, "nombre": "72 horas"},
    {"id": "7d", "horas": 168, "nombre": "7 días"},
    {"id": "30d", "horas": 720, "nombre": "30 días"},
]
HORAS_MAX = HORIZONTES_HORAS[-1]["horas"]
HORIZONTES_DIAS = [
    {"id": "1d", "dias": 1, "nombre": "1 día"},
    {"id": "7d", "dias": 7, "nombre": "7 días"},
    {"id": "30d", "dias": 30, "nombre": "30 días"},
    {"id": "90d", "dias": 90, "nombre": "90 días"},
    {"id": "180d", "dias": 180, "nombre": "180 días"},
]
MINIMO_CASOS = 8


def _r2(obs, pred) -> float | None:
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)
    if len(obs) < MINIMO_CASOS:
        return None
    total = float(np.sum((obs - obs.mean()) ** 2))
    if not total:
        return None
    return 1.0 - float(np.sum((obs - pred) ** 2)) / total


def _confiabilidad(obs_por_h: dict[int, list], pred_por_h: dict[int, list]) -> list[dict[str, Any]]:
    salida = []
    for h in HORIZONTES_HORAS:
        obs = obs_por_h.get(h["horas"], [])
        pred = pred_por_h.get(h["horas"], [])
        n = len(obs)
        r2 = _r2(obs, pred)
        salida.append(
            {
                "id": h["id"],
                "nombre": h["nombre"],
                "casos": n,
                "r2": round(r2, 3) if r2 is not None else None,
                "mae": round(float(np.mean(np.abs(np.asarray(obs) - np.asarray(pred)))), 3) if n >= MINIMO_CASOS else None,
                "comprobable": n >= MINIMO_CASOS,
            }
        )
    return salida


# ----------------------------------------------------------------------
# 1) Gradient boosting de oxigeno: un modelo por horizonte
# ----------------------------------------------------------------------
# Encadenar el modelo de una hora sobre sus propias previsiones acumula el
# error: a 72 horas ya rinde peor que el promedio y a 30 dias se desploma. Lo
# correcto en series temporales es la estrategia directa: un modelo por
# horizonte, con las mismas variables del presente, que aprende el cambio de
# oxigeno a ese plazo. Para no mezclar futuro con pasado, cada modelo solo
# aprende de momentos cuyo objetivo cae antes del inicio de la prueba.
def proyeccion_oxigeno_gb(modelo_1h, X, momentos, actual, grid: dict, corte: datetime, grid_actual: dict, M) -> dict[str, Any]:
    from sklearn.ensemble import GradientBoostingRegressor

    X = np.asarray(X, float)
    actual = np.asarray(actual, float)
    modelos, obs, pred = {}, {}, {}
    for h in HORIZONTES_HORAS:
        horas = h["horas"]
        destino = [m + timedelta(hours=horas) for m in momentos]
        futuro = np.asarray([grid[d][0] if d in grid else np.nan for d in destino])
        entrena = np.asarray([not np.isnan(f) and d < corte for f, d in zip(futuro, destino)])
        prueba = np.asarray([not np.isnan(f) and m >= corte for f, m in zip(futuro, momentos)])
        if horas == M.PASOS_HORIZONTE * M.BIN_MINUTOS / 60:
            modelo = modelo_1h
        elif entrena.sum() >= 300:
            modelo = GradientBoostingRegressor(random_state=20260907, n_estimators=200, max_depth=3, learning_rate=0.05)
            modelo.fit(X[entrena], (futuro - actual)[entrena])
        else:
            modelo = None
        modelos[horas] = modelo
        if modelo is not None and prueba.sum():
            obs[horas] = futuro[prueba].tolist()
            pred[horas] = np.clip(actual[prueba] + modelo.predict(X[prueba]), 0.0, 20.0).tolist()

    confiabilidad = _confiabilidad(obs, pred)

    # Prevision desde la ultima casilla medida.
    paso = timedelta(minutes=M.BIN_MINUTOS)
    puntos, origen, od_ahora = [], None, None
    if grid_actual:
        origen = max(grid_actual)
        previas = []
        for d in M.DESFASES:
            k = origen - paso * d
            cercana = k if k in grid_actual else M._mas_cercana(grid_actual, k)
            previas.append(cercana)
        if all(p is not None for p in previas):
            fila = M._fila(grid_actual, origen, previas)
            od_ahora = grid_actual[origen][0]
            if fila is not None:
                for h, c in zip(HORIZONTES_HORAS, confiabilidad):
                    modelo = modelos.get(h["horas"])
                    if modelo is None:
                        continue
                    valor = min(20.0, max(0.0, od_ahora + float(modelo.predict([fila])[0])))
                    puntos.append(
                        {
                            "id": h["id"],
                            "nombre": h["nombre"],
                            "horas": h["horas"],
                            "cuando": (origen + timedelta(hours=h["horas"])).isoformat(),
                            "od_mg_l": round(valor, 3),
                            "error_medio": c["mae"],
                            "r2": c["r2"],
                        }
                    )
    return {
        "opciones": HORIZONTES_HORAS,
        "desde": origen.isoformat() if origen else None,
        "valor_inicial": round(od_ahora, 3) if od_ahora is not None else None,
        "puntos": puntos,
        "unidad": "mg/L",
        "confiabilidad": confiabilidad,
        "supuestos": (
            "Un gradient boosting por horizonte, con las mismas variables del presente: el oxígeno de las últimas dos "
            "horas y su tendencia, el déficit de saturación, la hora del día, la temperatura y el pH. Cada uno aprendió "
            "solo de momentos cuyo resultado cae antes del periodo de prueba; la confiabilidad se mide en ese periodo."
        ),
    }


# ----------------------------------------------------------------------
# 2) Ciclo diario del oxigeno
# ----------------------------------------------------------------------
def onda_diaria(coef, hora: float) -> float:
    a, b, c = coef
    return a + b * math.sin(2 * math.pi * hora / 24.0) + c * math.cos(2 * math.pi * hora / 24.0)


def nivel_24h(indice: dict, momento: datetime) -> float | None:
    v = [indice[momento - timedelta(hours=k)] for k in range(0, 24) if momento - timedelta(hours=k) in indice]
    return float(np.mean(v)) if len(v) >= 18 else None


def proyeccion_oxigeno_diaria(horas: list[dict], coef_prueba, coef_final, corte: datetime) -> dict[str, Any]:
    """OD(t) = nivel de las 24 h hasta el origen + ciclo diario de la hora t."""
    indice = {x["hora"]: x["od"] for x in horas}
    obs, pred = {h["horas"]: [] for h in HORIZONTES_HORAS}, {h["horas"]: [] for h in HORIZONTES_HORAS}
    for o in [x["hora"] for x in horas if x["hora"] >= corte]:
        nivel = nivel_24h(indice, o)
        if nivel is None:
            continue
        for h in HORIZONTES_HORAS:
            destino = o + timedelta(hours=h["horas"])
            if destino in indice:
                obs[h["horas"]].append(indice[destino])
                pred[h["horas"]].append(nivel + onda_diaria(coef_prueba, destino.hour + 0.5))
    ultima = horas[-1]["hora"]
    nivel = nivel_24h(indice, ultima) or horas[-1]["od"]
    serie = [[(ultima + timedelta(hours=k)).isoformat(), round(nivel + onda_diaria(coef_final, (ultima + timedelta(hours=k)).hour + 0.5), 3)] for k in range(1, HORAS_MAX + 1)]
    return {
        "opciones": HORIZONTES_HORAS,
        "desde": ultima.isoformat(),
        "valor_inicial": round(indice[ultima], 3),
        "nivel_mg_l": round(nivel, 3),
        "serie": serie,
        "unidad": "mg/L",
        "confiabilidad": _confiabilidad(obs, pred),
        "supuestos": (
            "El nivel es el promedio de las últimas 24 horas y se mantiene; encima se repite el ciclo diario ajustado. "
            "A más días, más pesa que el nivel del estanque cambie por causas que el modelo no ve, como la aireación o "
            "la carga de peces."
        ),
    }


# ----------------------------------------------------------------------
# 4) Clase de calidad de agua sobre entradas proyectadas
# ----------------------------------------------------------------------
def proyeccion_calidad(svm, etiquetas, WQ, horas: list[dict], coef_prueba, coef_final, lecturas, corte: datetime) -> dict[str, Any]:
    """El SVM clasifica las entradas proyectadas de cada hora futura.

    Oxigeno: el ciclo diario sobre el nivel de 24 h. Temperatura: la de esa misma
    hora en los ultimos 7 dias. pH: promedio de 24 h. Nitrato: mediana valida de
    las ultimas 24 h.
    """
    indice_od = {x["hora"]: x["od"] for x in horas}
    por_hora: dict[datetime, list] = {}
    for f in lecturas:
        por_hora.setdefault(f["cuando"].replace(minute=0, second=0, microsecond=0), []).append(f)
    horas_lect = sorted(por_hora)

    def entradas(origen: datetime):
        previas = [h for h in horas_lect if origen - timedelta(days=7) < h <= origen]
        ultimas24 = [f for h in previas if h > origen - timedelta(hours=24) for f in por_hora[h]]
        if not ultimas24:
            return None
        temp_hora: dict[int, list] = {}
        for h in previas:
            temp_hora.setdefault(h.hour, []).extend(f["t"] for f in por_hora[h])
        nitratos = [f["no3"] for f in ultimas24]
        return {
            "t": {k: float(np.mean(v)) for k, v in temp_hora.items()},
            "t_media": float(np.mean([f["t"] for f in ultimas24])),
            "ph": float(np.mean([f["ph"] for f in ultimas24])),
            "no3": float(np.median(nitratos)),
            "nivel": nivel_24h(indice_od, origen),
        }

    def clase_real(h: datetime):
        filas = por_hora.get(h)
        if not filas:
            return None
        votos: dict[str, int] = {}
        for f in filas:
            try:
                res = WQ.water_quality_index(f["t"], f["ph"], f["od"], f["no3"])
            except Exception:
                continue
            cls = res.get("classification")
            etiqueta = str(cls.get("label") if isinstance(cls, dict) else cls)
            votos[etiqueta] = votos.get(etiqueta, 0) + 1
        return max(votos, key=votos.get) if votos else None

    def fila_para(e, destino, coef):
        od = (e["nivel"] if e["nivel"] is not None else 0.0) + onda_diaria(coef, destino.hour + 0.5)
        return [e["t"].get(destino.hour, e["t_media"]), e["ph"], max(0.0, od), e["no3"]]

    aciertos: dict[int, list] = {h["horas"]: [] for h in HORIZONTES_HORAS}
    origenes = [h for h in horas_lect if h >= corte and h.hour in (0, 6, 12, 18)]
    filas, destinos = [], []
    for o in origenes:
        e = entradas(o)
        if e is None or e["nivel"] is None:
            continue
        for h in HORIZONTES_HORAS:
            destino = o + timedelta(hours=h["horas"])
            real = clase_real(destino)
            if real is None:
                continue
            filas.append(fila_para(e, destino, coef_prueba))
            destinos.append((h["horas"], real))
    if filas:
        for (hh, real), p in zip(destinos, svm.predict(np.asarray(filas, float))):
            aciertos[hh].append(etiquetas[int(p)] == real)
    confiabilidad = []
    for h in HORIZONTES_HORAS:
        v = aciertos[h["horas"]]
        confiabilidad.append(
            {
                "id": h["id"],
                "nombre": h["nombre"],
                "casos": len(v),
                "acierto": round(float(np.mean(v)), 3) if len(v) >= MINIMO_CASOS else None,
                "comprobable": len(v) >= MINIMO_CASOS,
            }
        )

    serie = []
    entradas_serie = []
    ultima = horas_lect[-1] if horas_lect else None
    e = entradas(ultima) if ultima else None
    if e is not None:
        if e["nivel"] is None:
            e["nivel"] = float(np.mean([f["od"] for f in por_hora[ultima]]))
        futuras = [ultima + timedelta(hours=k) for k in range(1, HORAS_MAX + 1)]
        filas_f = [fila_para(e, d, coef_final) for d in futuras]
        for d, fila, p in zip(futuras, filas_f, svm.predict(np.asarray(filas_f, float))):
            serie.append([d.isoformat(), etiquetas[int(p)]])
            entradas_serie.append([d.isoformat(), round(fila[0], 2), round(fila[2], 2)])
    return {
        "opciones": HORIZONTES_HORAS,
        "desde": ultima.isoformat() if ultima else None,
        "serie": serie,
        "entradas": entradas_serie,
        "entradas_fijas": {"ph": round(e["ph"], 2), "nitrato_mg_l": round(e["no3"], 2)} if e else None,
        "orden_clases": etiquetas,
        "confiabilidad": confiabilidad,
        "supuestos": (
            "El SVM clasifica cada hora futura con entradas proyectadas: oxígeno del ciclo diario sobre el nivel de las "
            "últimas 24 horas, temperatura de esa misma hora en los últimos 7 días, pH promedio y nitrato mediano de las "
            "últimas 24 horas. La confiabilidad compara la clase proyectada con la clase real que tuvo el agua."
        ),
    }
