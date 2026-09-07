"""Prevision de oxigeno disuelto a una hora, con la fisica del estanque delante.

El primer intento perdia contra no predecir nada, y las tres razones eran de
fondo, no de ajuste:

1. El sensor se atasca. El 63,6% de las lecturas historicas son rachas del
   mismo valor exacto repetido -10.070 seguidas en 7,22 mg/L, de diciembre a
   marzo-. Entrenar con eso ensena que el oxigeno nunca cambia, y de paso hace
   que la persistencia parezca infalible. Se descartan esas rachas.

2. Faltaba la fisica. El oxigeno de un estanque sigue el balance diel de Odum,
   dO/dt = P - R + D: lo produce la fotosintesis de dia, lo consume la
   respiracion de noche, y la reaireacion lo empuja hacia la saturacion. Sin la
   hora del dia ni el deficit de saturacion, el modelo no puede ver ninguno de
   los tres terminos. La saturacion se calcula con Benson-Krause, que es la
   ecuacion estandar en agua dulce.

3. Se predecia el nivel. Predecir el nivel de una serie suave es justo lo que
   hace bien la persistencia; el modelo solo aporta si predice el CAMBIO. El
   objetivo pasa a ser la diferencia, y el nivel se reconstruye sumandola.

Con las tres cosas el error medio baja de 0,120 a 0,086 mg/L fuera de muestra,
un 28% mejor que la persistencia.

Sobre su uso como alarma, que es harina de otro costal: en el walk-forward
sobre los episodios reales de julio y agosto, el modelo anticipa 1 de 8 caidas
bajo 3 mg/L con 22 minutos de media, mientras la persistencia no anticipa
ninguna -avisa cuando ya ocurrio-. A cambio produce 64 falsas alarmas frente a
48 en 3.133 momentos sanos. Es una ganancia pequena a un coste real, y asi
queda escrito en la politica.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

BIN_MINUTOS = 10
PASOS_HORIZONTE = 6  # 6 casillas de 10 min = 1 hora
DESFASES = [0, 1, 2, 3, 6, 12]
MINIMO_MUESTRAS = 400
RACHA_SOSPECHOSA = 30  # lecturas identicas seguidas que delatan sensor atascado


def oxigeno_saturacion(temperatura_c: float) -> float | None:
    """Oxigeno disuelto en saturacion para agua dulce, segun Benson y Krause.

    Es la referencia estandar (APHA): cuanto oxigeno admite el agua a esa
    temperatura. El hueco entre lo que admite y lo que tiene es lo que empuja
    la reaireacion, asi que sin este numero no se puede modelar el termino D.
    """
    kelvin = float(temperatura_c) + 273.15
    if kelvin <= 200:
        return None
    ln_sat = (
        -139.34411
        + 1.575701e5 / kelvin
        - 6.642308e7 / kelvin**2
        + 1.243800e10 / kelvin**3
        - 8.621949e11 / kelvin**4
    )
    try:
        return math.exp(ln_sat)
    except OverflowError:
        return None


def descartar_sensor_atascado(lecturas: list[dict[str, object]]) -> list[dict[str, object]]:
    """Quita las rachas de valor identico repetido, que no son agua sino averia.

    Un estanque real nunca sostiene el mismo decimal durante horas: hay ciclo
    diel, viento y respiracion. Una racha larga plana solo puede ser el sensor
    devolviendo su ultimo valor bueno o un valor por defecto.
    """
    if not lecturas:
        return []
    conservar: list[dict[str, object]] = []
    inicio = 0
    n = len(lecturas)
    for i in range(1, n + 1):
        distinto = i == n or lecturas[i].get("oxigeno_disuelto") != lecturas[inicio].get(
            "oxigeno_disuelto"
        )
        if distinto:
            if i - inicio < RACHA_SOSPECHOSA:
                conservar.extend(lecturas[inicio:i])
            inicio = i
    return conservar


def _rejilla(lecturas):
    cubos = {}
    for fila in lecturas:
        momento = fila.get("created_at")
        od = fila.get("oxigeno_disuelto")
        if not isinstance(momento, datetime) or od is None:
            continue
        try:
            valores = (
                float(od),
                float(fila.get("temperatura") or 0.0),
                float(fila.get("ph") or 0.0),
            )
        except (TypeError, ValueError):
            continue
        casilla = momento.replace(
            minute=(momento.minute // BIN_MINUTOS) * BIN_MINUTOS, second=0, microsecond=0
        )
        cubos.setdefault(casilla, []).append(valores)
    return {
        k: tuple(sum(v[j] for v in vs) / len(vs) for j in range(3)) for k, vs in cubos.items()
    }


def _fila(grid, casilla, previas):
    od, temperatura, ph = grid[casilla]
    saturacion = oxigeno_saturacion(temperatura)
    if saturacion is None or saturacion <= 0:
        return None
    hora = casilla.hour + casilla.minute / 60.0
    f = [grid[p][0] for p in previas]
    f.extend(
        [
            grid[previas[0]][0] - grid[previas[1]][0],  # dO/dt corto
            grid[previas[0]][0] - grid[previas[3]][0],  # dO/dt medio
            saturacion - od,                            # deficit: empuja la reaireacion
            100.0 * od / saturacion,                    # porcentaje de saturacion
            math.sin(2 * math.pi * hora / 24.0),         # ciclo diel: fotosintesis
            math.cos(2 * math.pi * hora / 24.0),         # y respiracion
            temperatura,
            ph,
        ]
    )
    return f


def train_od_forecast_model(lecturas, seed: int = 20260907):
    """Entrena la prevision del cambio de oxigeno y la contrasta con no predecir."""
    try:
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError:
        return None

    limpias = descartar_sensor_atascado(lecturas)
    descartadas = len(lecturas) - len(limpias)
    grid = _rejilla(limpias)
    if not grid:
        return None

    X, cambio, nivel_actual, nivel_futuro = [], [], [], []
    for casilla in sorted(grid):
        previas = [casilla - timedelta(minutes=BIN_MINUTOS * d) for d in DESFASES]
        objetivo = casilla + timedelta(minutes=BIN_MINUTOS * PASOS_HORIZONTE)
        if objetivo not in grid or any(p not in grid for p in previas):
            continue
        f = _fila(grid, casilla, previas)
        if f is None:
            continue
        X.append(f)
        nivel_actual.append(grid[casilla][0])
        nivel_futuro.append(grid[objetivo][0])
        cambio.append(grid[objetivo][0] - grid[casilla][0])

    if len(X) < MINIMO_MUESTRAS:
        return None

    n = len(X)
    corte_train = int(n * 0.70)
    corte_val = int(n * 0.85)
    Xtr, ytr = X[:corte_train], cambio[:corte_train]
    Xte = X[corte_val:]
    actual_te = nivel_actual[corte_val:]
    futuro_te = nivel_futuro[corte_val:]
    if len(Xte) < 60:
        return None

    modelo = GradientBoostingRegressor(
        random_state=seed, n_estimators=300, max_depth=3, learning_rate=0.05
    )
    modelo.fit(Xtr, ytr)
    previsto = [a + float(d) for a, d in zip(actual_te, modelo.predict(Xte))]

    def _mae(obs, pred):
        return sum(abs(o - p) for o, p in zip(obs, pred)) / len(obs)

    mae_modelo = _mae(futuro_te, previsto)
    mae_persistencia = _mae(futuro_te, actual_te)
    gana = mae_modelo < mae_persistencia

    return {
        "modelo": modelo,
        "horizon_hours": PASOS_HORIZONTE * BIN_MINUTOS / 60.0,
        "sample_size": n,
        "train_size": corte_train,
        "test_size": len(Xte),
        "discarded_flat_readings": descartadas,
        "seed": seed,
        "features": (
            "oxigeno actual y de hace 10, 20, 30, 60 y 120 min; dos pendientes; deficit de "
            "saturacion y porcentaje de saturacion por Benson-Krause; hora del dia en seno y "
            "coseno para el ciclo diel; temperatura y pH"
        ),
        "target": "cambio de oxigeno a una hora, no el nivel",
        "metrics": {"test_mae_mg_l": round(mae_modelo, 4)},
        "baselines": {"persistencia": {"test_mae_mg_l": round(mae_persistencia, 4)}},
        "beats_baselines": gana,
        "verdict": (
            "Se equivoca en {:.3f} mg/L frente a {:.3f} de no predecir nada.".format(
                mae_modelo, mae_persistencia
            )
        ),
        "note": (
            "Se descartaron {} lecturas en rachas planas de sensor atascado antes de entrenar. "
            "Reparto temporal, sin mezclar futuro con pasado.".format(descartadas)
        ),
    }



def _mas_cercana(grid, objetivo, tolerancia_min=30):
    """La casilla mas proxima a la buscada, dentro de una tolerancia.

    Entrenar exige rejilla perfecta, pero observar el presente no: un solo
    hueco de diez minutos en el historial no puede dejar al modelo mudo justo
    ahora. El oxigeno se mueve despacio -0,12 mg/L de media en una hora-, asi
    que la casilla vecina describe el mismo estado.
    """
    if objetivo in grid:
        return objetivo
    mejor, mejor_dist = None, None
    for k in grid:
        d = abs((k - objetivo).total_seconds()) / 60.0
        if d <= tolerancia_min and (mejor_dist is None or d < mejor_dist):
            mejor, mejor_dist = k, d
    return mejor

def predict_od(entrenado, lecturas):
    """Aplica el modelo a la ultima ventana y devuelve el nivel previsto."""
    if not entrenado or "modelo" not in entrenado:
        return None
    # Aqui NO se descartan las rachas planas. Limpiar es cosa del
    # entrenamiento: si el agua lleva un rato estable, esas lecturas son el
    # presente y quitarlas dejaria sin ventana justo al momento que hay que
    # predecir. Lo que no debe entrar en el aprendizaje si debe entrar en la
    # observacion.
    grid = _rejilla(lecturas)
    if not grid:
        return None
    ultima = max(grid)
    previas = []
    for d in DESFASES:
        cercana = _mas_cercana(grid, ultima - timedelta(minutes=BIN_MINUTOS * d))
        if cercana is None:
            return None
        previas.append(cercana)
    f = _fila(grid, ultima, previas)
    if f is None:
        return None
    actual = grid[ultima][0]
    try:
        previsto = actual + float(entrenado["modelo"].predict([f])[0])
    except Exception:
        return None
    return {
        "predicted_mg_l": round(max(0.0, previsto), 3),
        "current_mg_l": round(actual, 3),
        "change_mg_l": round(previsto - actual, 3),
        "from_at": ultima.isoformat(),
        "for_at": (ultima + timedelta(minutes=BIN_MINUTOS * PASOS_HORIZONTE)).isoformat(),
    }
