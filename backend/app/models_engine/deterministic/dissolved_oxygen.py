from __future__ import annotations

import math
from collections.abc import Sequence


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


def do_saturation(temp_c: float) -> float:
    temp = float(temp_c)
    return 14.589 - 0.4 * temp + 0.008 * temp**2 - 0.0000661 * temp**3


def respiration_sinusoidal(
    t_h: float,
    temp_c: float,
    r_m: float,
    amplitude: float,
    phase: float,
    p_k: float = 0.07,
    freq: float = 1 / 24,
) -> float:
    base = float(r_m) + float(amplitude) * math.cos(
        2 * math.pi * float(freq) * (float(t_h) + float(phase))
    )
    return max(0.0, base * math.exp(float(p_k) * (float(temp_c) - 15.0)))


def oxygen_supply_rate(
    lo2_l_h: float,
    pressure_pa: float,
    molar_mass_g_mol: float,
    temp_c: float,
    volume_m3: float,
    efficiency: float = 0.9,
) -> float:
    volume = _positive("volume_m3", volume_m3)
    na = 6.022e23
    boltzmann = 1.38e-23
    return (
        float(efficiency)
        * float(lo2_l_h)
        * float(pressure_pa)
        * float(molar_mass_g_mol)
    ) / (na * boltzmann * (float(temp_c) + 273.15) * volume)


def update_do_0d(
    x_prev: float,
    x_in: float,
    q_l_h: float,
    volume_l: float,
    s: float,
    k_rear: float,
    do_sat: float,
    biomass_kg: float,
    respiration_rate: float,
    dt_h: float,
) -> float:
    volume = _positive("volume_l", volume_l)
    dt = _positive("dt_h", dt_h)
    q = _non_negative("q_l_h", q_l_h)
    biomass = _non_negative("biomass_kg", biomass_kg)
    respiration = _non_negative("respiration_rate", respiration_rate)
    dxdt = (
        q * (float(x_in) - float(x_prev)) / volume
        + float(s)
        + float(k_rear) * (float(do_sat) - float(x_prev))
        - (biomass * respiration / volume)
    )
    return max(0.0, float(x_prev) + dt * dxdt)


def update_do_1d(
    concentrations: Sequence[float],
    saturation: Sequence[float],
    biomass: Sequence[float],
    q_over_area_h: float,
    k_rear_h_1: float,
    respiration_rate: float,
    area_m2: float,
    dx_m: float,
    dt_h: float,
) -> list[float]:
    if not concentrations:
        raise ValueError("concentrations must not be empty")
    if len(concentrations) != len(saturation) or len(concentrations) != len(biomass):
        raise ValueError("concentrations, saturation and biomass must have same length")

    dx = _positive("dx_m", dx_m)
    dt = _positive("dt_h", dt_h)
    area = _positive("area_m2", area_m2)
    q_area = _non_negative("q_over_area_h", q_over_area_h)
    respiration = _non_negative("respiration_rate", respiration_rate)
    if q_area > 0 and dt > dx / q_area:
        raise ValueError("dt_h violates upwind stability condition")

    result = [max(0.0, float(concentrations[0]))]
    for index in range(1, len(concentrations)):
        c_i = float(concentrations[index])
        c_prev = float(concentrations[index - 1])
        sat_i = float(saturation[index])
        biomass_i = float(biomass[index])
        biomass_prev = float(biomass[index - 1])
        advective = -q_area * ((c_i - c_prev) / dx)
        reaeration = float(k_rear_h_1) * (sat_i - c_i)
        respiration_sink = (respiration / area) * ((biomass_i - biomass_prev) / dx)
        result.append(max(0.0, c_i + dt * (advective + reaeration - respiration_sink)))
    return result
