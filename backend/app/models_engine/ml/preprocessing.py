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
