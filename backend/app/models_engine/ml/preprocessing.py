from __future__ import annotations

import math
from datetime import datetime
from statistics import median


def require_numeric_feature(name: str, value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc


def require_positive_feature(name: str, value: object) -> float:
    numeric_value = require_numeric_feature(name, value)
    if numeric_value <= 0:
        raise ValueError(f"{name} must be positive")
    return numeric_value


def require_non_negative_feature(name: str, value: object) -> float:
    numeric_value = require_numeric_feature(name, value)
    if numeric_value < 0:
        raise ValueError(f"{name} must be non-negative")
    return numeric_value


def require_numeric_series(name: str, value: object) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty numeric list")
    return [require_numeric_feature(name, item) for item in value]


def minmax_normalize(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    if maximum == minimum:
        return 0.0
    return (value - minimum) / (maximum - minimum)


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("values must not be empty")
    numbers = [float(value) for value in values]
    mean = sum(numbers) / len(numbers)
    variance = sum((value - mean) ** 2 for value in numbers) / len(numbers)
    return mean, variance**0.5


def sigma3_flags(values: list[float]) -> list[bool]:
    mean, std = mean_std(values)
    if std == 0:
        return [False for _ in values]
    return [abs(float(value) - mean) > 3 * std for value in values]


def linear_interpolate_missing(values: list[float | None]) -> list[float]:
    if not values:
        raise ValueError("values must not be empty")
    result: list[float | None] = list(values)
    known = [index for index, value in enumerate(result) if value is not None]
    if not known:
        raise ValueError("at least one value is required for interpolation")
    first = known[0]
    for index in range(0, first):
        result[index] = float(result[first])
    last = known[-1]
    for index in range(last + 1, len(result)):
        result[index] = float(result[last])
    for left, right in zip(known, known[1:]):
        left_value = float(result[left])
        right_value = float(result[right])
        span = right - left
        for index in range(left + 1, right):
            fraction = (index - left) / span
            result[index] = left_value + (right_value - left_value) * fraction
    return [float(value) for value in result]


def interpolate_short_internal_gaps(
    values: list[float | None],
    max_gap: int = 2,
) -> tuple[list[float | None], set[int]]:
    """Interpolate only bounded internal gaps and keep edge/long gaps missing."""
    if max_gap < 1:
        raise ValueError("max_gap must be positive")
    result = list(values)
    interpolated: set[int] = set()
    index = 0
    while index < len(result):
        if result[index] is not None:
            index += 1
            continue
        start = index
        while index < len(result) and result[index] is None:
            index += 1
        end = index
        gap_size = end - start
        if start == 0 or end == len(result) or gap_size > max_gap:
            continue
        left = float(result[start - 1])
        right = float(result[end])
        span = gap_size + 1
        for offset, target_index in enumerate(range(start, end), start=1):
            result[target_index] = left + (right - left) * (offset / span)
            interpolated.add(target_index)
    return result, interpolated


def hampel_flags(
    values: list[float | None],
    window_radius: int = 6,
    threshold: float = 3.5,
) -> list[bool]:
    """Return robust local outlier flags using rolling median and MAD."""
    if window_radius < 1:
        raise ValueError("window_radius must be positive")
    flags = [False] * len(values)
    for index, value in enumerate(values):
        if value is None:
            continue
        start = max(0, index - window_radius)
        end = min(len(values), index + window_radius + 1)
        window = [float(item) for item in values[start:end] if item is not None]
        if len(window) < 5:
            continue
        center = median(window)
        absolute_deviations = [abs(item - center) for item in window]
        mad = median(absolute_deviations)
        if mad == 0:
            continue
        robust_sigma = 1.4826 * mad
        flags[index] = abs(float(value) - center) > threshold * robust_sigma
    return flags


def infer_sampling_minutes(timestamps: list[datetime]) -> float:
    ordered = sorted(set(timestamps))
    differences = [
        (right - left).total_seconds() / 60.0
        for left, right in zip(ordered, ordered[1:])
        if right > left
    ]
    if not differences:
        raise ValueError("at least two distinct timestamps are required")
    return float(median(differences))


def align_sensor_series(
    series_by_variable: dict[str, list[tuple[datetime, float | None]]],
    required_variables: list[str],
) -> tuple[list[dict[str, object]], float]:
    """Align sensor values by timestamp with a half-frequency nearest tolerance."""
    if any(not series_by_variable.get(code) for code in required_variables):
        missing = [code for code in required_variables if not series_by_variable.get(code)]
        raise ValueError(f"variables without timestamps: {', '.join(missing)}")

    deduplicated: dict[str, list[tuple[datetime, float | None]]] = {}
    for code in required_variables:
        by_timestamp: dict[datetime, float | None] = {}
        for timestamp, value in sorted(series_by_variable[code], key=lambda item: item[0]):
            if timestamp not in by_timestamp:
                by_timestamp[timestamp] = value
        deduplicated[code] = sorted(by_timestamp.items(), key=lambda item: item[0])

    reference_code = min(required_variables, key=lambda code: len(deduplicated[code]))
    reference_times = [item[0] for item in deduplicated[reference_code]]
    sampling_minutes = infer_sampling_minutes(reference_times)
    tolerance_seconds = sampling_minutes * 30.0
    pointers = {code: 0 for code in required_variables}
    aligned: list[dict[str, object]] = []

    for timestamp in reference_times:
        values: dict[str, float | None] = {}
        source_times: dict[str, datetime] = {}
        for code in required_variables:
            rows = deduplicated[code]
            pointer = pointers[code]
            while pointer + 1 < len(rows) and rows[pointer + 1][0] <= timestamp:
                pointer += 1
            candidates = rows[max(0, pointer - 1) : min(len(rows), pointer + 2)]
            nearest = min(candidates, key=lambda item: abs((item[0] - timestamp).total_seconds()))
            if abs((nearest[0] - timestamp).total_seconds()) <= tolerance_seconds:
                values[code] = nearest[1]
                source_times[code] = nearest[0]
                pointers[code] = pointer
            else:
                values[code] = None
        aligned.append(
            {
                "timestamp": timestamp,
                "values": values,
                "source_times": source_times,
                "interpolated_variables": set(),
                "invalid_variables": set(),
            }
        )
    return aligned, sampling_minutes


def build_svm_od_feature_rows(
    aligned_rows: list[dict[str, object]],
    sampling_minutes: float,
    required_variables: list[str],
) -> tuple[list[dict[str, object]], int, list[str]]:
    if sampling_minutes <= 0:
        raise ValueError("sampling_minutes must be positive")
    horizon_steps = max(1, round(60.0 / sampling_minutes))
    feature_names: list[str] = []
    for code in required_variables:
        feature_names.extend(
            [
                code,
                *[f"{code}_lag_{lag}" for lag in (1, 2, 3, 6)],
                f"{code}_mean_3",
                f"{code}_mean_6",
                f"{code}_std_6",
            ]
        )
    feature_names.extend(["hour_sin", "hour_cos"])

    feature_rows: list[dict[str, object]] = []
    for current_index in range(6, len(aligned_rows) - horizon_steps):
        target_index = current_index + horizon_steps
        lookback = aligned_rows[current_index - 6 : current_index + 1]
        target_row = aligned_rows[target_index]
        if any(row.get("invalid_variables") for row in lookback):
            continue
        if "dissolved_oxygen_mg_l" in target_row.get("invalid_variables", set()):
            continue

        values_by_variable: dict[str, list[float]] = {}
        missing = False
        for code in required_variables:
            values = [row["values"].get(code) for row in lookback]
            if any(value is None for value in values):
                missing = True
                break
            values_by_variable[code] = [float(value) for value in values]
        target = target_row["values"].get("dissolved_oxygen_mg_l")
        if missing or target is None:
            continue

        interpolated_count = sum(
            code in row.get("interpolated_variables", set())
            for row in lookback
            for code in required_variables
        )
        interpolated_ratio = interpolated_count / (len(lookback) * len(required_variables))
        if interpolated_ratio > 0.20:
            continue

        current_time = aligned_rows[current_index]["timestamp"]
        target_time = target_row["timestamp"]
        expected_seconds = horizon_steps * sampling_minutes * 60.0
        actual_seconds = (target_time - current_time).total_seconds()
        if abs(actual_seconds - expected_seconds) > sampling_minutes * 60.0:
            continue

        row: dict[str, object] = {
            "row_index": len(feature_rows),
            "issued_at": current_time,
            "target_time": target_time,
            "target": float(target),
            "interpolated_ratio": interpolated_ratio,
        }
        for code, values in values_by_variable.items():
            row[code] = values[-1]
            for lag in (1, 2, 3, 6):
                row[f"{code}_lag_{lag}"] = values[-1 - lag]
            mean_3 = sum(values[-3:]) / 3.0
            recent_6 = values[-6:]
            mean_6 = sum(recent_6) / 6.0
            row[f"{code}_mean_3"] = mean_3
            row[f"{code}_mean_6"] = mean_6
            row[f"{code}_std_6"] = math.sqrt(
                sum((value - mean_6) ** 2 for value in recent_6) / 6.0
            )
        hour = current_time.hour + current_time.minute / 60.0
        row["hour_sin"] = math.sin(2.0 * math.pi * hour / 24.0)
        row["hour_cos"] = math.cos(2.0 * math.pi * hour / 24.0)
        feature_rows.append(row)
    return feature_rows, horizon_steps, feature_names


def build_latest_svm_od_features(
    aligned_rows: list[dict[str, object]],
    required_variables: list[str],
) -> dict[str, object]:
    for current_index in range(len(aligned_rows) - 1, 5, -1):
        lookback = aligned_rows[current_index - 6 : current_index + 1]
        if any(row.get("invalid_variables") for row in lookback):
            continue
        values_by_variable: dict[str, list[float]] = {}
        if any(
            row["values"].get(code) is None
            for row in lookback
            for code in required_variables
        ):
            continue
        for code in required_variables:
            values_by_variable[code] = [
                float(row["values"][code]) for row in lookback
            ]
        row: dict[str, object] = {
            "issued_at": aligned_rows[current_index]["timestamp"],
            "input_window_start": lookback[0]["timestamp"],
            "input_window_end": lookback[-1]["timestamp"],
            "interpolated_ratio": sum(
                code in item.get("interpolated_variables", set())
                for item in lookback
                for code in required_variables
            )
            / (len(lookback) * len(required_variables)),
        }
        for code, values in values_by_variable.items():
            row[code] = values[-1]
            for lag in (1, 2, 3, 6):
                row[f"{code}_lag_{lag}"] = values[-1 - lag]
            recent_6 = values[-6:]
            mean_3 = sum(values[-3:]) / 3.0
            mean_6 = sum(recent_6) / 6.0
            row[f"{code}_mean_3"] = mean_3
            row[f"{code}_mean_6"] = mean_6
            row[f"{code}_std_6"] = math.sqrt(
                sum((value - mean_6) ** 2 for value in recent_6) / 6.0
            )
        current_time = row["issued_at"]
        hour = current_time.hour + current_time.minute / 60.0
        row["hour_sin"] = math.sin(2.0 * math.pi * hour / 24.0)
        row["hour_cos"] = math.cos(2.0 * math.pi * hour / 24.0)
        return row
    raise ValueError("no complete recent seven-step window is available")


def pearson_correlation(x_values: list[float], y_values: list[float]) -> float:
    if len(x_values) != len(y_values) or not x_values:
        raise ValueError("x_values and y_values must be non-empty and aligned")
    x = [float(value) for value in x_values]
    y = [float(value) for value in y_values]
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    numerator = sum((x_i - x_mean) * (y_i - y_mean) for x_i, y_i in zip(x, y))
    x_den = sum((x_i - x_mean) ** 2 for x_i in x) ** 0.5
    y_den = sum((y_i - y_mean) ** 2 for y_i in y) ** 0.5
    if x_den == 0 or y_den == 0:
        return 0.0
    return numerator / (x_den * y_den)


def select_pearson_features(
    features: dict[str, list[float]],
    target: list[float],
    threshold: float = 0.3,
) -> dict[str, float]:
    return {
        name: correlation
        for name, values in features.items()
        if abs(correlation := pearson_correlation(values, target)) >= threshold
    }


def make_time_windows(
    series: list[float],
    window_size: int,
    horizon: int = 1,
) -> list[dict[str, object]]:
    if window_size <= 0 or horizon <= 0:
        raise ValueError("window_size and horizon must be positive")
    if len(series) < window_size + horizon:
        return []
    windows: list[dict[str, object]] = []
    for start in range(0, len(series) - window_size - horizon + 1):
        end = start + window_size
        windows.append(
            {
                "x": [float(value) for value in series[start:end]],
                "y": float(series[end + horizon - 1]),
            }
        )
    return windows


def temporal_train_validation_test_split(
    rows: list[object],
    train_fraction: float = 0.7,
    validation_fraction: float = 0.15,
) -> dict[str, list[object]]:
    if train_fraction <= 0 or validation_fraction < 0:
        raise ValueError("fractions must be non-negative and train_fraction positive")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train_fraction + validation_fraction must be lower than 1")
    train_end = int(len(rows) * train_fraction)
    validation_end = train_end + int(len(rows) * validation_fraction)
    return {
        "train": rows[:train_end],
        "validation": rows[train_end:validation_end],
        "test": rows[validation_end:],
    }


def regression_metrics(
    observed: list[float],
    predicted: list[float],
) -> dict[str, float]:
    if len(observed) != len(predicted) or not observed:
        raise ValueError("observed and predicted must be non-empty and aligned")
    obs = [float(value) for value in observed]
    pred = [float(value) for value in predicted]
    errors = [obs_i - pred_i for obs_i, pred_i in zip(obs, pred)]
    mse = sum(error**2 for error in errors) / len(errors)
    mae = sum(abs(error) for error in errors) / len(errors)
    mean_obs = sum(obs) / len(obs)
    total = sum((value - mean_obs) ** 2 for value in obs)
    residual = sum(error**2 for error in errors)
    return {
        "mse": mse,
        "rmse": mse**0.5,
        "mae": mae,
        "r2": 1.0 - residual / total if total else 0.0,
    }


def classification_metrics(
    observed: list[object],
    predicted: list[object],
    positive_label: object = 1,
) -> dict[str, float]:
    if len(observed) != len(predicted) or not observed:
        raise ValueError("observed and predicted must be non-empty and aligned")
    tp = sum(1 for obs, pred in zip(observed, predicted) if obs == positive_label and pred == positive_label)
    fp = sum(1 for obs, pred in zip(observed, predicted) if obs != positive_label and pred == positive_label)
    fn = sum(1 for obs, pred in zip(observed, predicted) if obs == positive_label and pred != positive_label)
    correct = sum(1 for obs, pred in zip(observed, predicted) if obs == pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": correct / len(observed),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
