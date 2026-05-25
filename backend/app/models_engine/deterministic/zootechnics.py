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


def zootechnic_indexes(
    final_weight_g: float,
    initial_weight_g: float,
    final_length_cm: float,
    days: float,
    final_fish_count: float,
    initial_fish_count: float,
    feed_consumed_g: float,
    biomass_removed_mortality_g: float = 0.0,
    biomass_sampled_g: float = 0.0,
    tank_to_m3_factor: float = 1.666,
    average_feed_per_fish_g: float | None = None,
    average_body_weight_g: float | None = None,
) -> dict[str, float]:
    final_weight = _positive("final_weight_g", final_weight_g)
    initial_weight = _positive("initial_weight_g", initial_weight_g)
    final_length = _positive("final_length_cm", final_length_cm)
    duration = _positive("days", days)
    final_count = _non_negative("final_fish_count", final_fish_count)
    initial_count = _positive("initial_fish_count", initial_fish_count)
    feed = _non_negative("feed_consumed_g", feed_consumed_g)
    final_biomass_g = final_weight * final_count
    gain_biomass_total_g = (
        final_biomass_g
        - initial_weight * initial_count
        + _non_negative("biomass_removed_mortality_g", biomass_removed_mortality_g)
        + _non_negative("biomass_sampled_g", biomass_sampled_g)
    )
    adjusted_fcr = feed / gain_biomass_total_g if gain_biomass_total_g > 0 else 0.0
    avg_feed = feed / final_count if average_feed_per_fish_g is None and final_count > 0 else average_feed_per_fish_g or 0.0
    avg_weight = (
        (initial_weight + final_weight) / 2.0
        if average_body_weight_g is None
        else _positive("average_body_weight_g", average_body_weight_g)
    )
    mortality_count = max(0.0, initial_count - final_count)
    return {
        "condition_factor": 100.0 * final_weight / (final_length**3),
        "final_biomass_kg_m3": (final_weight * final_count / 1000.0) * float(tank_to_m3_factor),
        "daily_gain_g_fish_day": (final_weight - initial_weight) / duration,
        "specific_growth_rate_percent_day": 100.0 * (math.log(final_weight) - math.log(initial_weight)) / duration,
        "adjusted_feed_conversion_ratio": adjusted_fcr,
        "feeding_rate_percent_biomass": 100.0 * avg_feed / avg_weight if avg_weight > 0 else 0.0,
        "mortality_percent": 100.0 * mortality_count / initial_count,
        "gain_biomass_total_g": gain_biomass_total_g,
    }
