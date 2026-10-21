"""Experimental ML rate forecast, with chronological cohort history and no writes."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models_engine.ml.adaptive_tilapia_growth import CODE, VERSION, predict_history, timestamp

router = APIRouter()


class SensorForecast(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    value: float
    issued_at: datetime
    trained_until: datetime
    valid_until: datetime
    model_version: str = Field(min_length=1)
    target_kind: Literal["next_24h_mean"] = "next_24h_mean"
    availability_mode: str = "provided_by_client"


class ObservedBiometry(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    observed_at: datetime
    mean_weight_g: float = Field(gt=0)
    available_at: datetime | None = None
    cohort_id: str | None = None


class AdaptiveGrowthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    cohort_id: str = Field(min_length=1, max_length=200)
    issued_at: datetime
    target_at: datetime
    biometries: list[ObservedBiometry] = Field(min_length=2, max_length=100)
    sensor_forecasts: dict[str, SensorForecast] = Field(default_factory=dict)
    inference_mode: Literal["current", "historical_replay"] = "current"


def artifact(request: Request) -> dict:
    found = getattr(request.app.state, "tilapia_adaptive_model", None)
    if found is not None:
        return found
    path = os.environ.get("TILAPIA_GROWTH_ADAPTIVE_ARTIFACT")
    if not path:
        raise HTTPException(503, "Adaptive ML artifact is not configured")
    try:
        raw = Path(path).read_bytes()
        model = json.loads(raw)
        if model.get("model_code") != CODE or model.get("model_version") != VERSION:
            raise ValueError("Unexpected model version")
        model["loaded_artifact_sha256"] = hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Adaptive ML artifact cannot be loaded") from exc
    request.app.state.tilapia_adaptive_model = model
    return model


@router.get("/models/tilapia-growth-adaptive/status")
def status(request: Request):
    a = artifact(request)
    return {k: a.get(k) for k in ["model_code", "model_version", "specification", "feature_names",
        "training_examples", "training_studies", "training_local_cutoff", "sensor_keys", "sensor_support",
        "validation_status", "source_quality", "production_ready", "available_at", "loaded_artifact_sha256"]}


@router.post("/models/tilapia-growth-adaptive/predict")
def forecast(body: AdaptiveGrowthRequest, request: Request):
    a = artifact(request)
    payload = body.model_dump(mode="json")
    try:
        issue = timestamp(payload["issued_at"])
        # Replay also needs an artifact that already existed at that issue time.
        # A refit made later cannot be relabeled as a historical prediction.
        if a.get("available_at") and issue < timestamp(a["available_at"]):
            raise ValueError("Artifact was not available at issue time; use the archived artifact")
        if body.inference_mode == "current":
            if (issue-datetime.now(timezone.utc)).total_seconds() > 60:
                raise ValueError("Current forecasts cannot be issued in the future")
            if any(f.availability_mode.startswith("historical") for f in body.sensor_forecasts.values()):
                raise ValueError("Historical sensor reconstruction cannot be presented as current")
        result = predict_history(a, payload)
        result.update(inference_mode=body.inference_mode, artifact_sha256=a.get("loaded_artifact_sha256"))
        return result
    except (ValueError, KeyError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc


def pond_history(pond_id: int, now: datetime) -> dict:
    from sqlalchemy import text
    from backend.app.core.config import get_settings
    from backend.app.core.database import engine
    schema = get_settings().legacy_database_name
    if not schema or not schema.replace("_", "").isalnum():
        raise ValueError("Invalid configured legacy database")
    today = now.astimezone(ZoneInfo("America/Lima")).date()
    with engine.connect() as conn:
        latest = conn.execute(text(f"""SELECT ce.campania_especie_id
            FROM {schema}.biometrias b JOIN {schema}.campania_etapas ce ON ce.id=b.campania_etapa_id
            WHERE b.deleted_at IS NULL AND ce.deleted_at IS NULL AND ce.piscina_id=:pond
            AND b.fecha_muestreo<=:today AND b.updated_at<=CURRENT_TIMESTAMP()
            ORDER BY b.fecha_muestreo DESC,b.id DESC LIMIT 1"""), {"pond": pond_id, "today": today}).scalar()
        if latest is None:
            raise ValueError("No observed biometry for this pond")
        rows = conn.execute(text(f"""SELECT b.id,b.fecha_muestreo,b.prom_peso_g,b.cantidad_muestreo,
            UNIX_TIMESTAMP(b.updated_at) available_epoch
            FROM {schema}.biometrias b JOIN {schema}.campania_etapas ce ON ce.id=b.campania_etapa_id
            WHERE b.deleted_at IS NULL AND ce.deleted_at IS NULL AND ce.piscina_id=:pond
            AND ce.campania_especie_id=:cohort AND b.fecha_muestreo<=:today
            AND b.updated_at<=CURRENT_TIMESTAMP()
            ORDER BY b.fecha_muestreo DESC,b.id DESC LIMIT 3"""),
            {"pond": pond_id, "cohort": latest, "today": today}).mappings().all()
        last_light = conn.execute(text(f"""SELECT MAX(fecha_medicion) last_record, COUNT(*) n,
            MIN(iluminancia) minimum_lux,MAX(iluminancia) maximum_lux,
            SUM(segundos_oscuridad=0) zero_darkness_counter
            FROM {schema}.parametro_ambientes WHERE piscina_id=:pond"""), {"pond": pond_id}).mappings().first()
    if len(rows) < 2:
        raise ValueError("Two observed biomet­ries from the same cohort are required")
    cohort = f"legacy:{schema}:pond:{pond_id}:campaign_species:{latest}"
    bios = [{"observed_at": datetime.combine(r["fecha_muestreo"], datetime.min.time(),
                tzinfo=ZoneInfo("America/Lima")).isoformat(), "mean_weight_g": float(r["prom_peso_g"]),
             "available_at": datetime.fromtimestamp(float(r["available_epoch"]), timezone.utc).isoformat(),
             "cohort_id": cohort} for r in reversed(rows)]
    return {"cohort_id": cohort, "biometries": bios, "biometry_ids": [r["id"] for r in reversed(rows)],
        "sample_sizes": [r["cantidad_muestreo"] for r in reversed(rows)],
        "sample_hour_assumption": "start_of_sample_day_America/Lima; actual sampling hour is not recorded",
        "light_inventory": {k: (v.isoformat() if isinstance(v, datetime) else int(v) if v is not None else None)
            for k, v in dict(last_light).items()},
        "sensor_clock_alignment_verified": False,
        "light_quality": "Darkness counter cannot establish photoperiod; nighttime offset requires physical verification"}


@router.get("/ponds/{pond_id}/models/tilapia-growth-adaptive/forecast")
def pond_forecast(pond_id: int, request: Request, projection_days: int = Query(default=7, ge=1, le=28)):
    if pond_id <= 0:
        raise HTTPException(422, "Positive pond identifier required")
    now = datetime.now(timezone.utc)
    try:
        ctx = pond_history(pond_id, now)
        body = AdaptiveGrowthRequest(cohort_id=ctx["cohort_id"], issued_at=now,
            target_at=now+timedelta(days=projection_days), biometries=ctx["biometries"])
        result = forecast(body, request)
        result.update(pond_id=pond_id, projection_days=projection_days, source_context=ctx)
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
