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


UMBRAL_ALIMENTACION_LUX = 30.0


def train_light_adequacy_classifier(lecturas, seed=20260903):
    """Clasifica si dentro de doce horas habra luz para que los peces coman.

    La etiqueta no es "los peces comieron" -eso nadie lo anota- sino algo que
    el propio sensor mide: si en ese momento futuro la iluminancia llega o no
    al minimo con el que la tilapia distingue el alimento. Predecir el futuro a
    partir del pasado con una etiqueta medida no tiene nada de circular.

    Treinta lux es el umbral: por debajo, la tilapia -que se alimenta por
    vista- deja de detectar el pienso y la toma se desaprovecha.

    Se contrasta contra tres referencias: que la luz siga como esta, decir
    siempre la clase mayoritaria, y mirar solo la hora del dia.
    """
    try:
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVC
    except ImportError:
        return None

    grid = _rejilla(lecturas)
    X, y_lux, horas = _muestras(grid)
    if len(X) < MINIMO_MUESTRAS:
        return None
    y = [1 if valor >= UMBRAL_ALIMENTACION_LUX else 0 for valor in y_lux]

    n = len(X)
    corte_train = int(n * 0.70)
    corte_val = int(n * 0.85)
    Xtr, ytr = X[:corte_train], y[:corte_train]
    Xte, yte = X[corte_val:], y[corte_val:]
    if len(Xte) < 25 or len(set(ytr)) < 2:
        return None

    def _f1(observado, predicho):
        tp = sum(1 for o, p in zip(observado, predicho) if o == 1 and p == 1)
        fp = sum(1 for o, p in zip(observado, predicho) if o == 0 and p == 1)
        fn = sum(1 for o, p in zip(observado, predicho) if o == 1 and p == 0)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        acierto = sum(1 for o, p in zip(observado, predicho) if o == p) / len(observado)
        return round(f1, 4), round(acierto, 4)

    persistencia = [1 if fila[0] >= UMBRAL_ALIMENTACION_LUX else 0 for fila in Xte]
    mayoritaria_clase = 1 if sum(ytr) * 2 >= len(ytr) else 0
    mayoritaria = [mayoritaria_clase] * len(yte)
    por_hora = {}
    for i in range(corte_train):
        por_hora.setdefault(int(horas[i]), []).append(y[i])
    regla = {h: (1 if sum(v) * 2 >= len(v) else 0) for h, v in por_hora.items()}
    solo_hora = [regla.get(int(horas[corte_val + i]), mayoritaria_clase) for i in range(len(yte))]

    clf = make_pipeline(
        StandardScaler(),
        SVC(kernel="rbf", C=10.0, gamma="scale", class_weight="balanced", probability=True,
            random_state=seed),
    )
    clf.fit(Xtr, ytr)
    pred = [int(v) for v in clf.predict(Xte)]

    f1_modelo, ac_modelo = _f1(yte, pred)
    referencias = {
        "persistencia": dict(zip(("test_f1", "test_accuracy"), _f1(yte, persistencia))),
        "clase_mayoritaria": dict(zip(("test_f1", "test_accuracy"), _f1(yte, mayoritaria))),
        "solo_la_hora": dict(zip(("test_f1", "test_accuracy"), _f1(yte, solo_hora))),
    }
    gana = all(f1_modelo > ref["test_f1"] for ref in referencias.values())

    return {
        "modelo": clf,
        "threshold_lux": UMBRAL_ALIMENTACION_LUX,
        "horizon_hours": PASOS_HORIZONTE * BIN_MINUTOS / 60.0,
        "sample_size": n,
        "train_size": corte_train,
        "test_size": len(Xte),
        "positive_rate": round(sum(y) / len(y), 4),
        "metrics": {"test_f1": f1_modelo, "test_accuracy": ac_modelo},
        "baselines": referencias,
        "beats_baselines": gana,
        "verdict": (
            "Acierta el {:.0f}% con F1 {:.3f}, frente a {:.3f} de la persistencia y {:.3f} "
            "de mirar solo la hora.".format(
                100 * ac_modelo, f1_modelo,
                referencias["persistencia"]["test_f1"],
                referencias["solo_la_hora"]["test_f1"],
            )
            if gana
            else "No mejora a las referencias; no conviene usarlo para decidir."
        ),
        "note": (
            "Etiqueta medida por el propio sensor: si la iluminancia de dentro de doce horas "
            "llega o no a {:.0f} lux, el minimo con el que la tilapia ve el alimento. Reparto "
            "temporal, sin mezclar futuro con pasado.".format(UMBRAL_ALIMENTACION_LUX)
        ),
    }


def predict_light_adequacy(entrenado, lecturas):
    """Dice si la proxima toma de dentro de doce horas tendra luz suficiente."""
    if not entrenado or "modelo" not in entrenado:
        return None
    grid = _rejilla(lecturas)
    if not grid:
        return None
    ultima = max(grid)
    previas = [ultima - timedelta(minutes=BIN_MINUTOS * d) for d in DESFASES]
    if any(p not in grid for p in previas):
        return None
    fila, _, lux = _fila_de(grid, ultima, previas)
    modelo = entrenado["modelo"]
    try:
        clase = int(modelo.predict([fila])[0])
        try:
            confianza = float(max(modelo.predict_proba([fila])[0]))
        except Exception:
            confianza = None
    except Exception:
        return None
    momento = ultima + timedelta(minutes=BIN_MINUTOS * PASOS_HORIZONTE)
    return {
        "suficiente": bool(clase),
        "confianza": round(confianza, 3) if confianza is not None else None,
        "para": momento.isoformat(),
        "desde": ultima.isoformat(),
        "lux_actual": round(lux, 1),
        "umbral_lux": UMBRAL_ALIMENTACION_LUX,
        "lectura": (
            "Dentro de doce horas habra luz suficiente para alimentar."
            if clase
            else "Dentro de doce horas no habra luz suficiente: conviene mover esa toma."
        ),
    }
