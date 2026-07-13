import math
from datetime import datetime, timedelta, timezone

from backend.app.models_engine.deterministic.dissolved_oxygen import oxygen_status
from backend.app.models_engine.deterministic.growth import tilapia_growth_temperature
from backend.app.models_engine.deterministic.water_quality import water_quality_index
from backend.app.application.real_models import RealModelsService
from backend.app.models_engine.ml.preprocessing import (
    align_sensor_series,
    build_latest_svm_od_features,
    build_svm_od_feature_rows,
    interpolate_short_internal_gaps,
)
from backend.app.models_engine.ml.ica_classifier import build_ica_training_rows


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


def test_formula_relationship_chart_marks_the_current_measurement() -> None:
    latest = {
        "values": {
            "water_temperature_c": 26.0,
            "dissolved_oxygen_mg_l": 5.9,
        }
    }

    chart = RealModelsService._oxygen_temperature_chart([24.0, 25.0, 26.0], latest)

    assert chart["series"][0]["type"] == "line"
    assert chart["series"][1]["type"] == "scatter"
    assert chart["series"][1]["data"][0][0] == 26.0
    assert chart["series"][1]["data"][0][1] > 0


def test_forecast_chart_focuses_on_the_future_segment_and_marks_it() -> None:
    chart = RealModelsService._chart(
        "Proyeccion",
        [
            RealModelsService._series(
                "Prueba IA +1h",
                [["2026-01-01T00:00:00", 6.0], ["2026-01-01T01:00:00", 6.2]],
                "#f59e0b",
                dashed=True,
            )
        ],
        "mg/L",
        focus_from="2025-12-31T21:00:00",
    )

    assert chart["dataZoom"][0]["startValue"] == "2025-12-31T21:00:00"
    assert chart["series"][0]["showSymbol"] is True
    assert chart["series"][0]["markPoint"]["data"][0]["coord"][1] == 6.2


def test_water_quality_index_uses_documented_weights_and_ranges() -> None:
    excellent = water_quality_index(28.5, 7.4, 6.2, 12.0)
    assert excellent["ica"] == 100.0
    assert excellent["classification"] == "Excelente"

    low_oxygen = water_quality_index(28.0, 7.4, 2.5, 12.0)
    assert low_oxygen["ica"] == 82.5
    assert low_oxygen["classification"] == "Buena"
    assert low_oxygen["components"][2]["normalized_score"] == 50.0


def test_ica_training_rows_keep_only_clean_simultaneous_sensor_readings() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    aligned = [
        {
            "timestamp": started_at,
            "values": {
                "water_temperature_c": 28.0,
                "ph": 7.4,
                "dissolved_oxygen_mg_l": 6.2,
                "nitrate_ion": 12.0,
            },
            "invalid_variables": set(),
            "interpolated_variables": set(),
        },
        {
            "timestamp": started_at + timedelta(minutes=15),
            "values": {
                "water_temperature_c": 28.0,
                "ph": 7.4,
                "dissolved_oxygen_mg_l": 6.2,
                "nitrate_ion": 12.0,
            },
            "invalid_variables": {"nitrate_ion"},
            "interpolated_variables": set(),
        },
    ]

    rows = build_ica_training_rows(aligned)

    assert len(rows) == 1
    assert rows[0]["target_label"] == "Excelente"
    assert rows[0]["dissolved_oxygen_mg_l"] == 6.2
