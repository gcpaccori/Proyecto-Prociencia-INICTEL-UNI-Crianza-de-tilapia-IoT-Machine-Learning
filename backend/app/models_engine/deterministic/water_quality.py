from __future__ import annotations

import math


ICA_WEIGHTS = {
    "water_temperature_c": 0.25,
    "ph": 0.25,
    "dissolved_oxygen_mg_l": 0.35,
    "nitrate_ion": 0.15,
}

ICA_INTERPRETATION = [
    {"minimum": 90.0, "maximum": 100.0, "label": "Excelente"},
    {"minimum": 70.0, "maximum": 89.999, "label": "Buena"},
    {"minimum": 50.0, "maximum": 69.999, "label": "Regular"},
    {"minimum": 25.0, "maximum": 49.999, "label": "Mala"},
    {"minimum": 0.0, "maximum": 24.999, "label": "Muy mala"},
]


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _require_finite(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def normalize_temperature(temperature_c: float) -> float:
    """Normalize temperature with the 26-30 C range in Biometria1.docx."""
    value = _require_finite("water_temperature_c", temperature_c)
    if value < 26.0:
        return _bounded(100.0 - (26.0 - value) * 10.0)
    if value > 30.0:
        return _bounded(100.0 - (value - 30.0) * 10.0)
    return 100.0


def normalize_ph(ph: float) -> float:
    """Normalize pH with the 6.5-8.5 range in Biometria1.docx."""
    value = _require_finite("ph", ph)
    if value < 6.5:
        return _bounded(100.0 - (6.5 - value) * 20.0)
    if value > 8.5:
        return _bounded(100.0 - (value - 8.5) * 20.0)
    return 100.0


def normalize_dissolved_oxygen(dissolved_oxygen_mg_l: float) -> float:
    value = _require_finite("dissolved_oxygen_mg_l", dissolved_oxygen_mg_l)
    return 100.0 if value >= 5.0 else _bounded(value / 5.0 * 100.0)


def normalize_nitrate(nitrate_ion_mg_l: float) -> float:
    value = _require_finite("nitrate_ion", nitrate_ion_mg_l)
    if value < 50.0:
        return 100.0
    if value < 100.0:
        return _bounded(100.0 - (value - 50.0) * 2.0)
    return 0.0


def classify_ica(ica: float) -> str:
    value = _bounded(ica)
    for level in ICA_INTERPRETATION:
        if value >= float(level["minimum"]):
            return str(level["label"])
    return "Muy mala"


def water_quality_index(
    water_temperature_c: float,
    ph: float,
    dissolved_oxygen_mg_l: float,
    nitrate_ion_mg_l: float,
) -> dict[str, object]:
    """Calculate the documented ICA directly from real sensor values."""
    components = [
        {
            "variable": "Temperatura",
            "raw_value": _require_finite("water_temperature_c", water_temperature_c),
            "unit": "C",
            "normalized_score": normalize_temperature(water_temperature_c),
            "weight": ICA_WEIGHTS["water_temperature_c"],
            "interpretation": "Optimo entre 26 y 30 C.",
        },
        {
            "variable": "pH",
            "raw_value": _require_finite("ph", ph),
            "unit": "pH",
            "normalized_score": normalize_ph(ph),
            "weight": ICA_WEIGHTS["ph"],
            "interpretation": "Optimo entre 6.5 y 8.5.",
        },
        {
            "variable": "Oxigeno disuelto",
            "raw_value": _require_finite("dissolved_oxygen_mg_l", dissolved_oxygen_mg_l),
            "unit": "mg/L",
            "normalized_score": normalize_dissolved_oxygen(dissolved_oxygen_mg_l),
            "weight": ICA_WEIGHTS["dissolved_oxygen_mg_l"],
            "interpretation": "Puntaje maximo desde 5 mg/L.",
        },
        {
            "variable": "Ion nitrato",
            "raw_value": _require_finite("nitrate_ion", nitrate_ion_mg_l),
            "unit": "mg/L",
            "normalized_score": normalize_nitrate(nitrate_ion_mg_l),
            "weight": ICA_WEIGHTS["nitrate_ion"],
            "interpretation": "Puntaje maximo por debajo de 50 mg/L.",
        },
    ]
    value = sum(
        float(component["normalized_score"]) * float(component["weight"])
        for component in components
    )
    return {
        "status": "calculated",
        "ica": round(value, 2),
        "classification": classify_ica(value),
        "components": components,
        "interpretation": ICA_INTERPRETATION,
        "formula": "ICA = 0.25Q_T + 0.25Q_pH + 0.35Q_OD + 0.15Q_NO3",
    }


def biofloc_water_quality_readiness() -> dict[str, object]:
    """Expose the document formula without fabricating its local coefficients."""
    return {
        "status": "not_ready",
        "formula": "CA = a0 + a1T + a2pH + a3OD + a4NO3",
        "reason": (
            "El documento exige ajustar los coeficientes con una salida de calidad "
            "biofloc medida en la piscigranja; esa etiqueta aun no existe en MySQL."
        ),
        "required_real_data": [
            "etiqueta o indice de calidad biofloc por fecha y piscina",
            "criterio de calibracion aprobado para los coeficientes",
        ],
    }
