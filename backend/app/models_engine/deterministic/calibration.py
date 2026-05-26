from __future__ import annotations

from collections.abc import Sequence


def _aligned_numbers(
    observed: Sequence[float],
    predicted: Sequence[float],
) -> tuple[list[float], list[float]]:
    if len(observed) != len(predicted) or not observed:
        raise ValueError("observed and predicted must be non-empty and aligned")
    return [float(value) for value in observed], [float(value) for value in predicted]


def sum_squared_error(
    observed: Sequence[float],
    predicted: Sequence[float],
) -> float:
    obs, pred = _aligned_numbers(observed, predicted)
    return sum((obs_i - pred_i) ** 2 for obs_i, pred_i in zip(obs, pred))


def mean_absolute_error(
    observed: Sequence[float],
    predicted: Sequence[float],
) -> float:
    obs, pred = _aligned_numbers(observed, predicted)
    return sum(abs(obs_i - pred_i) for obs_i, pred_i in zip(obs, pred)) / len(obs)


def root_mean_squared_error(
    observed: Sequence[float],
    predicted: Sequence[float],
) -> float:
    obs, pred = _aligned_numbers(observed, predicted)
    return (sum_squared_error(obs, pred) / len(obs)) ** 0.5


def calibration_objective(
    observed: Sequence[float],
    predicted: Sequence[float],
    metric: str = "sse",
) -> float:
    metric_name = metric.strip().lower()
    if metric_name == "sse":
        return sum_squared_error(observed, predicted)
    if metric_name == "rmse":
        return root_mean_squared_error(observed, predicted)
    if metric_name == "mae":
        return mean_absolute_error(observed, predicted)
    raise ValueError("metric must be one of: sse, rmse, mae")
