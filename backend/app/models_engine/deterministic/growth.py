from __future__ import annotations

import math
import random
from dataclasses import dataclass


def _positive(name: str, value: float) -> float:
    numeric = float(value)
    if numeric <= 0:
        raise ValueError(f"{name} must be positive")
    return numeric


def _non_negative(name: str, value: float) -> float:
    numeric = float(value)
    if numeric < 0:
        raise ValueError(f"{name} must be non-negative")
    return numeric


def _fraction(name: str, value: float) -> float:
    numeric = float(value)
    if numeric < 0 or numeric > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric


def temperature_factor_yi(
    temperature_c: float,
    t_min_c: float,
    t_opti_c: float,
    t_max_c: float,
) -> float:
    temp = float(temperature_c)
    t_min = float(t_min_c)
    t_opti = float(t_opti_c)
    t_max = float(t_max_c)
    if not t_min < t_opti < t_max:
        raise ValueError("temperature bounds must satisfy t_min < t_opti < t_max")
    if temp <= t_min or temp >= t_max:
        return 0.0
    if temp < t_opti:
        exponent = -4.6 * (((t_opti - temp) / (t_opti - t_min)) ** 4)
    else:
        exponent = -4.6 * (((temp - t_opti) / (t_max - t_opti)) ** 4)
    return max(0.0, min(1.0, math.exp(exponent)))


def catabolism_yi(
    temperature_c: float,
    t_min_c: float,
    k_min: float,
    s: float,
) -> float:
    return _non_negative("k_min", k_min) * math.exp(float(s) * (float(temperature_c) - float(t_min_c)))


def oxygen_factor_yi(
    dissolved_oxygen_mg_l: float,
    do_min_mg_l: float,
    do_crit_mg_l: float,
) -> float:
    do_value = float(dissolved_oxygen_mg_l)
    do_min = float(do_min_mg_l)
    do_crit = float(do_crit_mg_l)
    if do_min >= do_crit:
        raise ValueError("do_min_mg_l must be lower than do_crit_mg_l")
    if do_value < do_min:
        return 0.0
    if do_value > do_crit:
        return 1.0
    return max(0.0, min(1.0, (do_value - do_min) / (do_crit - do_min)))


def yi_growth_rate(
    temperature_c: float,
    dissolved_oxygen_mg_l: float,
    fish_weight_g: float,
    t_min_c: float,
    t_opti_c: float,
    t_max_c: float,
    do_min_mg_l: float,
    do_crit_mg_l: float,
    k_min: float,
    s: float,
    kappa: float,
    phi: float,
    h: float,
    feeding_level: float,
    m: float,
    n: float,
) -> dict[str, float]:
    weight = _positive("fish_weight_g", fish_weight_g)
    tau = temperature_factor_yi(temperature_c, t_min_c, t_opti_c, t_max_c)
    delta = oxygen_factor_yi(dissolved_oxygen_mg_l, do_min_mg_l, do_crit_mg_l)
    catabolism = catabolism_yi(temperature_c, t_min_c, k_min, s)
    kappa_value = _fraction("kappa", kappa)
    phi_value = _fraction("phi", phi)
    feeding = _fraction("feeding_level", feeding_level)
    anabolic = 0.2919 * tau * kappa_value * delta * phi_value * float(h) * feeding * (weight ** float(m))
    catabolic = catabolism * (weight ** float(n))
    return {
        "fish_growth_rate_g_day": anabolic - catabolic,
        "tau": tau,
        "delta": delta,
        "catabolism_coefficient": catabolism,
        "anabolic_term": anabolic,
        "catabolic_term": catabolic,
    }


@dataclass(frozen=True)
class SoderbergEquation:
    species: str
    intercept: float
    slope: float
    min_temp_c: float
    max_temp_c: float
    r2: float
    source: str

    def applies_to(self, species: str, temperature_c: float) -> bool:
        return (
            self.species == normalize_species(species)
            and self.min_temp_c <= temperature_c <= self.max_temp_c
        )


def normalize_species(species: str) -> str:
    return species.strip().lower().replace("_", " ")


SODERBERG_EQUATIONS = [
    SoderbergEquation("nile tilapia", -1.6707, 0.09682, 21.0, 30.0, 0.95, "combined"),
    SoderbergEquation("nile tilapia", -1.6623, 0.097021, 21.0, 30.0, 0.95, "2002"),
    SoderbergEquation("nile tilapia", -1.7147, 0.097794, 21.0, 30.0, 0.95, "2005"),
    SoderbergEquation("blue tilapia", -0.853, 0.048, 20.0, 30.0, 0.99, "blue tilapia"),
    SoderbergEquation("brook trout", -0.348, 0.0944, 5.5, 12.2, 0.99, "hatchery 5.5-12.2"),
    SoderbergEquation("brook trout", 0.155, 0.0355, 4.0, 19.0, 0.637, "hatchery 4-19"),
    SoderbergEquation("brook trout", 0.006, 0.0455, 7.0, 19.0, 0.792, "hatchery 7-19"),
    SoderbergEquation("brook trout", -0.068, 0.0578, 7.0, 16.0, 0.882, "hatchery 7-16"),
    SoderbergEquation("rainbow trout", -0.040, 0.0505, 4.0, 19.0, 0.886, "hatchery 4-19"),
    SoderbergEquation("rainbow trout", 0.043, 0.0450, 7.0, 19.0, 0.801, "hatchery 7-19"),
    SoderbergEquation("rainbow trout", -0.167, 0.066, 7.0, 16.0, 0.971, "hatchery 7-16"),
    SoderbergEquation("lake trout", 0.176, 0.0426, 4.0, 16.0, 0.858, "hatchery 4-16"),
    SoderbergEquation("lake trout", -0.0622, 0.0588, 4.0, 13.0, 0.979, "hatchery 4-13"),
    SoderbergEquation("steelhead", 0.0329, 0.0294, 4.0, 19.0, 0.856, "hatchery 4-19"),
    SoderbergEquation("steelhead", -0.0407, 0.0386, 7.0, 16.0, 0.963, "hatchery 7-16"),
    SoderbergEquation("atlantic salmon", 0.0043, 0.0306, 4.0, 19.0, 0.926, "hatchery 4-19"),
    SoderbergEquation("channel catfish", -0.612, 0.0298, 24.0, 30.0, 0.825, "catfish 24-30"),
    SoderbergEquation("channel catfish", 0.195, 0.0463, 24.0, 28.0, 0.991, "catfish 24-28"),
]


def soderberg_delta_l(
    temperature_c: float,
    species: str = "nile tilapia",
) -> dict[str, float | str]:
    temp = float(temperature_c)
    normalized = normalize_species(species)
    if normalized == "tilapia":
        normalized = "nile tilapia"
    candidates = [
        equation
        for equation in SODERBERG_EQUATIONS
        if equation.applies_to(normalized, temp)
    ]
    if not candidates:
        raise ValueError("no Soderberg equation covers species and temperature")
    selected = max(candidates, key=lambda item: item.r2)
    delta_l = selected.intercept + selected.slope * temp
    return {
        "daily_length_gain_mm_day": max(0.0, delta_l),
        "equation_intercept": selected.intercept,
        "equation_slope": selected.slope,
        "equation_r2": selected.r2,
        "equation_source": selected.source,
        "species": selected.species,
    }


def nile_tilapia_weight_from_length(length_mm: float) -> float:
    length = _positive("length_mm", length_mm)
    return 1.861e-8 * length**3


# --------------------------------------------------------------------------
# Modelo peso-longitud entrenado
#
# Con biometria_detalles hay una medicion por pez, no una por muestreo: eso
# da suficientes puntos para entrenar y validar de verdad. Se compara contra
# dos referencias para no confundir "ajusta" con "sirve":
#
#   media       predecir siempre el peso medio. Si el modelo no le gana, sobra.
#   isometrico  la ley cubica clasica W = a*L^3, sin aprender el exponente.
# --------------------------------------------------------------------------

def _fit_allometry(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Ajusta W = a*L^b por minimos cuadrados sobre los logaritmos."""
    if len(points) < 2:
        return None
    log_l = [math.log(l) for l, _ in points]
    log_w = [math.log(w) for _, w in points]
    mean_l = sum(log_l) / len(log_l)
    mean_w = sum(log_w) / len(log_w)
    denom = sum((v - mean_l) ** 2 for v in log_l)
    if denom == 0:
        return None
    b = sum((l - mean_l) * (w - mean_w) for l, w in zip(log_l, log_w, strict=True)) / denom
    a = math.exp(mean_w - b * mean_l)
    return a, b


def _fit_isometric(points: list[tuple[float, float]]) -> float:
    """Ley cubica: solo se ajusta el coeficiente, el exponente se fija en 3."""
    num = sum(w * (l ** 3) for l, w in points)
    den = sum((l ** 3) ** 2 for l in (l for l, _ in points))
    return num / den if den else 0.0


def _scores(observed: list[float], predicted: list[float]) -> dict[str, float]:
    n = len(observed)
    if n == 0:
        return {"r2": 0.0, "mae": 0.0, "rmse": 0.0}
    mean = sum(observed) / n
    ss_res = sum((o - p) ** 2 for o, p in zip(observed, predicted, strict=True))
    ss_tot = sum((o - mean) ** 2 for o in observed)
    return {
        "r2": 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot,
        "mae": sum(abs(o - p) for o, p in zip(observed, predicted, strict=True)) / n,
        "rmse": math.sqrt(ss_res / n),
    }


def train_weight_length_model(
    samples: list[dict[str, object]],
    *,
    test_fraction: float = 0.25,
    seed: int = 20260902,
) -> dict[str, object] | None:
    """Entrena y valida W = a*L^b sobre peces medidos uno a uno."""
    points: list[tuple[float, float]] = []
    for sample in samples:
        length = sample.get("length_mm")
        weight = sample.get("weight_g")
        if length is None or weight is None:
            continue
        l, w = float(length), float(weight)
        if l > 0 and w > 0:
            points.append((l, w))

    if len(points) < 12 or len({l for l, _ in points}) < 4:
        return None

    # Reparto reproducible: mismo seed, mismo reparto, resultados comparables
    # entre ejecuciones.
    orden = list(range(len(points)))
    random.Random(seed).shuffle(orden)
    corte = max(3, int(round(len(points) * test_fraction)))
    idx_test = set(orden[:corte])
    train = [pt for i, pt in enumerate(points) if i not in idx_test]
    test = [pt for i, pt in enumerate(points) if i in idx_test]
    if len(train) < 8 or len(test) < 3:
        return None

    ajuste = _fit_allometry(train)
    if ajuste is None:
        return None
    a, b = ajuste

    obs = [w for _, w in test]
    pred_modelo = [a * (l ** b) for l, _ in test]
    media_train = sum(w for _, w in train) / len(train)
    pred_media = [media_train] * len(test)
    a_iso = _fit_isometric(train)
    pred_iso = [a_iso * (l ** 3) for l, _ in test]

    m_modelo = _scores(obs, pred_modelo)
    m_media = _scores(obs, pred_media)
    m_iso = _scores(obs, pred_iso)

    gana_media = m_modelo["mae"] < m_media["mae"]
    gana_iso = m_modelo["mae"] < m_iso["mae"]

    return {
        "coefficient": a,
        "exponent": b,
        "sample_size": len(points),
        "train_size": len(train),
        "test_size": len(test),
        "seed": seed,
        "metrics": {
            "test_r2": round(m_modelo["r2"], 4),
            "test_mae_g": round(m_modelo["mae"], 4),
            "test_rmse_g": round(m_modelo["rmse"], 4),
        },
        "baselines": {
            "media": {
                "test_mae_g": round(m_media["mae"], 4),
                "test_r2": round(m_media["r2"], 4),
            },
            "isometrico_cubico": {
                "test_mae_g": round(m_iso["mae"], 4),
                "test_r2": round(m_iso["r2"], 4),
                "coefficient": a_iso,
            },
        },
        "beats_mean_baseline": gana_media,
        "beats_isometric_baseline": gana_iso,
        "usable": gana_media,
        "verdict": (
            "Le gana a predecir siempre el peso medio y tambien a la ley cubica clasica."
            if gana_media and gana_iso
            else "Le gana al peso medio, pero no a la ley cubica clasica."
            if gana_media
            else "No le gana a predecir siempre el peso medio: no aporta."
        ),
        "formula": f"W = {a:.6g} * L^{b:.4f}",
        "note": (
            "Exponente cercano a 3 indica crecimiento isometrico; por debajo, "
            "los peces se alargan mas de lo que engordan."
        ),
    }


def fit_local_weight_length(
    samples: list[dict[str, object]],
) -> dict[str, float | int] | None:
    """Fit W = aL^b with real biometric detail rows in millimetres and grams."""
    points: list[tuple[float, float]] = []
    for sample in samples:
        length = sample.get("length_mm")
        weight = sample.get("weight_g")
        if length is None or weight is None:
            continue
        numeric_length = float(length)
        numeric_weight = float(weight)
        if numeric_length > 0 and numeric_weight > 0:
            points.append((numeric_length, numeric_weight))

    if len(points) < 8 or len({length for length, _ in points}) < 2:
        return None

    log_lengths = [math.log(length) for length, _ in points]
    log_weights = [math.log(weight) for _, weight in points]
    mean_length = sum(log_lengths) / len(log_lengths)
    mean_weight = sum(log_weights) / len(log_weights)
    denominator = sum((value - mean_length) ** 2 for value in log_lengths)
    if denominator == 0:
        return None
    exponent = sum(
        (log_length - mean_length) * (log_weight - mean_weight)
        for log_length, log_weight in zip(log_lengths, log_weights, strict=True)
    ) / denominator
    coefficient = math.exp(mean_weight - exponent * mean_length)
    predictions = [coefficient * length**exponent for length, _ in points]
    observed_mean = sum(weight for _, weight in points) / len(points)
    residual_sum = sum(
        (weight - predicted) ** 2
        for (_, weight), predicted in zip(points, predictions, strict=True)
    )
    total_sum = sum((weight - observed_mean) ** 2 for _, weight in points)
    r2 = 1.0 if total_sum == 0 else 1.0 - residual_sum / total_sum
    return {
        "coefficient": coefficient,
        "exponent": exponent,
        "r2": r2,
        "sample_count": len(points),
    }


def local_weight_from_length(
    length_mm: float,
    weight_length_model: dict[str, float | int],
) -> float:
    length = _positive("length_mm", length_mm)
    return float(weight_length_model["coefficient"]) * length ** float(
        weight_length_model["exponent"]
    )



# --------------------------------------------------------------------------
# Factores limitantes del crecimiento
#
# La temperatura marca el potencial. El oxigeno y el pH solo pueden restarle.
# Los umbrales coinciden con la tabla parametro_bandas del propio sistema.
# --------------------------------------------------------------------------

#: Por debajo de esto la tilapia no gana peso: toda la energia se va en respirar.
OXYGEN_NO_GROWTH_MG_L = 2.0
#: Desde aqui el oxigeno deja de limitar. Coincide con el umbral critico de 4
#: mg/L de parametro_bandas mas un margen de seguridad.
OXYGEN_FULL_GROWTH_MG_L = 5.0

#: Banda optima de pH, identica a la de parametro_bandas.
PH_OPTIMAL_LOW, PH_OPTIMAL_HIGH = 6.5, 8.5
#: Fuera de estos extremos se considera que no hay crecimiento.
PH_LETHAL_LOW, PH_LETHAL_HIGH = 5.0, 10.0


def oxygen_growth_factor(dissolved_oxygen_mg_l: float | None) -> tuple[float, str]:
    """Cuanto del crecimiento potencial permite el oxigeno disponible."""
    if dissolved_oxygen_mg_l is None:
        return 1.0, "Sin lectura de oxigeno: no se aplica limitacion."
    od = float(dissolved_oxygen_mg_l)
    if od <= OXYGEN_NO_GROWTH_MG_L:
        return 0.0, f"Oxigeno en {od:.2f} mg/L: por debajo de {OXYGEN_NO_GROWTH_MG_L:.0f} el pez no crece."
    if od >= OXYGEN_FULL_GROWTH_MG_L:
        return 1.0, f"Oxigeno en {od:.2f} mg/L: suficiente, no limita."
    factor = (od - OXYGEN_NO_GROWTH_MG_L) / (OXYGEN_FULL_GROWTH_MG_L - OXYGEN_NO_GROWTH_MG_L)
    return factor, (
        f"Oxigeno en {od:.2f} mg/L: limita el crecimiento al {factor * 100:.0f}% de su potencial."
    )


def ph_growth_factor(ph: float | None) -> tuple[float, str]:
    """Cuanto del crecimiento potencial permite el pH del agua."""
    if ph is None:
        return 1.0, "Sin lectura de pH: no se aplica limitacion."
    valor = float(ph)
    if PH_OPTIMAL_LOW <= valor <= PH_OPTIMAL_HIGH:
        return 1.0, f"pH en {valor:.2f}: dentro del rango optimo, no limita."
    if valor <= PH_LETHAL_LOW or valor >= PH_LETHAL_HIGH:
        return 0.0, f"pH en {valor:.2f}: fuera del rango tolerable, no hay crecimiento."
    if valor < PH_OPTIMAL_LOW:
        factor = (valor - PH_LETHAL_LOW) / (PH_OPTIMAL_LOW - PH_LETHAL_LOW)
        motivo = "acido"
    else:
        factor = (PH_LETHAL_HIGH - valor) / (PH_LETHAL_HIGH - PH_OPTIMAL_HIGH)
        motivo = "alcalino"
    return factor, (
        f"pH en {valor:.2f}, demasiado {motivo}: limita el crecimiento al {factor * 100:.0f}%."
    )


def tilapia_growth_temperature(
    temperature_c: float,
    initial_length_mm: float | None = None,
    projection_days: int | None = None,
    weight_length_model: dict[str, float | int] | None = None,
    dissolved_oxygen_mg_l: float | None = None,
    ph: float | None = None,
) -> dict[str, object]:
    temperature = float(temperature_c)
    validated_range = [21.0, 30.0]
    if not validated_range[0] <= temperature <= validated_range[1]:
        return {
            "status": "out_of_validated_domain",
            "temperature_c": temperature,
            "daily_length_gain_mm_day": None,
            "validated_temperature_range_c": validated_range,
            "source_r2": 0.95,
            "length_projection": None,
        }

    growth = soderberg_delta_l(temperature, "nile tilapia")
    potential_gain = float(growth["daily_length_gain_mm_day"])

    # La temperatura marca el techo; el oxigeno y el pH solo pueden bajarlo.
    oxygen_factor, oxygen_detail = oxygen_growth_factor(dissolved_oxygen_mg_l)
    ph_factor, ph_detail = ph_growth_factor(ph)
    combined_factor = oxygen_factor * ph_factor
    daily_gain = potential_gain * combined_factor
    limiting_factors = {
        "oxygen": {
            "value_mg_l": dissolved_oxygen_mg_l,
            "factor": round(oxygen_factor, 4),
            "detail": oxygen_detail,
        },
        "ph": {
            "value": ph,
            "factor": round(ph_factor, 4),
            "detail": ph_detail,
        },
        "combined_factor": round(combined_factor, 4),
        "limited_by": (
            "oxigeno" if oxygen_factor < ph_factor
            else "pH" if ph_factor < oxygen_factor
            else ("ninguno" if combined_factor >= 0.999 else "oxigeno y pH")
        ),
    }
    projection = None
    note = "No se proyecto longitud porque no existe una longitud inicial real."
    if initial_length_mm is not None:
        length = _positive("initial_length_mm", initial_length_mm)
        days = 1 if projection_days is None else int(projection_days)
        if days < 1:
            raise ValueError("projection_days must be positive")
        projected_length = length + daily_gain * days
        projection = {
            "initial_length_mm": length,
            "projection_days": days,
            "projected_length_mm": projected_length,
            "projected_weight_g": (
                local_weight_from_length(projected_length, weight_length_model)
                if weight_length_model is not None
                else None
            ),
        }
        note = (
            "Longitud y peso proyectados desde biometria real y una curva local longitud-peso."
            if weight_length_model is not None
            else "Longitud proyectada desde biometria real; el peso requiere al menos ocho mediciones biometrica detalladas."
        )
    return {
        "status": "calculated",
        "temperature_c": temperature,
        "daily_length_gain_mm_day": daily_gain,
        "potential_daily_length_gain_mm_day": potential_gain,
        "limiting_factors": limiting_factors,
        "validated_temperature_range_c": validated_range,
        "source_r2": 0.95,
        "length_projection": projection,
        "weight_length_model": weight_length_model,
        "note": note,
    }


def haskell_feed_rate(
    feed_conversion_ratio: float,
    daily_length_gain: float,
    fish_length: float,
) -> float:
    length = _positive("fish_length", fish_length)
    return (3.0 * _non_negative("feed_conversion_ratio", feed_conversion_ratio) * _non_negative("daily_length_gain", daily_length_gain) / length) * 100.0


def assess_body_condition(
    samples: list[dict[str, object]],
    model: dict[str, object] | None,
) -> dict[str, object] | None:
    """Contrasta el peso real de cada pez con el que predice la curva entrenada.

    La curva W = a*L^b dice cuanto deberia pesar un pez de esa talla en esta
    piscigranja. Dividir el peso medido entre ese peso esperado da el factor de
    condicion relativo: 1.00 es exactamente lo previsto, por debajo son peces
    mas flacos de lo que su talla promete y por encima, mas robustos.

    Se mira solo el ultimo muestreo, porque mezclar muestreos de fechas
    distintas promediaria estados que no son comparables. Se exige un minimo de
    peces para que una sola medida rara no dispare nada.
    """
    if not model:
        return None
    try:
        a = float(model["coefficient"])
        b = float(model["exponent"])
    except (KeyError, TypeError, ValueError):
        return None
    if a <= 0:
        return None

    fechas = [s.get("sampled_at") for s in samples if s.get("sampled_at") is not None]
    if not fechas:
        return None
    ultima = max(fechas)

    ratios: list[float] = []
    puntos: list[tuple[float, float]] = []
    for muestra in samples:
        if muestra.get("sampled_at") != ultima:
            continue
        length, weight = muestra.get("length_mm"), muestra.get("weight_g")
        if length is None or weight is None:
            continue
        l, w = float(length), float(weight)
        if l <= 0 or w <= 0:
            continue
        esperado = a * (l ** b)
        if esperado > 0:
            ratios.append(w / esperado)
            # se guardan para poder dibujar cada pez contra la curva
            puntos.append((l, w))

    # Con menos de ocho peces el promedio es demasiado fragil para avisar.
    if len(ratios) < 8:
        return None

    ratios.sort()
    n = len(ratios)
    kn = sum(ratios) / n
    mediana = ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2.0
    flacos = sum(1 for r in ratios if r < 0.90)
    robustos = sum(1 for r in ratios if r > 1.10)

    if kn < 0.90:
        estado = "bajo"
        lectura = (
            f"Los peces pesan un {round((1 - kn) * 100)}% menos de lo que su talla promete. "
            "Suele apuntar a alimentacion corta, competencia o algo que les esta pasando factura."
        )
    elif kn > 1.10:
        estado = "alto"
        lectura = (
            f"Los peces pesan un {round((kn - 1) * 100)}% mas de lo previsto para su talla. "
            "Conviene revisar que la medida de longitud se este tomando igual que siempre."
        )
    else:
        estado = "normal"
        lectura = "El peso acompana a la talla: la condicion corporal esta donde se espera."

    return {
        "points": puntos,
        "condition_factor": round(kn, 4),
        "median_factor": round(mediana, 4),
        "sample_size": n,
        "below_count": flacos,
        "above_count": robustos,
        "state": estado,
        "reading": lectura,
        "sampled_at": ultima.isoformat() if hasattr(ultima, "isoformat") else str(ultima),
        "expected_from": f"W = {a:.6g} * L^{b:.4f}",
        "note": (
            "Peso medido dividido entre el que predice la curva entrenada con los peces "
            "de esta misma piscigranja. Se usa solo el ultimo muestreo."
        ),
    }
