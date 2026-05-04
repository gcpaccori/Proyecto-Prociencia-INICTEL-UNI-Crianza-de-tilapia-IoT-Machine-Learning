from backend.app.models_engine.base import ModelInput


class VisionArtifactPendingError(RuntimeError):
    pass


def require_media_reference(model_input: ModelInput) -> None:
    image_value = model_input.inputs.get("image")
    frame_value = model_input.inputs.get("video_frame")
    if image_value is None and frame_value is None:
        raise ValueError("image or video_frame is required")

    if image_value is not None and image_value.unit != "image_ref":
        raise ValueError(f"image must use unit image_ref; received {image_value.unit}")
    if frame_value is not None and frame_value.unit != "frame_ref":
        raise ValueError(
            f"video_frame must use unit frame_ref; received {frame_value.unit}"
        )


def require_mapping(name: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def require_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def require_non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        numeric_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if numeric_value < 0:
        raise ValueError(f"{name} must be non-negative")
    if numeric_value != value:
        raise ValueError(f"{name} must be an integer")
    return numeric_value


def require_non_negative_float(name: str, value: object) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if numeric_value < 0:
        raise ValueError(f"{name} must be non-negative")
    return numeric_value


def require_probability(name: str, value: object) -> float:
    numeric_value = require_non_negative_float(name, value)
    if numeric_value > 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric_value
