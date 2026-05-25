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


def haskell_feed_rate(
    feed_conversion_ratio: float,
    daily_length_gain: float,
    fish_length: float,
) -> float:
    length = _positive("fish_length", fish_length)
    return (3.0 * _non_negative("feed_conversion_ratio", feed_conversion_ratio) * _non_negative("daily_length_gain", daily_length_gain) / length) * 100.0
