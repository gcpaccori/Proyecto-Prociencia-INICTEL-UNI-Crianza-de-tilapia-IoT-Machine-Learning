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
        raise ValueError("min-max normalization requires max != min")
    return (value - minimum) / (maximum - minimum)
