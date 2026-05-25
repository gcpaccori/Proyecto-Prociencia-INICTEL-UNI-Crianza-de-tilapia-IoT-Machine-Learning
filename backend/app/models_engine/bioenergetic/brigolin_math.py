from __future__ import annotations

import math


BRIGOLIN_DEFAULTS = {
    "i_max_day_1": 0.09,
    "alpha": 0.3,
    "protein_assimilation": 0.85,
    "carbohydrate_assimilation": 0.5,
    "lipid_assimilation": 0.95,
    "protein_energy_kj_g": 23.6,
    "carbohydrate_energy_kj_g": 17.2,
    "lipid_energy_kj_g": 36.2,
    "oxygen_energy_kj_g": 13.6,
    "p_k_c_1": 0.06,
    "k_0_day_1": 0.00072,
    "m": 0.6,
    "n": 1.0,
    "b": 0.2,
    "t_0_c": 25.0,
    "t_m_c": 32.9,
}


def _positive(name: str, value: float) -> float:
    numeric = float(value)
    if numeric <= 0:
        raise ValueError(f"{name} must be positive")
    return numeric


def _fraction(name: str, value: float) -> float:
    numeric = float(value)
    if numeric < 0 or numeric > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric


def somatic_energy_content_kj_g(weight_g: float) -> float:
    weight = _positive("weight_g", weight_g)
    return 4.66 * weight**0.14


def brigolin_temperature_effect(
    temp_c: float,
    t_0_c: float = BRIGOLIN_DEFAULTS["t_0_c"],
    t_m_c: float = BRIGOLIN_DEFAULTS["t_m_c"],
    b: float = BRIGOLIN_DEFAULTS["b"],
) -> float:
    temp = float(temp_c)
    if temp < 12.0 or temp >= t_m_c:
        return 0.0
    ratio = max(0.0, (t_m_c - temp) / (t_m_c - t_0_c))
    return (ratio ** (b * (t_m_c - t_0_c))) * math.exp(b * (temp - t_0_c))


def brigolin_step(
    wet_weight_g: float,
    water_temperature_c: float,
    feed_ration_day_1: float,
    protein_fraction: float,
    lipid_fraction: float,
    carbohydrate_fraction: float,
    protein_digestibility: float | None = None,
    lipid_digestibility: float | None = None,
    carbohydrate_digestibility: float | None = None,
    energy_content_somatic_tissue_kj_g: float | None = None,
    dt_day: float = 1.0,
    parameters: dict[str, float] | None = None,
) -> dict[str, float]:
    params = {**BRIGOLIN_DEFAULTS, **(parameters or {})}
    weight = _positive("wet_weight_g", wet_weight_g)
    dt = _positive("dt_day", dt_day)
    protein = _fraction("protein_fraction", protein_fraction)
    lipid = _fraction("lipid_fraction", lipid_fraction)
    carbohydrate = _fraction("carbohydrate_fraction", carbohydrate_fraction)
    if protein + lipid + carbohydrate > 1.0:
        raise ValueError("diet fractions must sum to 1.0 or less")

    beta_p = _fraction(
        "protein_digestibility",
        protein_digestibility
        if protein_digestibility is not None
        else params["protein_assimilation"],
    )
    beta_l = _fraction(
        "lipid_digestibility",
        lipid_digestibility
        if lipid_digestibility is not None
        else params["lipid_assimilation"],
    )
    beta_c = _fraction(
        "carbohydrate_digestibility",
        carbohydrate_digestibility
        if carbohydrate_digestibility is not None
        else params["carbohydrate_assimilation"],
    )

    h_tw = brigolin_temperature_effect(
        water_temperature_c,
        params["t_0_c"],
        params["t_m_c"],
        params["b"],
    )
    i_unlimited = params["i_max_day_1"] * h_tw * (weight ** params["m"])
    feed_intake_day_1 = min(i_unlimited, float(feed_ration_day_1)) if water_temperature_c >= 12.0 else 0.0
    diet_energy = (
        protein * params["protein_energy_kj_g"] * beta_p
        + carbohydrate * params["carbohydrate_energy_kj_g"] * beta_c
        + lipid * params["lipid_energy_kj_g"] * beta_l
    )
    net_anabolism_kj_day = (1.0 - params["alpha"]) * feed_intake_day_1 * diet_energy
    feces_production_g_day = feed_intake_day_1 * (
        protein * (1.0 - beta_p)
        + carbohydrate * (1.0 - beta_c)
        + lipid * (1.0 - beta_l)
    )
    fasting_catabolism_kj_day = (
        params["oxygen_energy_kj_g"]
        * params["k_0_day_1"]
        * math.exp(params["p_k_c_1"] * float(water_temperature_c))
        * (weight ** params["n"])
    )
    epsilon_t = (
        _positive("energy_content_somatic_tissue_kj_g", energy_content_somatic_tissue_kj_g)
        if energy_content_somatic_tissue_kj_g is not None
        else somatic_energy_content_kj_g(weight)
    )
    delta_weight_g_day = (net_anabolism_kj_day - fasting_catabolism_kj_day) / epsilon_t
    predicted_weight = max(0.0, weight + delta_weight_g_day * dt)
    return {
        "predicted_weight_g": predicted_weight,
        "delta_weight_g_day": delta_weight_g_day,
        "net_anabolism_j_day": net_anabolism_kj_day * 1000.0,
        "fasting_catabolism_j_day": fasting_catabolism_kj_day * 1000.0,
        "feed_intake_day_1": feed_intake_day_1,
        "uneaten_feed_g": max(0.0, float(feed_ration_day_1) - feed_intake_day_1) * weight,
        "feces_production_g_day": feces_production_g_day,
        "temperature_effect": h_tw,
        "somatic_energy_content_kj_g": epsilon_t,
    }
