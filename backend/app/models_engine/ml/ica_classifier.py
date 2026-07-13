from __future__ import annotations

from backend.app.models_engine.deterministic.water_quality import water_quality_index


ICA_FEATURE_NAMES = [
    "water_temperature_c",
    "ph",
    "dissolved_oxygen_mg_l",
    "nitrate_ion",
]
ICA_CLASS_ORDER = ["Excelente", "Buena", "Regular", "Mala", "Muy mala"]
ICA_CLASS_TO_CODE = {label: index for index, label in enumerate(ICA_CLASS_ORDER)}


def build_ica_training_rows(aligned_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Create chronological ICA labels from clean, simultaneous sensor readings.

    The target is deliberately named as a formula-derived label because the
    database has no independent field-quality labels for a supervised target.
    """
    rows: list[dict[str, object]] = []
    for index, source in enumerate(aligned_rows):
        values = source["values"]
        invalid = source.get("invalid_variables", set())
        interpolated = source.get("interpolated_variables", set())
        if any(values.get(name) is None or name in invalid for name in ICA_FEATURE_NAMES):
            continue
        if any(name in interpolated for name in ICA_FEATURE_NAMES):
            continue
        result = water_quality_index(
            float(values["water_temperature_c"]),
            float(values["ph"]),
            float(values["dissolved_oxygen_mg_l"]),
            float(values["nitrate_ion"]),
        )
        label = str(result["classification"])
        rows.append(
            {
                "row_index": index,
                "issued_at": source["timestamp"],
                "target_time": source["timestamp"],
                "target": ICA_CLASS_TO_CODE[label],
                "target_label": label,
                "interpolated_ratio": 0.0,
                **{name: float(values[name]) for name in ICA_FEATURE_NAMES},
            }
        )
    return rows
