from backend.app.models_engine.base import BaseModelRunner
from backend.app.models_engine.bioenergetic import BioenergeticSparusAurataBrigolin2010
from backend.app.models_engine.feeding import DailyRationModel, FeedingSatietyRules
from backend.app.models_engine.mechanistic import DissolvedOxygen0DRoyer2021
from backend.app.models_engine.ml import BPNNMEAFeedIntake, PearsonLSTMAttentionWaterQuality
from backend.app.models_engine.vision import FishCountingModel, FishSizeWeightEstimation


def build_default_model_suite() -> list[BaseModelRunner]:
    return [
        DissolvedOxygen0DRoyer2021(),
        BioenergeticSparusAurataBrigolin2010(),
        FeedingSatietyRules(),
        DailyRationModel(),
        BPNNMEAFeedIntake(),
        PearsonLSTMAttentionWaterQuality(),
        FishCountingModel(),
        FishSizeWeightEstimation(),
    ]


def default_model_codes() -> list[str]:
    return [runner.model_code for runner in build_default_model_suite()]
