"""TILAPIA_INTERVAL_GROWTH_PILOT: interval supervision and causal exposure.

Research candidate, deliberately not registered as an active production runner.
An environmental forecast is an input, never a measured biological label.
The log-growth regression is an empirical benchmark, not a published physiological
equation and not evidence that environmental coefficients are causal.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODEL_CODE = "TILAPIA_INTERVAL_GROWTH_PILOT"
MODEL_VERSION = "0.1.0-research"


def _finite(value: float, name: str) -> float:
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite")
    return x


def _aware(t: datetime) -> None:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("timezone-aware timestamps are required")


@dataclass(frozen=True)
class EnvironmentalSegment:
    start: datetime
    end: datetime
    temperature_c: float
    do_mg_l: float
    kind: Literal["observed", "forecast"]
    available_at: datetime
    model_version: str | None = None
    trained_until: datetime | None = None

    def validate(self, issued_at: datetime) -> None:
        for t in (self.start, self.end, self.available_at, issued_at):
            _aware(t)
        if self.end <= self.start:
            raise ValueError("segment duration must be positive")
        if self.kind not in ("observed", "forecast"):
            raise ValueError("unknown segment kind")
        _finite(self.temperature_c, "temperature_c")
        if _finite(self.do_mg_l, "do_mg_l") < 0:
            raise ValueError("dissolved oxygen cannot be negative")
        if self.available_at > issued_at:
            raise ValueError("data was not available at forecast issue time")
        if self.kind == "observed" and self.end > issued_at:
            raise ValueError("future observations cannot be used for forecasting")
        if self.kind == "forecast":
            if not self.model_version or self.trained_until is None:
                raise ValueError("forecast requires model version and training cutoff")
            _aware(self.trained_until)
            if self.trained_until > self.available_at:
                raise ValueError("forecast model was trained after the forecast was available")


def interval_exposure(
    start: datetime,
    end: datetime,
    issued_at: datetime,
    segments: Sequence[EnvironmentalSegment],
    *,
    min_coverage: float = 0.95,
    thermal_base_c: float = 15.5,
    oxygen_threshold_mg_l: float = 3.0,
) -> dict[str, float]:
    """Duration-weighted features without filling gaps or inventing labels.

    Step-held concentrations are an explicit integration assumption. Thresholds
    define exposure summaries and are not universal physiological constants.
    """
    for t in (start, end, issued_at):
        _aware(t)
    if end <= start or not 0 < min_coverage <= 1:
        raise ValueError("invalid interval or minimum coverage")
    thermal_base_c = _finite(thermal_base_c, "thermal_base_c")
    oxygen_threshold_mg_l = _finite(oxygen_threshold_mg_l, "oxygen_threshold_mg_l")
    if oxygen_threshold_mg_l < 0:
        raise ValueError("oxygen threshold cannot be negative")
    duration_h = (end - start).total_seconds() / 3600
    covered_h = forecast_h = t_sum = do_sum = thermal = deficit = low_h = 0.0
    previous_end = start
    max_gap_h = 0.0
    for segment in sorted(segments, key=lambda s: s.start):
        a, b = max(start, segment.start), min(end, segment.end)
        if b <= a:
            continue
        segment.validate(issued_at)
        if a < previous_end:
            raise ValueError("overlapping environmental segments would double-count exposure")
        max_gap_h = max(max_gap_h, (a-previous_end).total_seconds()/3600)
        previous_end = b
        hours = (b-a).total_seconds()/3600
        covered_h += hours
        forecast_h += hours if segment.kind == "forecast" else 0
        t_sum += segment.temperature_c * hours
        do_sum += segment.do_mg_l * hours
        thermal += max(segment.temperature_c-thermal_base_c, 0) * hours
        deficit += max(oxygen_threshold_mg_l-segment.do_mg_l, 0) * hours
        low_h += hours if segment.do_mg_l < oxygen_threshold_mg_l else 0
    max_gap_h = max(max_gap_h, (end-previous_end).total_seconds()/3600)
    coverage = covered_h / duration_h
    if covered_h <= 0 or coverage + 1e-12 < min_coverage:
        raise ValueError(f"insufficient environmental coverage: {coverage:.3f}")
    return {
        "duration_days": duration_h/24,
        "coverage_fraction": coverage,
        "max_gap_hours": max_gap_h,
        "forecast_fraction": forecast_h/covered_h,
        "temperature_mean_c": t_sum/covered_h,
        "do_mean_mg_l": do_sum/covered_h,
        "degree_days_observed_support": thermal/24,
        "oxygen_deficit_mg_h_l": deficit,
        "hours_do_below_threshold": low_h,
    }


@dataclass(frozen=True)
class GrowthCovariates:
    study_id: str
    cohort_id: str
    duration_days: float
    initial_weight_g: float
    temperature_mean_c: float
    do_mean_mg_l: float
    source_reference: str

    def validate(self) -> None:
        if not self.study_id or not self.cohort_id or not self.source_reference:
            raise ValueError("study, cohort and source provenance are required")
        for key in ("duration_days", "initial_weight_g"):
            if _finite(getattr(self, key), key) <= 0:
                raise ValueError(f"{key} must be positive")
        _finite(self.temperature_mean_c, "temperature_mean_c")
        if _finite(self.do_mean_mg_l, "do_mean_mg_l") < 0:
            raise ValueError("dissolved oxygen cannot be negative")


@dataclass(frozen=True)
class GrowthTrainingInterval(GrowthCovariates):
    final_weight_g: float

    def validate(self) -> None:
        super().validate()
        if _finite(self.final_weight_g, "final_weight_g") <= 0:
            raise ValueError("final_weight_g must be positive")


class IntervalGrowthPilot:
    """Regularized interval log-growth regression; uncertainty is not calibrated.

    For the first external experiment, one tank supplies ONE 60-day target.
    Endpoint row numbers are not interpreted as tags. Ridge alpha is fixed before
    evaluation. It must be selected using nested grouped CV for a larger corpus.
    """
    def __init__(self, *, environmental: bool = True, alpha: float = 10.0):
        if not math.isfinite(alpha) or alpha <= 0:
            raise ValueError("positive finite ridge penalty required")
        self.environmental = environmental
        self.alpha = alpha

    def _x(self, rows: Sequence[GrowthCovariates]) -> np.ndarray:
        features = []
        for r in rows:
            r.validate()
            x = [math.log(r.initial_weight_g)]
            if self.environmental:
                x += [r.temperature_mean_c, r.do_mean_mg_l]
            features.append(x)
        return np.asarray(features, dtype=float)

    def fit(self, rows: Sequence[GrowthTrainingInterval]) -> "IntervalGrowthPilot":
        if len(rows) < 5:
            raise ValueError("at least five observed cohort intervals required for this pilot")
        x = self._x(rows)
        y = np.asarray([math.log(r.final_weight_g/r.initial_weight_g)/r.duration_days for r in rows])
        self.estimator_ = make_pipeline(StandardScaler(), Ridge(alpha=self.alpha))
        self.estimator_.fit(x, y)
        self.bounds_ = {
            key: (min(getattr(r,key) for r in rows), max(getattr(r,key) for r in rows))
            for key in ("duration_days", "initial_weight_g", "temperature_mean_c", "do_mean_mg_l")
        }
        self.study_count_ = len({r.study_id for r in rows})
        self.training_interval_count_ = len(rows)
        return self

    def predict(self, row: GrowthCovariates, *, allow_extrapolation: bool = False) -> dict[str, object]:
        if not hasattr(self, "estimator_"):
            raise ValueError("pilot has not been trained")
        row.validate()
        outside = [key for key,(lo,hi) in self.bounds_.items()
                   if getattr(row,key) < lo-1e-9 or getattr(row,key) > hi+1e-9]
        common = {"model_code": MODEL_CODE, "model_version": MODEL_VERSION,
                  "production_ready": False, "confidence": None,
                  "training_studies": self.study_count_,
                  "training_intervals": self.training_interval_count_,
                  "outside_training_range": outside,
                  "warning": "Research pilot; no validated local accuracy or calibrated prediction interval."}
        if outside and not allow_extrapolation:
            return {**common, "status": "out_of_training_domain", "weight_g": None}
        rate = float(self.estimator_.predict(self._x([row]))[0])
        log_weight = math.log(row.initial_weight_g)+rate*row.duration_days
        if not math.isfinite(log_weight) or log_weight > 700 or log_weight < -700:
            raise ValueError("unstable weight extrapolation")
        return {**common, "status": "research_extrapolation" if outside else "research_prediction",
                "weight_g": math.exp(log_weight), "log_growth_rate_per_day": rate}


def grouped_benchmark(
    rows: Sequence[GrowthTrainingInterval],
    groups: Sequence[str],
    *,
    environmental: bool,
) -> dict[str, object]:
    """Hold out complete studies/treatments; never split fish sharing a tank.

    Cross-study generalization exists only if groups actually denote studies.
    Extrapolated validation values are explicitly counted, not hidden.
    """
    if len(rows) != len(groups) or len(set(groups)) < 2:
        raise ValueError("at least two complete groups are required")
    predictions = []
    for group in sorted(set(groups)):
        train = [r for r,g in zip(rows,groups) if g != group]
        test = [r for r,g in zip(rows,groups) if g == group]
        model = IntervalGrowthPilot(environmental=environmental).fit(train)
        for r in test:
            p = model.predict(r, allow_extrapolation=True)
            predictions.append({"study_id":r.study_id, "cohort_id":r.cohort_id,
                "held_out_group":group, "observed_g":r.final_weight_g,
                "predicted_g":p["weight_g"], "outside_training_range":p["outside_training_range"]})
    errors = [p["predicted_g"]-p["observed_g"] for p in predictions]
    return {"n_intervals":len(predictions), "n_groups":len(set(groups)),
            "n_studies":len({r.study_id for r in rows}),
            "mae_g":float(np.mean(np.abs(errors))),
            "rmse_g":float(np.sqrt(np.mean(np.square(errors)))),
            "mape_pct":float(np.mean([100*abs(e)/p["observed_g"] for e,p in zip(errors,predictions)])),
            "extrapolated_intervals":sum(bool(p["outside_training_range"]) for p in predictions),
            "predictions":predictions, "production_ready":False}
