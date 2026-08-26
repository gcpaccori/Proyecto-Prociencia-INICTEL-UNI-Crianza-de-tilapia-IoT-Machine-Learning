"""Native, non-blocking contract for model-derived alerts.

The existing real-models dashboard deliberately does substantial local work: it
syncs MySQL observations, cleans them and evaluates the models.  That is the
right work for a background calculation, but not for a browser request that
also has to render the Laravel screen.  This service caches the resulting
contract and starts a refresh in a worker when necessary.  A cold request gets
an explicit ``warming`` response immediately instead of waiting for the full
calculation or timing out.

An event is emitted only when a local Laravel policy has been explicitly
approved and the corresponding model is genuinely eligible for production.
No threshold is fabricated here.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any, Callable

from sqlalchemy import text

from backend.app.application.real_models import RealModelsService


SVM_MODEL_CODE = "SVM_OD_FORECAST_1H"
GROWTH_MODEL_CODE = "TILAPIA_GROWTH_TEMPERATURE"
ICA_MODEL_CODE = "WATER_QUALITY_INDEX_ICA"
LIGHT_MODEL_CODE = "LIGHT_FEED_RESPONSE_CLASSIFIER_V1"

_CACHE_SECONDS = 120.0
_STALE_SECONDS = 1800.0
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="model-alerts")
_cache: dict[tuple[int, str, int], tuple[float, dict[str, Any]]] = {}
_inflight: set[tuple[int, str, int]] = set()
_cache_lock = Lock()


class ModelAlertDashboardService:
    """Adapt local model results to the Laravel alarm contract."""

    def __init__(
        self,
        store: object,
        dashboard_provider: Callable[[str, int], dict[str, Any]] | None = None,
    ) -> None:
        self.store = store
        self.dashboard_provider = dashboard_provider or self._calculate_dashboard

    def dashboard(self, pond_id: str, window_hours: int = 24) -> dict[str, Any]:
        """Return cached results immediately, refreshing expensive results off-thread."""
        key = (id(self.store), pond_id, window_hours)
        now = monotonic()

        with _cache_lock:
            cached = _cache.get(key)
            if cached and now - cached[0] <= _CACHE_SECONDS:
                return self._with_runtime_meta(cached[1], warming=False, stale=False)

            self._queue_refresh(key, pond_id, window_hours)
            if cached and now - cached[0] <= _STALE_SECONDS:
                return self._with_runtime_meta(cached[1], warming=True, stale=True)

        return self._warming_dashboard(pond_id, window_hours)

    def _queue_refresh(self, key: tuple[int, str, int], pond_id: str, window_hours: int) -> None:
        if key in _inflight:
            return
        _inflight.add(key)
        _executor.submit(self._refresh, key, pond_id, window_hours)

    def _refresh(self, key: tuple[int, str, int], pond_id: str, window_hours: int) -> None:
        try:
            calculated = self.dashboard_provider(pond_id, window_hours)
            policies = self._policies_for_pond(pond_id)
            payload = self.build_contract(calculated, pond_id, window_hours, policies)
            with _cache_lock:
                _cache[key] = (monotonic(), payload)
        except Exception:
            # Keep a bounded, explicit failure state.  Browser requests never need
            # the exception details, and the next refresh can recover normally.
            with _cache_lock:
                _cache[key] = (monotonic(), self._unavailable_dashboard(pond_id, window_hours))
        finally:
            with _cache_lock:
                _inflight.discard(key)

    def _calculate_dashboard(self, pond_id: str, window_hours: int) -> dict[str, Any]:
        return RealModelsService(self.store).dashboard(
            pond_id,
            window_hours=window_hours,
            growth_projection_days=7,
        )

    @classmethod
    def clear_cache(cls) -> None:
        with _cache_lock:
            _cache.clear()
            _inflight.clear()

    def build_contract(
        self,
        dashboard: dict[str, Any],
        pond_id: str,
        window_hours: int,
        policies: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a serialisable contract without changing model calculations."""
        policies = policies or {}
        raw_models = {
            str(model.get("code")): model
            for model in dashboard.get("models", [])
            if isinstance(model, dict) and model.get("code")
        }
        svm = raw_models.get(SVM_MODEL_CODE, {})
        growth = raw_models.get(GROWTH_MODEL_CODE, {})
        ica = raw_models.get(ICA_MODEL_CODE, {})
        light = self._light_context(pond_id, window_hours)

        cards = [
            self._ica_card(ica, policies.get(ICA_MODEL_CODE)),
            self._growth_card(growth, policies.get(GROWTH_MODEL_CODE)),
            self._svm_card(svm, dashboard, policies.get(SVM_MODEL_CODE)),
            self._light_card(light, policies.get(LIGHT_MODEL_CODE)),
        ]
        events = self._eligible_events(cards, pond_id)
        observations = self._technical_observations(dashboard)

        return {
            "schema_version": "1.0",
            "generated_at": self._iso_now(),
            "pond_id": pond_id,
            "summary": {
                "active_events": len(events),
                "can_emit": sum(1 for card in cards if card["can_emit"]),
                "shadow": sum(1 for card in cards if card["maturity"] == "shadow"),
                "blocked": sum(
                    1
                    for card in cards
                    if card["maturity"] in {"blocked_inputs", "collecting_data"}
                ),
                "technical_observations": len(observations),
            },
            "models": cards,
            "events": events,
            "technical_observations": observations,
            "light": light,
            "meta": {
                "source": "fastapi_model_alert_contract",
                "computed_at": self._iso_now(),
                "window_hours": window_hours,
                "warming": False,
                "stale": False,
                "degraded": False,
                "message": "Resultados calculados localmente con MySQL y FastAPI de la misma maquina virtual.",
            },
        }

    def _ica_card(self, model: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
        calculated = model.get("status") == "calculado"
        return self._card(
            code=ICA_MODEL_CODE,
            alarm_code="MODEL_ICA_DEGRADATION",
            name="Indice de calidad de agua",
            purpose="Resume temperatura, pH, oxigeno disuelto e ion nitrato para vigilar el deterioro de la calidad del agua.",
            horizon="Estado actual",
            inputs=["Temperatura", "pH", "Oxigeno disuelto", "Ion nitrato"],
            model=model,
            policy=policy,
            eligible=calculated,
            unavailable_detail="Faltan lecturas limpias simultaneas para calcular el ICA.",
            eligible_detail="El ICA se calcula con las lecturas reales; una politica aprobada decide si debe notificar.",
            prediction_value=self._number(model.get("current_value")),
            prediction_for=model.get("traceability", {}).get("latest_timestamp") if isinstance(model.get("traceability"), dict) else None,
        )

    def _growth_card(self, model: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
        has_projection = bool(model.get("forecast")) and model.get("status") == "calculado"
        card = self._card(
            code=GROWTH_MODEL_CODE,
            alarm_code="MODEL_GROWTH_DEVIATION",
            name="Crecimiento de tilapia por temperatura",
            purpose="Proyecta la ganancia diaria y la biometria esperada a partir de la temperatura medida.",
            horizon="1 a 365 dias",
            inputs=["Temperatura", "Longitud", "Peso", "Fecha de biometria"],
            model=model,
            policy=policy,
            eligible=False,
            unavailable_detail="Faltan temperatura valida o biometria para contrastar la trayectoria.",
            eligible_detail="La proyeccion queda en modo sombra hasta validar una banda local de error con biometria real.",
            prediction_value=self._number(model.get("current_value")),
            prediction_for=None,
        )
        card["maturity"] = "shadow" if has_projection else "blocked_inputs"
        card["can_emit"] = False
        card["status_detail"] = (
            "La proyeccion esta disponible para revision tecnica; todavia no puede emitir una alarma."
            if has_projection
            else card["status_detail"]
        )
        return card

    def _svm_card(
        self,
        model: dict[str, Any],
        dashboard: dict[str, Any],
        policy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        forecast = dashboard.get("svm_od_forecast", {})
        if not isinstance(forecast, dict):
            forecast = {}
        active_asset = model.get("status") == "asset_activo" and bool(
            (dashboard.get("ai_model") or {}).get("productive")
        )
        prediction = self._number(forecast.get("forecast_do_mg_l"))
        card = self._card(
            code=SVM_MODEL_CODE,
            alarm_code="MODEL_OD_THRESHOLD_FORECAST",
            name="Cruce futuro de oxigeno disuelto",
            purpose="Estima el oxigeno disuelto a una hora con una SVR entrenada sobre temperatura, pH, OD e ion nitrato.",
            horizon="1 hora",
            inputs=["Temperatura", "pH", "Oxigeno disuelto", "Ion nitrato", "Historial temporal"],
            model=model,
            policy=policy,
            eligible=active_asset and prediction is not None,
            unavailable_detail="El artefacto SVM permanece en evaluacion tecnica o no tiene una proyeccion valida.",
            eligible_detail="El artefacto activo puede notificar solo cuando la politica aprobada detecta un cruce futuro.",
            prediction_value=prediction,
            prediction_for=forecast.get("target_time"),
        )
        card["asset_id"] = forecast.get("asset_id") or card.get("asset_id")
        card["version"] = forecast.get("asset_version") or card.get("version")
        card["metrics"] = forecast.get("metrics") or card.get("metrics", {})
        return card

    def _light_card(self, light: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
        sensor_registered = bool(light.get("sensor_registered"))
        card = self._card(
            code=LIGHT_MODEL_CODE,
            alarm_code="MODEL_LIGHT_FEED_RESPONSE_RISK",
            name="Luz y respuesta alimentaria",
            purpose="Preparara una prediccion de respuesta alimentaria con luz subacuatica, fotoperiodo y contexto del agua.",
            horizon="Siguiente evento de alimentacion",
            inputs=["Luz subacuatica", "Fotoperiodo", "Hora", "OD", "Temperatura", "Racion", "Respuesta observada"],
            model={
                "status": "collecting_data" if sensor_registered else "sin_sensor",
                "current_value": light.get("latest_value"),
                "unit": light.get("unit", "lux"),
                "chart": light.get("chart"),
                "formula": {
                    "latex": r"P(\\mathrm{consumo})=f(\\mathrm{lux},\\mathrm{fotoperiodo},OD,T,\\mathrm{racion})",
                    "detail": "La formula representa el futuro clasificador; no existe un artefacto entrenado ni una prediccion productiva mientras falten etiquetas reales de consumo.",
                },
                "usage": {
                    "status": "collecting_data",
                    "label": "Recopilacion de evidencia",
                    "detail": "El sensor de luz debe registrar lecturas vinculadas a racion y respuesta alimentaria antes de entrenar.",
                },
            },
            policy=policy,
            eligible=False,
            unavailable_detail="No hay un sensor de luz disponible en esta piscina.",
            eligible_detail="Hay sensor de luz, pero faltan etiquetas de consumo o remanente para entrenar y validar el modelo.",
            prediction_value=self._number(light.get("latest_value")),
            prediction_for=light.get("latest_at"),
        )
        card["maturity"] = "collecting_data" if sensor_registered else "blocked_inputs"
        card["can_emit"] = False
        return card

    def _card(
        self,
        *,
        code: str,
        alarm_code: str,
        name: str,
        purpose: str,
        horizon: str,
        inputs: list[str],
        model: dict[str, Any],
        policy: dict[str, Any] | None,
        eligible: bool,
        unavailable_detail: str,
        eligible_detail: str,
        prediction_value: float | None,
        prediction_for: str | None,
    ) -> dict[str, Any]:
        policy_payload = self._policy_payload(policy)
        can_emit = eligible and policy_payload["status"] == "approved"
        model_status = str(model.get("status") or "sin_datos")
        missing_inputs = [] if eligible else list(inputs)
        if eligible:
            maturity = "active" if can_emit else "ready_for_policy"
            detail = eligible_detail if can_emit else "El modelo esta listo, pero no existe una politica aprobada que convierta su salida en alarma."
        else:
            maturity = "blocked_inputs"
            detail = unavailable_detail

        return {
            "code": code,
            "alarm_code": alarm_code,
            "name": name,
            "purpose": purpose,
            "maturity": maturity,
            "can_emit": can_emit,
            "alarm_state": "enabled" if can_emit else "not_enabled",
            "status_detail": detail,
            "horizon": horizon,
            "inputs": inputs,
            "missing_inputs": missing_inputs,
            "current_value": model.get("current_value"),
            "unit": model.get("unit"),
            "data_timestamp": prediction_for,
            "prediction_value": prediction_value,
            "prediction_for": prediction_for,
            "model_status": model_status,
            "asset_id": model.get("asset_id"),
            "version": model.get("version"),
            "metrics": model.get("metrics") or {},
            "projection": {
                "available": bool(model.get("chart")),
                "chart": model.get("chart"),
                "forecast": model.get("forecast") or [],
                "description": model.get("chart_description"),
            },
            "relationship": model.get("relationship"),
            "formula": model.get("formula"),
            "usage": model.get("usage"),
            "traceability": model.get("traceability"),
            "policy": policy_payload,
        }

    def _eligible_events(self, cards: list[dict[str, Any]], pond_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for card in cards:
            if not card["can_emit"]:
                continue
            policy = card["policy"]
            value = card.get("prediction_value")
            if value is None or not self._matches_policy(float(value), policy):
                continue
            event_id = self._event_id(card, pond_id, value)
            severity = policy["severity"]
            prediction_for = card.get("prediction_for") or self._iso_now()
            events.append(
                {
                    "id": event_id,
                    "source_event_id": event_id,
                    "event_type": "triggered",
                    "productive": True,
                    "occurred_at": self._iso_now(),
                    "pond_id": pond_id,
                    "alarm_code": card["alarm_code"],
                    "title": f"{card['name']}: condicion {severity}",
                    "message": (
                        f"El resultado {value:g} {card.get('unit') or ''} cumple la politica aprobada "
                        f"{policy['condition']} para {card['name']}."
                    ).strip(),
                    "suggested_severity": severity,
                    "predicted_value": value,
                    "prediction_for": prediction_for,
                    "horizon_minutes": self._horizon_minutes(card["code"]),
                    "model": {
                        "code": card["code"],
                        "version": card.get("version"),
                        "asset_id": card.get("asset_id"),
                    },
                    "policy": {"code": policy["code"]},
                    "evidence": {
                        "formula": (card.get("formula") or {}).get("latex"),
                        "model_status": card.get("model_status"),
                        "projection_for": prediction_for,
                        "policy": policy,
                    },
                }
            )
        return events

    def _technical_observations(self, dashboard: dict[str, Any]) -> list[dict[str, Any]]:
        warnings = dashboard.get("warnings") or []
        observations: list[dict[str, Any]] = []
        for warning in warnings:
            if not warning:
                continue
            observations.append(
                {
                    "kind": "model_runtime_observation",
                    "message": str(warning),
                    "productive": False,
                }
            )
        return observations

    def _warming_dashboard(self, pond_id: str, window_hours: int) -> dict[str, Any]:
        models = [
            self._warming_card(ICA_MODEL_CODE, "MODEL_ICA_DEGRADATION", "Indice de calidad de agua", "Estado actual"),
            self._warming_card(GROWTH_MODEL_CODE, "MODEL_GROWTH_DEVIATION", "Crecimiento de tilapia por temperatura", "1 a 365 dias"),
            self._warming_card(SVM_MODEL_CODE, "MODEL_OD_THRESHOLD_FORECAST", "Cruce futuro de oxigeno disuelto", "1 hora"),
            self._warming_card(LIGHT_MODEL_CODE, "MODEL_LIGHT_FEED_RESPONSE_RISK", "Luz y respuesta alimentaria", "Siguiente evento de alimentacion"),
        ]
        return {
            "schema_version": "1.0",
            "generated_at": self._iso_now(),
            "pond_id": pond_id,
            "summary": {"active_events": 0, "can_emit": 0, "shadow": 0, "blocked": 0, "technical_observations": 0},
            "models": models,
            "events": [],
            "technical_observations": [],
            "light": self._empty_light_context(),
            "meta": {
                "source": "fastapi_model_alert_contract",
                "warming": True,
                "stale": False,
                "degraded": False,
                "window_hours": window_hours,
                "message": "FastAPI esta preparando los calculos locales; la pantalla se actualizara automaticamente.",
            },
        }

    def _unavailable_dashboard(self, pond_id: str, window_hours: int) -> dict[str, Any]:
        payload = self._warming_dashboard(pond_id, window_hours)
        payload["meta"] = {
            "source": "fastapi_model_alert_contract",
            "warming": False,
            "stale": False,
            "degraded": True,
            "window_hours": window_hours,
            "message": "FastAPI no pudo completar el calculo local. Se reintentara automaticamente sin generar alarmas.",
        }
        for card in payload["models"]:
            card["maturity"] = "blocked_inputs"
            card["model_status"] = "unavailable"
            card["status_detail"] = "No se completo el calculo local; no se emitira ninguna alarma hasta disponer de evidencia valida."
        return payload

    @staticmethod
    def _warming_card(code: str, alarm_code: str, name: str, horizon: str) -> dict[str, Any]:
        return {
            "code": code,
            "alarm_code": alarm_code,
            "name": name,
            "purpose": "Preparando evidencia local para este modelo.",
            "maturity": "candidate",
            "can_emit": False,
            "alarm_state": "warming",
            "status_detail": "El calculo se ejecuta en segundo plano; aun no hay una decision de alarma.",
            "horizon": horizon,
            "inputs": [],
            "missing_inputs": [],
            "current_value": None,
            "unit": None,
            "data_timestamp": None,
            "prediction_value": None,
            "prediction_for": None,
            "model_status": "warming",
            "asset_id": None,
            "version": None,
            "metrics": {},
            "projection": {"available": False, "chart": None, "forecast": [], "description": None},
            "relationship": None,
            "formula": None,
            "usage": None,
            "traceability": None,
            "policy": {"code": None, "status": "draft", "condition": "Pendiente de lectura de politica aprobada.", "severity": None},
        }

    def _light_context(self, pond_id: str, window_hours: int) -> dict[str, Any]:
        try:
            sensors = self.store.list_sensors(pond_id)
        except Exception:
            sensors = []
        matches = []
        for sensor in sensors:
            variable_code = str(getattr(sensor, "variable_code", "")).lower()
            sensor_code = str(getattr(sensor, "sensor_code", "")).lower()
            if any(token in f"{variable_code} {sensor_code}" for token in ("lux", "illumin", "light", "ppfd")):
                matches.append(sensor)

        try:
            measurements = self.store.list_clean_measurements(pond_id, limit=10000)
        except Exception:
            measurements = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        observations: list[tuple[str, float, str]] = []
        for measurement in measurements:
            variable_code = str(self._field(measurement, "variable_code") or "").lower()
            if not any(token in variable_code for token in ("lux", "illumin", "light", "ppfd")):
                continue
            value = self._number(self._field(measurement, "clean_value"))
            timestamp = self._value_to_iso(self._field(measurement, "time"))
            if value is None or timestamp is None:
                continue
            observed_at = self._parse_datetime(timestamp)
            if observed_at and observed_at < cutoff:
                continue
            observations.append((timestamp, value, str(self._field(measurement, "standard_unit") or "lux")))
        observations.sort(key=lambda row: row[0])
        latest = observations[-1] if observations else None
        unit = latest[2] if latest else "lux"

        return {
            "sensor_registered": bool(matches or observations),
            "sensor_codes": [str(getattr(sensor, "sensor_code", "")) for sensor in matches],
            "observation_count": len(observations),
            "latest_value": latest[1] if latest else None,
            "latest_at": latest[0] if latest else None,
            "unit": unit,
            "chart": self._light_chart(observations, unit),
            "alarm": {
                "status": "not_emitted",
                "can_emit": False,
                "message": "La luz no genera una alarma hasta contar con un modelo entrenado, datos etiquetados y una politica aprobada.",
            },
        }

    @staticmethod
    def _empty_light_context() -> dict[str, Any]:
        return {
            "sensor_registered": False,
            "sensor_codes": [],
            "observation_count": 0,
            "latest_value": None,
            "latest_at": None,
            "unit": "lux",
            "chart": ModelAlertDashboardService._light_placeholder_chart(),
            "alarm": {
                "status": "not_emitted",
                "can_emit": False,
                "message": "La disponibilidad del sensor se comprobara cuando termine la actualizacion.",
            },
        }

    @staticmethod
    def _light_placeholder_chart() -> dict[str, Any]:
        return {
            "title": {"text": "Lecturas de luz pendientes"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "time"},
            "yAxis": {"type": "value", "name": "lux"},
            "series": [],
        }

    @staticmethod
    def _light_chart(observations: list[tuple[str, float, str]], unit: str) -> dict[str, Any]:
        if not observations:
            return ModelAlertDashboardService._light_placeholder_chart()
        return {
            "title": {"text": "Luz subacuatica observada"},
            "tooltip": {"trigger": "axis"},
            "dataZoom": [{"type": "inside"}, {"type": "slider"}],
            "xAxis": {"type": "time"},
            "yAxis": {"type": "value", "name": unit},
            "series": [
                {
                    "name": "Luz observada",
                    "type": "line",
                    "showSymbol": False,
                    "smooth": True,
                    "lineStyle": {"width": 2, "color": "#f59e0b"},
                    "itemStyle": {"color": "#f59e0b"},
                    "data": [[timestamp, value] for timestamp, value, _ in observations],
                }
            ],
        }

    def _policies_for_pond(self, pond_id: str) -> dict[str, dict[str, Any]]:
        """Read Laravel-owned policies without making the backend own their table."""
        engine = getattr(self.store, "engine", None)
        legacy_database = getattr(self.store, "legacy_database_name", None)
        if engine is None or not legacy_database:
            return {}
        pond_number = self._pond_number(pond_id)
        if pond_number is None:
            return {}
        safe_database = str(legacy_database).replace("`", "``")
        try:
            with engine.connect() as connection:
                exists = connection.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = :database_name AND TABLE_NAME = 'model_alert_policies'
                        LIMIT 1
                        """
                    ),
                    {"database_name": legacy_database},
                ).scalar()
                if not exists:
                    return {}
                rows = connection.execute(
                    text(
                        f"""
                        SELECT code, model_code, piscina_id, status, `operator`, threshold,
                               unit, severity, version, approved_at, rationale, updated_at
                        FROM `{safe_database}`.`model_alert_policies`
                        WHERE piscina_id IS NULL OR piscina_id = :piscina_id
                        ORDER BY (piscina_id IS NOT NULL) DESC, updated_at DESC
                        """
                    ),
                    {"piscina_id": pond_number},
                ).mappings().all()
        except Exception:
            return {}

        policies: dict[str, dict[str, Any]] = {}
        for row in rows:
            model_code = str(row.get("model_code") or "")
            if model_code and model_code not in policies:
                policies[model_code] = dict(row)
        return policies

    @staticmethod
    def _policy_payload(policy: dict[str, Any] | None) -> dict[str, Any]:
        if not policy:
            return {
                "code": None,
                "status": "draft",
                "condition": "No existe una politica aprobada para este modelo.",
                "severity": None,
                "operator": None,
                "threshold": None,
                "unit": None,
            }
        operator = str(policy.get("operator") or "")
        threshold = ModelAlertDashboardService._number(policy.get("threshold"))
        unit = str(policy.get("unit") or "")
        condition = (
            f"{operator} {threshold:g} {unit}".strip()
            if threshold is not None and operator
            else "Politica sin condicion valida."
        )
        return {
            "code": policy.get("code"),
            "status": str(policy.get("status") or "draft"),
            "condition": condition,
            "severity": policy.get("severity"),
            "operator": operator,
            "threshold": threshold,
            "unit": unit,
            "version": policy.get("version"),
            "approved_at": ModelAlertDashboardService._value_to_iso(policy.get("approved_at")),
            "rationale": policy.get("rationale"),
        }

    @staticmethod
    def _matches_policy(value: float, policy: dict[str, Any]) -> bool:
        threshold = ModelAlertDashboardService._number(policy.get("threshold"))
        operator = policy.get("operator")
        if threshold is None:
            return False
        return {
            "lt": value < threshold,
            "lte": value <= threshold,
            "gt": value > threshold,
            "gte": value >= threshold,
        }.get(operator, False)

    @staticmethod
    def _event_id(card: dict[str, Any], pond_id: str, value: float) -> str:
        material = "|".join(
            [
                pond_id,
                card["code"],
                str(card["policy"].get("code") or ""),
                str(card.get("prediction_for") or ""),
                f"{value:.5f}",
            ]
        )
        return f"MODEL-{sha256(material.encode('utf-8')).hexdigest()[:40]}"

    @staticmethod
    def _horizon_minutes(model_code: str) -> int | None:
        return {SVM_MODEL_CODE: 60, ICA_MODEL_CODE: 0}.get(model_code)

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if numeric == numeric else None

    @staticmethod
    def _pond_number(pond_id: str) -> int | None:
        suffix = pond_id.removeprefix("LEGACY-POND-")
        return int(suffix) if suffix.isdigit() else None

    @staticmethod
    def _value_to_iso(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value else None

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        return value.get(name) if isinstance(value, dict) else getattr(value, name, None)

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _with_runtime_meta(payload: dict[str, Any], *, warming: bool, stale: bool) -> dict[str, Any]:
        result = dict(payload)
        meta = dict(result.get("meta") or {})
        meta.update(
            {
                "warming": warming,
                "stale": stale,
                "degraded": False,
                "message": (
                    "Se muestra el ultimo calculo local mientras FastAPI actualiza la evidencia."
                    if stale
                    else meta.get("message")
                ),
            }
        )
        result["meta"] = meta
        return result
