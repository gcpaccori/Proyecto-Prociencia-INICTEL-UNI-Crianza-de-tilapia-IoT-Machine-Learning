from datetime import datetime, timezone

import pytest

from backend.app.models_engine.base import ModelInput, ModelInputValue, ModelRunContext
from backend.app.models_engine.feeding import DailyRationModel, FeedingSatietyRules


def test_feeding_satiety_rules_stop_on_no_reaction() -> None:
    model = FeedingSatietyRules()
    model_input = ModelInput(
        model_code="FEEDING_SATIETY_RULES",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        inputs={
            "feeding_behavior_category": ModelInputValue(
                value="NO_REACTION",
                unit="category",
            ),
            "feed_remaining": ModelInputValue(value=True, unit="boolean"),
            "fish_reaction": ModelInputValue(value="No reaction", unit="text"),
        },
    )
    context = ModelRunContext(
        model_code="FEEDING_SATIETY_RULES",
        model_version="1.0.0",
        source_report="INFORME017",
    )

    result = model.run(model_input, context)

    assert result.outputs["stop_feeding"].value is True
    assert result.outputs["feed_waste_risk"].value == "high"
    assert "Stop feeding" in result.outputs["recommendation"].value


def test_feeding_satiety_rules_continue_for_active_feeding() -> None:
    model_input = ModelInput(
        model_code="FEEDING_SATIETY_RULES",
        inputs={
            "feeding_behavior_category": ModelInputValue(
                value="ACTIVE_CONTINUOUS_FEEDING",
                unit="category",
            ),
            "feed_remaining": ModelInputValue(value=False, unit="boolean"),
            "fish_reaction": ModelInputValue(value="Active", unit="text"),
        },
    )
    context = ModelRunContext(
        model_code="FEEDING_SATIETY_RULES",
        model_version="1.0.0",
        source_report="INFORME017",
    )

    result = FeedingSatietyRules().run(model_input, context)

    assert result.outputs["stop_feeding"].value is False
    assert result.outputs["feed_waste_risk"].value == "low"


def test_feeding_satiety_rules_reject_unsupported_category() -> None:
    model_input = ModelInput(
        model_code="FEEDING_SATIETY_RULES",
        inputs={
            "feeding_behavior_category": ModelInputValue(value="OTHER", unit="category"),
            "feed_remaining": ModelInputValue(value=False, unit="boolean"),
            "fish_reaction": ModelInputValue(value="Unknown", unit="text"),
        },
    )
    context = ModelRunContext(
        model_code="FEEDING_SATIETY_RULES",
        model_version="1.0.0",
        source_report="INFORME017",
    )

    with pytest.raises(ValueError, match="feeding_behavior_category"):
        FeedingSatietyRules().run(model_input, context)


def test_daily_ration_model_calculates_feed_percentage_and_amount() -> None:
    model_input = ModelInput(
        model_code="DAILY_RATION_MODEL",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        inputs={
            "feed_conversion_ratio": ModelInputValue(value=1.5, unit="ratio"),
            "daily_growth": ModelInputValue(value=0.2, unit="cm/day"),
            "fish_length": ModelInputValue(value=10.0, unit="cm"),
            "fish_weight": ModelInputValue(value=100.0, unit="g"),
        },
    )
    context = ModelRunContext(
        model_code="DAILY_RATION_MODEL",
        model_version="1.0.0",
        source_report="INFORME017",
    )

    result = DailyRationModel().run(model_input, context)

    assert result.outputs["feed_percentage_body_weight"].value == pytest.approx(9.0)
    assert result.outputs["feed_amount_g_day"].value == pytest.approx(9.0)
    assert result.unit_map["feed_amount_g_day"] == "g/day"


def test_daily_ration_model_validates_units() -> None:
    model_input = ModelInput(
        model_code="DAILY_RATION_MODEL",
        inputs={
            "feed_conversion_ratio": ModelInputValue(value=1.5, unit="ratio"),
            "daily_growth": ModelInputValue(value=0.2, unit="mm/day"),
            "fish_length": ModelInputValue(value=10.0, unit="cm"),
            "fish_weight": ModelInputValue(value=100.0, unit="g"),
        },
    )
    context = ModelRunContext(
        model_code="DAILY_RATION_MODEL",
        model_version="1.0.0",
        source_report="INFORME017",
    )

    with pytest.raises(ValueError, match="daily_growth"):
        DailyRationModel().run(model_input, context)


def test_daily_ration_model_requires_positive_length() -> None:
    model_input = ModelInput(
        model_code="DAILY_RATION_MODEL",
        inputs={
            "feed_conversion_ratio": ModelInputValue(value=1.5, unit="ratio"),
            "daily_growth": ModelInputValue(value=0.2, unit="cm/day"),
            "fish_length": ModelInputValue(value=0.0, unit="cm"),
            "fish_weight": ModelInputValue(value=100.0, unit="g"),
        },
    )
    context = ModelRunContext(
        model_code="DAILY_RATION_MODEL",
        model_version="1.0.0",
        source_report="INFORME017",
    )

    with pytest.raises(ValueError, match="fish_length"):
        DailyRationModel().run(model_input, context)
