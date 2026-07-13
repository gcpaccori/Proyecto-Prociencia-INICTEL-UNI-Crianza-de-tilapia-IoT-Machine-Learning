from __future__ import annotations

import math
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


def tilapia_growth_temperature(
    temperature_c: float,
    initial_length_mm: float | None = None,
    projection_days: int | None = None,
    weight_length_model: dict[str, float | int] | None = None,
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
    daily_gain = float(growth["daily_length_gain_mm_day"])
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
