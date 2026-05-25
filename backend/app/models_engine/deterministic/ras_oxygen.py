from __future__ import annotations

import math


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


def fish_respiration_do(
    average_weight_g: float,
    temperature_c: float,
    stocking_density_kg_m3: float,
) -> float:
    weight = _positive("average_weight_g", average_weight_g)
    density = _non_negative("stocking_density_kg_m3", stocking_density_kg_m3)
    temp = float(temperature_c)
    fr = (
        2014.45
        + 2.75 * weight
        - 165.2 * temp
        + 0.007 * weight**2
        + 3.93 * temp**2
        - 0.21 * weight * temp
    )
    return max(0.0, fr * density / 1000.0)


def auxiliary_feed_rate(weight_g: float) -> float:
    weight = _positive("weight_g", weight_g)
    return 17.02 * math.exp((math.log(weight + 1.14) ** 2) / -19.52)


def nitrification_do(
    temperature_c: float,
    feed_rate_percent_body_weight_day: float,
    average_weight_g: float,
    fish_count: float,
    volume_m3: float,
) -> float:
    volume = _positive("volume_m3", volume_m3)
    feed_rate = _non_negative(
        "feed_rate_percent_body_weight_day",
        feed_rate_percent_body_weight_day,
    )
    weight = _positive("average_weight_g", average_weight_g)
    count = _non_negative("fish_count", fish_count)
    k_nr = 0.1 * (1.08 ** (float(temperature_c) - 20.0))
    n_r = (0.03 * feed_rate * weight * count) / (24.0 * 1000.0)
    return 4.57 * k_nr * (n_r / volume)


def biofilter_do(
    bod5_mg_o2_kg_day: float,
    biomass_kg: float,
    volume_m3: float,
) -> float:
    volume = _positive("volume_m3", volume_m3)
    return (
        2.3
        * _non_negative("bod5_mg_o2_kg_day", bod5_mg_o2_kg_day)
        * _non_negative("biomass_kg", biomass_kg)
    ) / (volume * 24.0 * 1000.0)


def pipe_flow_oxygen(
    pump_cycle_h: float,
    pump_frequency_h_1: float,
    efficiency: float,
    oxygen_transfer_rate_g_h: float,
    volume_m3: float,
) -> float:
    volume = _positive("volume_m3", volume_m3)
    eff = float(efficiency)
    if eff > 1:
        eff = eff / 100.0
    eff = max(0.0, min(1.0, eff))
    return (
        _non_negative("pump_cycle_h", pump_cycle_h)
        * _non_negative("pump_frequency_h_1", pump_frequency_h_1)
        * eff
        * _non_negative("oxygen_transfer_rate_g_h", oxygen_transfer_rate_g_h)
    ) / volume


def ras_oxygen_balance(
    do_previous_mg_l: float,
    average_weight_g: float,
    temperature_c: float,
    stocking_density_kg_m3: float,
    fish_count: float,
    volume_m3: float,
    biomass_kg: float,
    dt_h: float,
    feed_rate_percent_body_weight_day: float | None = None,
    bod5_mg_o2_kg_day: float = 2160.0,
    pump_cycle_h: float = 0.0,
    pump_frequency_h_1: float = 0.0,
    pump_efficiency: float = 0.0,
    oxygen_transfer_rate_g_h: float = 0.0,
) -> dict[str, float]:
    volume = _positive("volume_m3", volume_m3)
    dt = _positive("dt_h", dt_h)
    feed_rate = (
        auxiliary_feed_rate(average_weight_g)
        if feed_rate_percent_body_weight_day is None
        else float(feed_rate_percent_body_weight_day)
    )
    do_fr = fish_respiration_do(
        average_weight_g,
        temperature_c,
        stocking_density_kg_m3,
    )
    do_n = nitrification_do(
        temperature_c,
        feed_rate,
        average_weight_g,
        fish_count,
        volume,
    )
    do_b = biofilter_do(bod5_mg_o2_kg_day, biomass_kg, volume)
    do_pf = pipe_flow_oxygen(
        pump_cycle_h,
        pump_frequency_h_1,
        pump_efficiency,
        oxygen_transfer_rate_g_h,
        volume,
    )
    oxygen_required = max(0.0, do_fr + do_b + do_n - do_pf)
    do_next = max(0.0, float(do_previous_mg_l) + (do_pf - do_fr - do_b - do_n) * dt)
    return {
        "do_next_mg_l": do_next,
        "oxygen_required_mg_l_h": oxygen_required,
        "fish_respiration_mg_l_h": do_fr,
        "biofilter_consumption_mg_l_h": do_b,
        "nitrification_consumption_mg_l_h": do_n,
        "pipe_flow_oxygen_mg_l_h": do_pf,
        "feed_rate_percent_body_weight_day": feed_rate,
    }
