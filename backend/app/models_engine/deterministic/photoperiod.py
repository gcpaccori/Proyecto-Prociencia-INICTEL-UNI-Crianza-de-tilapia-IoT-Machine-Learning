"""Fotoperiodo de vivero: compara la luz medida dentro con la luz natural.

Las tilapias de este centro viven bajo vivero. El sensor mide dentro; la luz
que deberia haber afuera se toma de Open-Meteo (servicio abierto, sin llave).
De la diferencia salen tres cosas que si tienen efecto documentado sobre el
pez: cuantas horas hay luz suficiente para que coma, con que intensidad, y
cuanta luz natural se esta perdiendo por la cubierta.

Referencias de comportamiento usadas para los umbrales:

- Oreochromis niloticus es un alimentador visual: por debajo de ~10 lux la
  deteccion del alimento cae y practicamente deja de comer.
- Entre ~10 y ~30 lux come, pero de forma pobre e irregular.
- El rango util documentado para crecimiento en cultivo intensivo esta por
  encima de ~100 lux durante la ventana de alimentacion.
- El fotoperiodo recomendado va de 12L:12D a 18L:6D. Menos de 10 h de luz
  util reduce ingesta y ganancia de peso; 24 h continuas aumentan
  crecimiento pero tambien estres, por eso tambien se marca el exceso.

Todo lo que se calcula aqui es determinista y trazable: no hay artefacto
entrenado, no hace falta validar contra persistencia.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT_SECONDS = 12.0

#: Por debajo de esto la tilapia practicamente no detecta el alimento.
FEEDING_MINIMUM_LUX = 10.0
#: Por debajo de esto come, pero de forma pobre.
FEEDING_POOR_LUX = 30.0
#: Referencia de confort para crecimiento en la ventana de alimentacion.
FEEDING_COMFORT_LUX = 100.0
#: Horas de luz util por debajo de las cuales se considera fotoperiodo corto.
SHORT_PHOTOPERIOD_HOURS = 10.0
#: Horas de luz util por encima de las cuales hay riesgo de estres por exceso.
LONG_PHOTOPERIOD_HOURS = 18.0

#: Conversion aproximada de irradiancia global a iluminancia para luz diurna.
#: 1 W/m2 de radiacion solar de banda ancha equivale a ~116 lux.
LUX_PER_WATT_M2 = 116.0


class PhotoperiodDataUnavailable(RuntimeError):
    """No hay suficiente evidencia para calcular el fotoperiodo."""


@dataclass
class OutdoorReference:
    """Luz natural esperada afuera, segun Open-Meteo."""

    date: str
    daylight_hours: float
    sunshine_hours: float
    radiation_sum_mj_m2: float
    peak_irradiance_w_m2: float | None = None
    source: str = "open-meteo"

    @property
    def peak_lux_estimate(self) -> float | None:
        if self.peak_irradiance_w_m2 is None:
            return None
        return self.peak_irradiance_w_m2 * LUX_PER_WATT_M2


@dataclass
class IndoorProfile:
    """Lo que realmente midio el sensor dentro del vivero."""

    readings: int
    peak_lux: float
    mean_daytime_lux: float
    night_floor_lux: float
    measured_hours: float
    effective_hours: float
    poor_hours: float
    comfort_hours: float
    first_light_hour: float | None
    last_light_hour: float | None
    hourly_mean_lux: dict[int, float] = field(default_factory=dict)


@dataclass
class PhotoperiodAssessment:
    """Resultado listo para tarjeta, alarma y gemelo digital."""

    indoor: IndoorProfile
    outdoor: OutdoorReference | None
    transmittance_pct: float | None
    deficit_hours: float | None
    level: str
    headline: str
    detail: str
    effects: list[str]
    recommendations: list[str]

    @property
    def alarm_value(self) -> float:
        """Valor que compara la politica: horas de luz util para comer."""
        return round(self.indoor.effective_hours, 2)


def fetch_outdoor_reference(
    latitude: float,
    longitude: float,
    *,
    timezone_name: str = "America/Lima",
    opener=urllib.request.urlopen,
) -> OutdoorReference:
    """Consulta Open-Meteo. Servicio abierto, sin llave ni cuota registrada."""

    query = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:.5f}",
            "longitude": f"{longitude:.5f}",
            "daily": "daylight_duration,sunshine_duration,shortwave_radiation_sum",
            "hourly": "shortwave_radiation",
            "timezone": timezone_name,
            "forecast_days": 1,
        }
    )
    url = f"{OPEN_METEO_URL}?{query}"
    with opener(url, timeout=OPEN_METEO_TIMEOUT_SECONDS) as response:
        payload = json.load(response)

    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        raise PhotoperiodDataUnavailable("Open-Meteo no devolvio datos diarios.")

    index = 0
    daylight_seconds = _first_number(daily.get("daylight_duration"), index)
    sunshine_seconds = _first_number(daily.get("sunshine_duration"), index)
    radiation_sum = _first_number(daily.get("shortwave_radiation_sum"), index) or 0.0

    hourly = payload.get("hourly") or {}
    radiation_series = [value for value in (hourly.get("shortwave_radiation") or []) if value is not None]
    peak_irradiance = max(radiation_series) if radiation_series else None

    return OutdoorReference(
        date=str(dates[index]),
        daylight_hours=round((daylight_seconds or 0.0) / 3600.0, 2),
        sunshine_hours=round((sunshine_seconds or 0.0) / 3600.0, 2),
        radiation_sum_mj_m2=round(float(radiation_sum), 2),
        peak_irradiance_w_m2=float(peak_irradiance) if peak_irradiance is not None else None,
    )


def build_indoor_profile(
    observations: list[tuple[datetime, float]],
    *,
    window_hours: int = 24,
) -> IndoorProfile:
    """Resume las lecturas del sensor de luz dentro del vivero."""

    if not observations:
        raise PhotoperiodDataUnavailable("El sensor de luz no tiene lecturas en la ventana.")

    ordered = sorted(observations, key=lambda item: item[0])
    newest = ordered[-1][0]
    cutoff = newest - timedelta(hours=window_hours)
    recent = [(moment, value) for moment, value in ordered if moment >= cutoff]
    if len(recent) < 4:
        raise PhotoperiodDataUnavailable(
            "Se necesitan al menos 4 lecturas de luz en la ventana para describir el dia."
        )

    buckets: dict[int, list[float]] = {}
    for moment, value in recent:
        buckets.setdefault(moment.hour, []).append(float(value))
    hourly_mean = {hour: sum(values) / len(values) for hour, values in sorted(buckets.items())}

    effective_hours = sum(1.0 for mean in hourly_mean.values() if mean >= FEEDING_MINIMUM_LUX)
    poor_hours = sum(
        1.0 for mean in hourly_mean.values() if FEEDING_MINIMUM_LUX <= mean < FEEDING_POOR_LUX
    )
    comfort_hours = sum(1.0 for mean in hourly_mean.values() if mean >= FEEDING_COMFORT_LUX)

    lit_hours = [hour for hour, mean in hourly_mean.items() if mean >= FEEDING_MINIMUM_LUX]
    daytime = [mean for mean in hourly_mean.values() if mean >= FEEDING_MINIMUM_LUX]
    night = [mean for mean in hourly_mean.values() if mean < FEEDING_MINIMUM_LUX]

    return IndoorProfile(
        readings=len(recent),
        measured_hours=float(len(hourly_mean)),
        peak_lux=round(max(value for _, value in recent), 1),
        mean_daytime_lux=round(sum(daytime) / len(daytime), 1) if daytime else 0.0,
        night_floor_lux=round(sum(night) / len(night), 1) if night else 0.0,
        effective_hours=effective_hours,
        poor_hours=poor_hours,
        comfort_hours=comfort_hours,
        first_light_hour=float(min(lit_hours)) if lit_hours else None,
        last_light_hour=float(max(lit_hours)) if lit_hours else None,
        hourly_mean_lux={hour: round(mean, 1) for hour, mean in hourly_mean.items()},
    )


def assess(indoor: IndoorProfile, outdoor: OutdoorReference | None) -> PhotoperiodAssessment:
    """Cruza lo medido con lo esperado y dice que significa para el pez."""

    transmittance = None
    if outdoor is not None:
        reference_peak = outdoor.peak_lux_estimate
        if reference_peak and reference_peak > 0:
            transmittance = round(100.0 * indoor.peak_lux / reference_peak, 2)

    deficit = None
    if outdoor is not None:
        deficit = round(outdoor.daylight_hours - indoor.effective_hours, 2)

    effects: list[str] = []
    recommendations: list[str] = []

    # Sin cobertura suficiente no se puede afirmar que falte luz: puede ser
    # que falten lecturas. Se avisa del hueco en lugar de dar un falso corto.
    incomplete = indoor.measured_hours < 20.0
    if incomplete:
        gap = int(24 - indoor.measured_hours)
        return PhotoperiodAssessment(
            indoor=indoor,
            outdoor=outdoor,
            transmittance_pct=transmittance,
            deficit_hours=deficit,
            level="normal",
            headline=f"Faltan lecturas de {gap} horas del dia",
            detail=(
                f"Solo hay datos de {indoor.measured_hours:.0f} de las 24 horas. "
                f"De esas, {indoor.effective_hours:.0f} tienen luz suficiente para comer. "
                "No se puede concluir que el fotoperiodo sea corto mientras falten horas sin medir."
            ),
            effects=["Medicion incompleta: el diagnostico queda en espera."],
            recommendations=["Revisar por que el sensor de luz dejo de reportar en ese tramo."],
        )

    if indoor.effective_hours < SHORT_PHOTOPERIOD_HOURS:
        level = "critico" if indoor.effective_hours < 8.0 else "advertencia"
        headline = f"Solo hay {indoor.effective_hours:.0f} h de luz util al dia"
        detail = (
            f"El sensor registra {indoor.effective_hours:.0f} horas por encima de "
            f"{FEEDING_MINIMUM_LUX:.0f} lux. Por debajo de {SHORT_PHOTOPERIOD_HOURS:.0f} h "
            "la tilapia reduce la ingesta y la ganancia de peso."
        )
        effects.append("Menos horas para comer: baja la ingesta diaria.")
        effects.append("Menor ganancia de peso y conversion alimenticia peor.")
        recommendations.append("Concentrar las raciones dentro de las horas con mas luz.")
        recommendations.append("Evaluar iluminacion de apoyo hasta llegar a 12 h utiles.")
    elif indoor.effective_hours > LONG_PHOTOPERIOD_HOURS:
        level = "advertencia"
        headline = f"Hay {indoor.effective_hours:.0f} h de luz al dia, mas de lo recomendado"
        detail = (
            "Pasar de 18 h de luz puede acelerar el crecimiento, pero tambien eleva el "
            "estres y reduce el descanso del pez."
        )
        effects.append("Menos descanso; se ha asociado a mayor estres.")
        recommendations.append("Dejar al menos 6 h continuas de oscuridad.")
    elif indoor.comfort_hours < 6.0:
        level = "advertencia"
        headline = "La luz dura lo suficiente, pero es demasiado tenue"
        detail = (
            f"Hay {indoor.effective_hours:.0f} h de luz, pero solo {indoor.comfort_hours:.0f} h "
            f"superan {FEEDING_COMFORT_LUX:.0f} lux. Dentro del vivero la luz llega difusa."
        )
        effects.append("El pez ve poco el alimento: mas alimento sin consumir.")
        recommendations.append("Revisar suciedad o sombra de la cubierta del vivero.")
    else:
        level = "normal"
        headline = f"Fotoperiodo adecuado: {indoor.effective_hours:.0f} h de luz util"
        detail = (
            f"{indoor.comfort_hours:.0f} h superan {FEEDING_COMFORT_LUX:.0f} lux, "
            "dentro del rango recomendado para alimentar."
        )
        effects.append("Ventana de alimentacion suficiente.")

    if transmittance is not None and transmittance < 5.0:
        effects.append(
            f"La cubierta deja pasar solo {transmittance:.1f}% de la luz natural."
        )
        if "Revisar suciedad o sombra de la cubierta del vivero." not in recommendations:
            recommendations.append("Revisar suciedad o sombra de la cubierta del vivero.")

    return PhotoperiodAssessment(
        indoor=indoor,
        outdoor=outdoor,
        transmittance_pct=transmittance,
        deficit_hours=deficit,
        level=level,
        headline=headline,
        detail=detail,
        effects=effects,
        recommendations=recommendations,
    )


def build_chart(assessment: PhotoperiodAssessment) -> dict[str, object]:
    """Barras por hora con las lineas de referencia del comportamiento."""

    hours = list(range(24))
    values = [assessment.indoor.hourly_mean_lux.get(hour, 0.0) for hour in hours]
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"bottom": 0},
        "grid": {"top": 24, "left": 8, "right": 18, "bottom": 34, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": [f"{hour:02d}h" for hour in hours],
        },
        "yAxis": {"type": "value", "name": "lux"},
        "series": [
            {
                "name": "Luz medida dentro",
                "type": "bar",
                "data": [round(value, 1) for value in values],
                "itemStyle": {"color": "#f59e0b"},
                "markLine": {
                    "silent": True,
                    "symbol": "none",
                    "data": [
                        {
                            "yAxis": FEEDING_MINIMUM_LUX,
                            "lineStyle": {"color": "#dc2626", "type": "dashed"},
                            "label": {"formatter": "Deja de comer"},
                        },
                        {
                            "yAxis": FEEDING_COMFORT_LUX,
                            "lineStyle": {"color": "#16a34a", "type": "dashed"},
                            "label": {"formatter": "Come bien"},
                        },
                    ],
                },
            }
        ],
    }


def _first_number(values: object, index: int) -> float | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
