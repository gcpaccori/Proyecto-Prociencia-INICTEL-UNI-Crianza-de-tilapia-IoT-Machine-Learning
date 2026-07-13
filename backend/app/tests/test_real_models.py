import math
from datetime import datetime, timedelta, timezone

from backend.app.models_engine.deterministic.dissolved_oxygen import oxygen_status
from backend.app.models_engine.deterministic.growth import tilapia_growth_temperature
from backend.app.application.real_models import RealModelsService
from backend.app.models_engine.ml.preprocessing import (
    align_sensor_series,
    build_latest_svm_od_features,
    build_svm_od_feature_rows,
    interpolate_short_internal_gaps,
)


VARIABLES = [
    "water_temperature_c",
    "ph",
    "dissolved_oxygen_mg_l",
    "nitrate_ion",
]


def test_short_gap_interpolation_never_fills_edges_or_long_gaps() -> None:
    values, interpolated = interpolate_short_internal_gaps(
        [None, 1.0, None, None, 4.0, None, None, None, 8.0, None],
        max_gap=2,
    )

    assert values == [None, 1.0, 2.0, 3.0, 4.0, None, None, None, 8.0, None]
    assert interpolated == {2, 3}


def test_svm_features_are_timestamp_aligned_and_target_one_hour_ahead() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    series = {code: [] for code in VARIABLES}
    for index in range(620):
        timestamp = started_at + timedelta(minutes=10 * index)
        series["water_temperature_c"].append((timestamp, 27.0 + math.sin(index / 20)))
        series["ph"].append((timestamp, 7.5 + math.cos(index / 25) * 0.1))
        series["dissolved_oxygen_mg_l"].append((timestamp, 6.0 + math.sin(index / 18) * 0.4))
        series["nitrate_ion"].append((timestamp, 10.0 + math.cos(index / 30)))

    aligned, sampling_minutes = align_sensor_series(series, VARIABLES)
    feature_rows, horizon_steps, feature_names = build_svm_od_feature_rows(
        aligned,
        sampling_minutes,
        VARIABLES,
    )

    assert sampling_minutes == 10.0
    assert horizon_steps == 6
    assert len(feature_rows) >= 500
    assert feature_rows[0]["target_time"] - feature_rows[0]["issued_at"] == timedelta(hours=1)
    assert "dissolved_oxygen_mg_l_lag_6" in feature_names
    latest = build_latest_svm_od_features(aligned, VARIABLES)
    assert latest["dissolved_oxygen_mg_l_lag_6"] == series["dissolved_oxygen_mg_l"][-7][1]


def test_deterministic_models_use_only_supplied_real_measurements() -> None:
    oxygen = oxygen_status(27.0, 5.8, 5.42)
    assert oxygen["do_saturation_mg_l"] > oxygen["measured_do_mg_l"]
    assert oxygen["forecast_saturation_percent_1h"] < oxygen["saturation_percent"]

    growth = tilapia_growth_temperature(27.0)
    assert growth["status"] == "calculated"
    assert growth["daily_length_gain_mm_day"] == -1.6707 + 0.09682 * 27.0
    assert growth["length_projection"] is None

    outside_domain = tilapia_growth_temperature(20.0)
    assert outside_domain["status"] == "out_of_validated_domain"
    assert outside_domain["daily_length_gain_mm_day"] is None


def test_correlation_chart_is_built_from_real_variable_rows() -> None:
    chart = RealModelsService._correlation_chart(
        "Correlacion de prueba",
        [
            {"temperature_c": 24.0, "od_mg_l": 5.1},
            {"temperature_c": 25.0, "od_mg_l": 5.5},
            {"temperature_c": 26.0, "od_mg_l": 5.9},
        ],
        {"temperature_c": "Temperatura (C)", "od_mg_l": "OD (mg/L)"},
    )

    assert chart["series"][0]["type"] == "heatmap"
    assert len(chart["series"][0]["data"]) == 4
    assert chart["series"][0]["data"][1][2] == 1.0
