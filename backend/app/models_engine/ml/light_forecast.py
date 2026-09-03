"""Prevision de luz a doce horas dentro del vivero.

Por que doce horas y no una: se probaron los horizontes de 30 minutos, 1, 2, 3,
6 y 12 horas contra dos referencias honestas, la persistencia (la luz seguira
como esta) y la media historica de esa hora del dia. Hasta las seis horas la
persistencia gana a cualquier modelo, porque la luz cambia despacio y decir
"seguira parecida" acierta mas que aprender nada. A doce horas la persistencia
se derrumba -predice el dia mirando la noche- y ahi si hay algo que aprender.

Sirve para lo que le importa a quien cria: por la noche, saber si manana
temprano habra luz suficiente para que la tilapia vea el alimento.

El modelo se valida fuera de muestra y con reparto temporal, nunca aleatorio:
mezclar el futuro con el pasado en una serie de tiempo infla los resultados. Si
no le gana a las dos referencias, se dice y no se usa para decidir.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

BIN_MINUTOS = 10
PASOS_HORIZONTE = 72  # 72 casillas de 10 min = 12 horas
DESFASES = [0, 1, 2, 3, 6, 12, 18]
MINIMO_MUESTRAS = 150


def _rejilla(lecturas):
    """Lleva lecturas irregulares a casillas fijas de diez minutos.

    El sensor no tiene cadencia estable: alterna tramos de tres minutos con
    otros de diez y deja noches enteras sin registrar. Promediar por casilla
    evita que un mismo desfase signifique cosas distintas segun el tramo.
    """
    cubos = {}
    for fila in lecturas:
        momento = fila.get("fecha_medicion")
        lux = fila.get("iluminancia")
        if not isinstance(momento, datetime) or lux is None:
            continue
        try:
            valores = (
                float(lux),
                float(fila.get("temperatura_ambiente") or 0.0),
                float(fila.get("humedad_ambiente") or 0.0),
            )
        except (TypeError, ValueError):
            continue
        casilla = momento.replace(
            minute=(momento.minute // BIN_MINUTOS) * BIN_MINUTOS, second=0, microsecond=0
        )
        cubos.setdefault(casilla, []).append(valores)
    return {
        casilla: tuple(sum(v[j] for v in vals) / len(vals) for j in range(3))
        for casilla, vals in cubos.items()
    }


def _fila_de(grid, casilla, previas):
    lux, temperatura, humedad = grid[casilla]
    hora = casilla.hour + casilla.minute / 60.0
    fila = [grid[p][0] for p in previas]
    fila.append(sum(grid[p][0] for p in previas[:4]) / 4.0)
    fila.extend(
        [
            math.sin(2 * math.pi * hora / 24.0),
            math.cos(2 * math.pi * hora / 24.0),
            temperatura,
            humedad,
        ]
    )
    return fila, hora, lux


def _muestras(grid):
    """Arma las filas de entrenamiento y descarta las que tengan huecos."""
    X, y, horas = [], [], []
    for casilla in sorted(grid):
        previas = [casilla - timedelta(minutes=BIN_MINUTOS * d) for d in DESFASES]
        objetivo = casilla + timedelta(minutes=BIN_MINUTOS * PASOS_HORIZONTE)
        if objetivo not in grid or any(p not in grid for p in previas):
            continue
        fila, hora, _ = _fila_de(grid, casilla, previas)
        X.append(fila)
        y.append(grid[objetivo][0])
        horas.append(hora)
    return X, y, horas


def _metricas(observado, predicho):
    n = len(observado)
    media = sum(observado) / n
    mae = sum(abs(o - p) for o, p in zip(observado, predicho)) / n
    residuo = sum((o - p) ** 2 for o, p in zip(observado, predicho))
    total = sum((o - media) ** 2 for o in observado)
    return mae, (1.0 - residuo / total if total else 0.0)


def train_light_forecast_model(lecturas, seed=20260903):
    """Entrena la prevision y la contrasta con persistencia y media horaria."""
    try:
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVR
    except ImportError:
        return None

    grid = _rejilla(lecturas)
    X, y, horas = _muestras(grid)
    if len(X) < MINIMO_MUESTRAS:
        return None

    n = len(X)
    corte_train = int(n * 0.70)
    corte_val = int(n * 0.85)
    Xtr, ytr = X[:corte_train], y[:corte_train]
    Xte, yte = X[corte_val:], y[corte_val:]
    if len(Xte) < 25:
        return None

    # Referencia 1: la luz sigue como esta ahora.
    persistencia = [fila[0] for fila in Xte]
    mae_persistencia, r2_persistencia = _metricas(yte, persistencia)

    # Referencia 2: lo que suele haber a esa hora, aprendido solo del tramo de
    # entrenamiento para no mirar el futuro.
    por_hora = {}
    for i in range(corte_train):
        por_hora.setdefault(int(horas[i]), []).append(y[i])
    medias = {h: sum(v) / len(v) for h, v in por_hora.items()}
    global_media = sum(ytr) / len(ytr)
    climatologia = [medias.get(int(horas[corte_val + i]), global_media) for i in range(len(yte))]
    mae_clima, r2_clima = _metricas(yte, climatologia)

    modelo = make_pipeline(
        StandardScaler(), SVR(kernel="rbf", C=200.0, gamma="scale", epsilon=3.0)
    )
    modelo.fit(Xtr, ytr)
    predicho = [float(v) for v in modelo.predict(Xte)]
    mae_modelo, r2_modelo = _metricas(yte, predicho)

    gana = mae_modelo < mae_persistencia and mae_modelo < mae_clima
    if gana:
        veredicto = (
            "Le gana a las dos referencias: se equivoca en {:.0f} lux frente a {:.0f} de la "
            "persistencia y {:.0f} de la media horaria.".format(
                mae_modelo, mae_persistencia, mae_clima
            )
        )
    else:
        veredicto = (
            "No le gana a las referencias ({:.0f} lux frente a {:.0f}). No conviene usarlo "
            "para decidir.".format(mae_modelo, min(mae_persistencia, mae_clima))
        )

    return {
        "modelo": modelo,
        "horizon_hours": PASOS_HORIZONTE * BIN_MINUTOS / 60.0,
        "sample_size": n,
        "train_size": corte_train,
        "test_size": len(Xte),
        "seed": seed,
        "features": (
            "lux actual y de hace 10, 20, 30, 60, 120 y 180 min; media de la ultima media "
            "hora; hora del dia en seno y coseno; temperatura y humedad ambiente"
        ),
        "metrics": {"test_mae_lux": round(mae_modelo, 1), "test_r2": round(r2_modelo, 4)},
        "baselines": {
            "persistencia": {
                "test_mae_lux": round(mae_persistencia, 1),
                "test_r2": round(r2_persistencia, 4),
            },
            "media_horaria": {
                "test_mae_lux": round(mae_clima, 1),
                "test_r2": round(r2_clima, 4),
            },
        },
        "beats_baselines": gana,
        "verdict": veredicto,
        "note": (
            "Reparto temporal 70/15/15 sin mezclar futuro con pasado. El horizonte de doce "
            "horas se eligio midiendo: por debajo de seis, la persistencia gana a cualquier "
            "modelo."
        ),
    }


def predict_next_light(modelo_entrenado, lecturas):
    """Aplica el modelo a la ultima ventana disponible."""
    if not modelo_entrenado or "modelo" not in modelo_entrenado:
        return None
    grid = _rejilla(lecturas)
    if not grid:
        return None
    ultima = max(grid)
    previas = [ultima - timedelta(minutes=BIN_MINUTOS * d) for d in DESFASES]
    if any(p not in grid for p in previas):
        return None
    fila, _, lux = _fila_de(grid, ultima, previas)
    try:
        valor = float(modelo_entrenado["modelo"].predict([fila])[0])
    except Exception:
        return None
    return {
        "predicted_lux": round(max(0.0, valor), 1),
        "from_at": ultima.isoformat(),
        "for_at": (ultima + timedelta(minutes=BIN_MINUTOS * PASOS_HORIZONTE)).isoformat(),
        "current_lux": round(lux, 1),
    }
