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

import time

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
PHOTOPERIOD_MODEL_CODE = "PHOTOPERIOD_GREENHOUSE_V1"
CONDITION_MODEL_CODE = "TILAPIA_WEIGHT_LENGTH_ML"
LIGHT_FORECAST_MODEL_CODE = "LIGHT_FORECAST_SVR_12H"

_CACHE_SECONDS = 120.0
_STALE_SECONDS = 1800.0

# Laravel guarda created_at/updated_at en la hora de la piscigranja
# (app.timezone = America/Lima), sin marca de zona. MySQL en cambio corre en
# UTC. Si se lee una de esas fechas como si fuera UTC, todo dato parece cinco
# horas mas viejo de lo que es y una lectura de hace diez minutos se anuncia
# como de hace cinco horas. Se declara la zona real para no restar de mas.
_TZ_LOCAL = ZoneInfo("America/Lima")


def _asumir_hora_local(momento: datetime) -> datetime:
    """Una fecha sin zona viene de la base: es hora local, no UTC."""
    return momento.replace(tzinfo=_TZ_LOCAL) if momento.tzinfo is None else momento
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
            # Un mes: con 7 dias la curva de peso es casi una recta y no se ve.
            growth_projection_days=30,
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
        photoperiod = self._photoperiod_context(pond_id, window_hours)
        self._source_dates = self._source_freshness(pond_id)

        cards = [
            self._ica_card(ica, policies.get(ICA_MODEL_CODE)),
            self._growth_card(growth, policies.get(GROWTH_MODEL_CODE)),
            self._svm_card(svm, dashboard, policies.get(SVM_MODEL_CODE)),
            self._light_card(light, policies.get(LIGHT_MODEL_CODE)),
            self._photoperiod_card(photoperiod, policies.get(PHOTOPERIOD_MODEL_CODE)),
            self._condition_card(growth, policies.get(CONDITION_MODEL_CODE)),
            self._light_forecast_card(pond_id, policies.get(LIGHT_FORECAST_MODEL_CODE)),
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
            "photoperiod": photoperiod,
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
            eligible=has_projection,
            unavailable_detail="Faltan temperatura valida o biometria para contrastar la trayectoria.",
            eligible_detail=(
                "Proyecta la ganancia diaria con la ecuacion de Soderberg y la biometria real. "
                "Revisa la antiguedad del dato antes de tomar una decision."
            ),
            prediction_value=self._number(model.get("current_value")),
            prediction_for=None,
        )
        if not has_projection:
            card["maturity"] = "blocked_inputs"
            card["can_emit"] = False
        return card

    def _condition_card(
        self, growth: dict[str, Any], policy: dict[str, Any] | None
    ) -> dict[str, Any]:
        """El unico modelo entrenado con peces de esta piscigranja, como alarma.

        La curva W = a*L^b se ajusta con biometria_detalles y se valida fuera de
        muestra. Aqui se le da la vuelta: en vez de predecir el peso, se usa
        para juzgar el que se midio. Un lote que pesa bastante menos de lo que
        su talla promete es una senal temprana, y aparece antes de que la
        longitud media se resienta.
        """
        condicion = (growth or {}).get("body_condition") or {}
        entrenado = ((growth or {}).get("traceability") or {}).get("weight_length_ml")
        listo = bool(condicion) and bool(entrenado)

        kn = condicion.get("condition_factor")
        modelo = {
            "current_value": kn,
            "unit": "x lo esperado",
            "status": "calculado" if listo else "sin_datos",
            "asset_id": None,
            "version": None,
        }

        card = self._card(
            code=CONDITION_MODEL_CODE,
            alarm_code="MODEL_CONDITION_DEVIATION",
            name="Condicion corporal frente a la curva entrenada",
            purpose=(
                "Compara el peso medido de cada pez con el que predice la curva "
                "peso-longitud ajustada con los peces de esta piscigranja."
            ),
            horizon="Ultimo muestreo",
            inputs=["Longitud por pez", "Peso por pez", "Fecha de biometria"],
            model=modelo,
            policy=policy,
            eligible=listo,
            unavailable_detail=(
                "Hacen falta al menos ocho peces medidos uno a uno en el ultimo "
                "muestreo, y una curva entrenada con la que compararlos."
            ),
            eligible_detail=(
                "Avisa cuando el lote se aparta de la curva propia mas de un 10%. "
                "Por debajo suele ser alimentacion o competencia; por encima, "
                "conviene revisar como se esta midiendo la longitud."
            ),
            prediction_value=self._number(kn),
            prediction_for=condicion.get("sampled_at"),
        )
        if listo:
            card["body_condition"] = condicion
            card["traceability"] = {**(card.get("traceability") or {}),
                                    "weight_length_ml": entrenado}
        else:
            card["maturity"] = "collecting_data"
            card["can_emit"] = False
        return card

    def _light_rows(self, pond_id: str) -> list[dict[str, Any]]:
        """Historial completo de ambiente, que es lo que necesita el entrenamiento."""
        engine = getattr(self.store, "engine", None)
        legacy = getattr(self.store, "legacy_database_name", None)
        pond_number = self._pond_number(pond_id)
        if engine is None or not legacy or pond_number is None:
            return []
        safe = str(legacy).replace("`", "``")
        try:
            with engine.connect() as connection:
                filas = connection.execute(
                    text(
                        f"""
                        SELECT fecha_medicion, iluminancia, temperatura_ambiente, humedad_ambiente
                        FROM `{safe}`.`parametro_ambientes`
                        WHERE piscina_id = :piscina_id AND iluminancia IS NOT NULL
                        ORDER BY fecha_medicion ASC
                        """
                    ),
                    {"piscina_id": pond_number},
                ).mappings().all()
        except Exception:
            return []
        return [dict(fila) for fila in filas]

    def _light_forecast_card(
        self, pond_id: str, policy: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Prevision de luz a doce horas, entrenada con el propio vivero.

        Se queda en sombra a proposito: le gana a la persistencia y a la media
        horaria, pero se entreno con nueve dias de sensor. Calcula y se deja
        ver; no dispara nada hasta que haya historial suficiente para fiarse.
        """
        from backend.app.models_engine.ml.light_forecast import (
            predict_next_light,
            train_light_forecast_model,
        )

        filas = self._light_rows(pond_id)
        entrenado = train_light_forecast_model(filas) if filas else None
        prevision = predict_next_light(entrenado, filas) if entrenado else None
        listo = bool(entrenado and prevision and entrenado.get("beats_baselines"))

        modelo = {
            "current_value": prevision.get("predicted_lux") if prevision else None,
            "unit": "lux",
            "status": "calculado" if listo else "sin_datos",
            "asset_id": None,
            "version": None,
        }
        card = self._card(
            code=LIGHT_FORECAST_MODEL_CODE,
            alarm_code="MODEL_LIGHT_FORECAST_DEFICIT",
            name="Prevision de luz a 12 horas",
            purpose=(
                "Anticipa la iluminancia dentro del vivero doce horas por delante, "
                "para saber de noche si manana temprano habra luz para alimentar."
            ),
            horizon="12 horas",
            inputs=["Iluminancia", "Temperatura ambiente", "Humedad ambiente", "Hora del dia"],
            model=modelo,
            policy=policy,
            eligible=False,
            unavailable_detail=(
                "Necesita al menos ciento cincuenta ventanas completas de sensor para entrenarse."
            ),
            eligible_detail="",
            prediction_value=prevision.get("predicted_lux") if prevision else None,
            prediction_for=prevision.get("for_at") if prevision else None,
        )
        if listo:
            card["maturity"] = "shadow"
            card["status_detail"] = (
                "Calcula y se puede contrastar, pero todavia no dispara alarmas: "
                "se entreno con nueve dias de sensor y hace falta mas historial."
            )
            card["missing_inputs"] = []
            card["traceability"] = {
                **(card.get("traceability") or {}),
                "light_forecast_ml": {
                    k: v for k, v in entrenado.items() if k != "modelo"
                },
            }
            card["light_forecast"] = prevision
        else:
            card["maturity"] = "collecting_data"
        card["can_emit"] = False
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
            purpose="Relaciona la luz subacuatica medida, el fotoperiodo y el estado del agua con la respuesta a la alimentacion.",
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
            unavailable_detail=(
                # El luxometro si existe: lo que falta para entrenar es la otra
                # mitad del par, saber cuanto se les echo y cuanto comieron.
                "Hay lecturas de luz, pero el clasificador necesita ademas la racion "
                "servida y la respuesta observada para poder entrenarse."
                if sensor_registered
                else "No hay un sensor de luz disponible en esta piscina."
            ),
            eligible_detail="Hay sensor de luz, pero faltan etiquetas de consumo o remanente para entrenar y validar el modelo.",
            prediction_value=self._number(light.get("latest_value")),
            prediction_for=light.get("latest_at"),
        )
        card["maturity"] = "collecting_data" if sensor_registered else "blocked_inputs"
        card["can_emit"] = False
        if sensor_registered:
            # Con el luxometro dando lecturas, lo unico que falta de verdad es
            # la etiqueta: cuanto se sirvio y como respondieron los peces.
            card["missing_inputs"] = ["Racion", "Respuesta observada"]
        return card


    # ------------------------------------------------------------------
    # Fotoperiodo de vivero: sensor interior contra luz natural de Open-Meteo
    # ------------------------------------------------------------------
    _photoperiod_outdoor_cache: dict[tuple[float, float], tuple[float, Any]] = {}

    def _photoperiod_context(self, pond_id: str, window_hours: int) -> dict[str, Any]:
        from backend.app.models_engine.deterministic import photoperiod as pp

        empty = {
            "available": False,
            "reason": "No hay lecturas de iluminancia para esta piscina.",
        }
        engine = getattr(self.store, "engine", None)
        legacy_database = getattr(self.store, "legacy_database_name", None)
        pond_number = self._pond_number(pond_id)
        if engine is None or not legacy_database or pond_number is None:
            return empty
        safe = str(legacy_database).replace("`", "``")

        try:
            with engine.connect() as connection:
                exists = connection.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'parametro_ambientes' LIMIT 1
                        """
                    ),
                    {"db": legacy_database},
                ).scalar()
                if not exists:
                    return empty
                rows = connection.execute(
                    text(
                        f"""
                        SELECT fecha_medicion, iluminancia
                        FROM `{safe}`.`parametro_ambientes`
                        WHERE piscina_id = :piscina_id AND iluminancia IS NOT NULL
                        ORDER BY fecha_medicion DESC
                        LIMIT 2000
                        """
                    ),
                    {"piscina_id": pond_number},
                ).mappings().all()
                coords = connection.execute(
                    text(
                        f"""
                        SELECT g.latitud, g.longitud, g.nombre
                        FROM `{safe}`.`piscinas` p
                        JOIN `{safe}`.`piscigranjas` g ON g.id = p.piscigranja_id
                        WHERE p.id = :piscina_id LIMIT 1
                        """
                    ),
                    {"piscina_id": pond_number},
                ).mappings().first()
        except Exception:
            return empty

        observations = []
        for row in rows:
            moment = row.get("fecha_medicion")
            value = row.get("iluminancia")
            if moment is None or value is None:
                continue
            try:
                observations.append((moment, float(value)))
            except (TypeError, ValueError):
                continue
        if not observations:
            return empty

        try:
            indoor = pp.build_indoor_profile(observations, window_hours=max(72, window_hours))
        except pp.PhotoperiodDataUnavailable as error:
            return {"available": False, "reason": str(error)}

        outdoor = None
        outdoor_error = None
        try:
            latitude = float(coords["latitud"]) if coords and coords.get("latitud") else None
            longitude = float(coords["longitud"]) if coords and coords.get("longitud") else None
        except (TypeError, ValueError):
            latitude = longitude = None
        if latitude is not None and longitude is not None:
            key = (round(latitude, 4), round(longitude, 4))
            cached = self._photoperiod_outdoor_cache.get(key)
            now = time.time()
            if cached and now - cached[0] < 3600.0:
                outdoor = cached[1]
            else:
                try:
                    outdoor = pp.fetch_outdoor_reference(latitude, longitude)
                    self._photoperiod_outdoor_cache[key] = (now, outdoor)
                except Exception as error:  # la API externa nunca debe tumbar el panel
                    outdoor_error = f"{type(error).__name__}: {error}"
                    if cached:
                        outdoor = cached[1]

        assessment = pp.assess(indoor, outdoor)
        return {
            "available": True,
            "farm": (coords or {}).get("nombre"),
            "latitude": latitude,
            "longitude": longitude,
            "indoor": {
                "readings": indoor.readings,
                "measured_hours": indoor.measured_hours,
                "peak_lux": indoor.peak_lux,
                "mean_daytime_lux": indoor.mean_daytime_lux,
                "night_floor_lux": indoor.night_floor_lux,
                "effective_hours": indoor.effective_hours,
                "poor_hours": indoor.poor_hours,
                "comfort_hours": indoor.comfort_hours,
                "first_light_hour": indoor.first_light_hour,
                "last_light_hour": indoor.last_light_hour,
                "hourly_mean_lux": indoor.hourly_mean_lux,
            },
            "outdoor": None if outdoor is None else {
                "date": outdoor.date,
                "daylight_hours": outdoor.daylight_hours,
                "sunshine_hours": outdoor.sunshine_hours,
                "radiation_sum_mj_m2": outdoor.radiation_sum_mj_m2,
                "peak_irradiance_w_m2": outdoor.peak_irradiance_w_m2,
                "peak_lux_estimate": outdoor.peak_lux_estimate,
                "source": outdoor.source,
            },
            "outdoor_error": outdoor_error,
            "transmittance_pct": assessment.transmittance_pct,
            "deficit_hours": assessment.deficit_hours,
            "level": assessment.level,
            "headline": assessment.headline,
            "detail": assessment.detail,
            "effects": assessment.effects,
            "recommendations": assessment.recommendations,
            "alarm_value": assessment.alarm_value,
            "chart": pp.build_chart(assessment),
        }

    def _photoperiod_card(
        self, context: dict[str, Any], policy: dict[str, Any] | None
    ) -> dict[str, Any]:
        from backend.app.models_engine.deterministic import photoperiod as pp

        available = bool(context.get("available"))
        indoor = context.get("indoor") or {}
        outdoor = context.get("outdoor") or {}
        transmittance = context.get("transmittance_pct")

        detail_parts = [context.get("detail") or ""]
        if transmittance is not None:
            detail_parts.append(
                f"La cubierta del vivero transmite {transmittance:.2f}% de la luz natural."
            )
        if context.get("outdoor_error"):
            detail_parts.append("No se pudo consultar la luz natural externa en este ciclo.")

        card = self._card(
            code=PHOTOPERIOD_MODEL_CODE,
            alarm_code="MODEL_PHOTOPERIOD_DEFICIT",
            name="Fotoperiodo del vivero",
            purpose=(
                "Compara la luz medida dentro del vivero con la luz natural que deberia "
                "haber afuera y estima si alcanza para que la tilapia coma bien."
            ),
            horizon="Ultimas 24 horas",
            inputs=["Iluminancia interior", "Ubicacion de la piscigranja", "Luz natural (Open-Meteo)"],
            model={
                "status": "calculado" if available else "sin_datos",
                "current_value": context.get("alarm_value"),
                "unit": "h de luz util",
                "chart": context.get("chart"),
                "relationship": None if not available else {
                    "description": (
                        "Cada barra es el promedio de luz por hora dentro del vivero. "
                        "Debajo de 10 lux la tilapia deja de detectar el alimento; "
                        "por encima de 100 lux come con normalidad."
                    ),
                    "chart": context.get("chart"),
                },
                "formula": {
                    "expression": "horas_utiles = suma(horas con lux >= 10)",
                    "detail": (
                        "Se promedia la iluminancia por hora y se cuentan las horas que superan "
                        "el umbral de deteccion visual de la tilapia. La transmitancia se calcula "
                        "dividiendo el pico interior entre la irradiancia externa convertida a lux "
                        "(1 W/m2 = 116 lux)."
                    ),
                    "conditions": [
                        "Umbral de deteccion: 10 lux; alimentacion pobre entre 10 y 30 lux.",
                        "Referencia de confort: 100 lux durante la ventana de alimentacion.",
                        "Fotoperiodo recomendado entre 12L:12D y 18L:6D.",
                        "Calculo determinista: no usa artefacto entrenado.",
                    ],
                },
                "usage": {
                    "status": "en_uso" if available else "sin_datos",
                    "label": context.get("headline") or "Sin lecturas de luz",
                    "detail": " ".join(part for part in detail_parts if part).strip(),
                },
                "traceability": {
                    "indoor_source": "sismapiscis.parametro_ambientes.iluminancia",
                    "outdoor_source": "Open-Meteo forecast API (servicio abierto, sin llave)",
                    "farm": context.get("farm"),
                    "latitude": context.get("latitude"),
                    "longitude": context.get("longitude"),
                    "outdoor_date": outdoor.get("date"),
                    "readings_used": indoor.get("readings"),
                    "effects_on_fish": context.get("effects") or [],
                    "recommendations": context.get("recommendations") or [],
                },
                "metrics": {} if not available else {
                    "horas_luz_util": indoor.get("effective_hours"),
                    "horas_sobre_100_lux": indoor.get("comfort_hours"),
                    "pico_interior_lux": indoor.get("peak_lux"),
                    "piso_nocturno_lux": indoor.get("night_floor_lux"),
                    "luz_natural_horas": outdoor.get("daylight_hours"),
                    "pico_exterior_lux": outdoor.get("peak_lux_estimate"),
                    "transmitancia_pct": transmittance,
                },
            },
            policy=policy,
            eligible=available,
            unavailable_detail=str(
                context.get("reason") or "No hay lecturas de iluminancia para esta piscina."
            ),
            eligible_detail=(
                "El fotoperiodo se calcula con el sensor del vivero y la luz natural del dia; "
                "una politica aprobada decide cuando avisar."
            ),
            prediction_value=context.get("alarm_value"),
            prediction_for=None,
        )
        return card



    #: Que tabla legacy alimenta a cada modelo.
    _MODEL_SOURCE_TABLE = {
        ICA_MODEL_CODE: "parametro_aguas",
        SVM_MODEL_CODE: "parametro_aguas",
        GROWTH_MODEL_CODE: "biometrias",
        LIGHT_MODEL_CODE: "parametro_ambientes",
        PHOTOPERIOD_MODEL_CODE: "parametro_ambientes",
        CONDITION_MODEL_CODE: "biometrias",
        LIGHT_FORECAST_MODEL_CODE: "parametro_ambientes",
    }

    def _source_freshness(self, pond_id: str) -> dict[str, Any]:
        """Ultima fecha real de cada tabla de origen, leida del legacy."""
        engine = getattr(self.store, "engine", None)
        legacy = getattr(self.store, "legacy_database_name", None)
        if engine is None or not legacy:
            return {}
        safe = str(legacy).replace("`", "``")
        pond = self._pond_number(pond_id)
        filtro = " WHERE piscina_id = :pond" if pond is not None else ""
        consultas = {
            "parametro_aguas": (
                f"SELECT MAX(created_at) AS llegada, MAX(fecha_medicion) AS sensor "
                f"FROM `{safe}`.`parametro_aguas`{filtro}"
            ),
            "parametro_ambientes": (
                f"SELECT MAX(created_at) AS llegada, MAX(fecha_medicion) AS sensor "
                f"FROM `{safe}`.`parametro_ambientes`{filtro}"
            ),
            "biometrias": (
                f"SELECT MAX(fecha_muestreo) AS llegada, MAX(fecha_muestreo) AS sensor "
                f"FROM `{safe}`.`biometrias`"
            ),
        }
        salida: dict[str, Any] = {}
        try:
            with engine.connect() as connection:
                for tabla, sql in consultas.items():
                    try:
                        params = {"pond": pond} if ":pond" in sql else {}
                        fila = connection.execute(text(sql), params).mappings().first()
                        salida[tabla] = {
                            "llegada": fila["llegada"] if fila else None,
                            "sensor": fila["sensor"] if fila else None,
                        }
                    except Exception:
                        salida[tabla] = {"llegada": None, "sensor": None}
        except Exception:
            return {}
        return salida


    @staticmethod
    def _drift_days(sensor: object, llegada: object) -> float | None:
        """Dias que el reloj del equipo va por detras de la hora real.

        Cero significa que el sensor esta en hora. Un valor alto significa que
        sus marcas de tiempo no sirven para ordenar una serie temporal.
        """
        from datetime import date as _date

        def _dt(valor: object) -> datetime | None:
            if isinstance(valor, datetime):
                return valor
            if isinstance(valor, _date):
                return datetime(valor.year, valor.month, valor.day)
            return None

        a, b = _dt(sensor), _dt(llegada)
        if a is None or b is None:
            return None
        dias = (b - a).total_seconds() / 86400.0
        return round(dias, 1) if abs(dias) >= 0.5 else 0.0

    def _freshness(self, raw: object) -> dict[str, Any]:
        """Cuantos dias tiene el dato mas reciente que alimenta un modelo.

        Un modelo puede estar calculando bien y aun asi estar leyendo datos de
        hace semanas. En vez de bloquearlo por eso, se deja que proyecte y se
        marca la antiguedad para que quien mire sepa de cuando habla.
        """
        from datetime import date as _date

        moment = None
        if isinstance(raw, datetime):
            moment = raw
        elif isinstance(raw, _date):
            # biometrias.fecha_muestreo es DATE: se toma el final del dia
            moment = datetime(raw.year, raw.month, raw.day, 23, 59, tzinfo=_TZ_LOCAL)
        elif isinstance(raw, str) and raw:
            moment = self._parse_datetime(raw)
        if moment is None:
            return {"timestamp": None, "age_hours": None, "level": "unknown",
                    "label": "Sin fecha del ultimo dato"}
        moment = _asumir_hora_local(moment)
        age = (datetime.now(timezone.utc) - moment).total_seconds() / 3600.0
        age = max(0.0, age)
        if age <= 6:
            level, label = "fresh", "Dato reciente"
        elif age <= 48:
            hours = int(round(age))
            level, label = "recent", f"Dato de hace {hours} h"
        else:
            days = int(round(age / 24.0))
            level = "stale" if age <= 24 * 30 else "very_stale"
            label = f"Dato de hace {days} dias"
        return {
            "timestamp": moment.isoformat(),
            "age_hours": round(age, 1),
            "age_days": round(age / 24.0, 1),
            "level": level,
            "label": label,
        }

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
        tabla = self._MODEL_SOURCE_TABLE.get(code)
        origen = getattr(self, "_source_dates", {}) or {}
        fechas = origen.get(tabla) or {}
        # La antiguedad real es cuando el dato llego, no la hora del sensor.
        freshness = self._freshness(fechas.get("llegada"))
        freshness["source_table"] = tabla
        freshness["clock_drift_days"] = self._drift_days(
            fechas.get("sensor"), fechas.get("llegada")
        )
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
            # Que esta frenando al modelo respecto de su potencial, cuando aplica.
            "limiting_factors": model.get("limiting_factors"),
            "potential_value": model.get("potential_daily_length_gain_mm_day"),
            "projection_series": model.get("projection_series"),
            "policy": policy_payload,
            "data_freshness": freshness,
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

    def _legacy_light_observations(
        self, pond_id: str, window_hours: int
    ) -> list[tuple[str, float, str]]:
        """Lecturas de luz del esquema antiguo.

        El registro de sensores y la tabla de mediciones limpias son del
        esquema nuevo y aqui estan vacios, pero la piscina si tiene luxometro:
        sus lecturas caen en parametro_ambientes.iluminancia, que es de donde
        bebe el fotoperiodo. Se leen de ahi en lugar de dar el sensor por
        ausente.
        """
        engine = getattr(self.store, "engine", None)
        legacy = getattr(self.store, "legacy_database_name", None)
        pond_number = self._pond_number(pond_id)
        if engine is None or not legacy or pond_number is None:
            return []
        safe = str(legacy).replace("`", "``")
        try:
            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        f"""
                        SELECT fecha_medicion, iluminancia
                        FROM `{safe}`.`parametro_ambientes`
                        WHERE piscina_id = :piscina_id AND iluminancia IS NOT NULL
                        ORDER BY fecha_medicion DESC
                        LIMIT 5000
                        """
                    ),
                    {"piscina_id": pond_number},
                ).mappings().all()
        except Exception:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        observaciones: list[tuple[str, float, str]] = []
        for row in rows:
            moment, value = row.get("fecha_medicion"), row.get("iluminancia")
            if moment is None or value is None:
                continue
            momento = _asumir_hora_local(moment) if isinstance(moment, datetime) else None
            if momento is None or momento < cutoff:
                continue
            try:
                observaciones.append((momento.isoformat(), float(value), "lux"))
            except (TypeError, ValueError):
                continue
        observaciones.sort(key=lambda fila: fila[0])
        return observaciones

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
        # Si el esquema nuevo no tiene nada, la luz sigue estando: se lee del antiguo.
        if not observations:
            observations = self._legacy_light_observations(pond_id, window_hours)
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
        # Las politicas no tienen por que estar donde los sensores.
        legacy_database = getattr(self.store, "policy_database_name", None) or getattr(
            self.store, "legacy_database_name", None
        )
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
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_TZ_LOCAL)

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
