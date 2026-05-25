from __future__ import annotations

from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.deterministic.dissolved_oxygen import update_do_1d
from backend.app.models_engine.deterministic.growth import (
    haskell_feed_rate,
    nile_tilapia_weight_from_length,
    soderberg_delta_l,
    yi_growth_rate,
)
from backend.app.models_engine.deterministic.ras_oxygen import ras_oxygen_balance
from backend.app.models_engine.deterministic.zootechnics import zootechnic_indexes


def _value(model_input: ModelInput, name: str) -> object:
    return model_input.inputs[name].value


def _float(model_input: ModelInput, name: str) -> float:
    return float(_value(model_input, name))


def _series(model_input: ModelInput, name: str) -> list[float]:
    value = _value(model_input, name)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    return [float(item) for item in value]


class _UnitValidatedRunner(BaseModelRunner):
    required_inputs: dict[str, str]

    def validate_inputs(self, model_input: ModelInput) -> None:
        missing = set(self.required_inputs) - set(model_input.inputs)
        if missing:
            raise ValueError(f"Missing required inputs: {', '.join(sorted(missing))}")
        for input_name, expected_unit in self.required_inputs.items():
            input_value = model_input.inputs[input_name]
            if input_value.unit != expected_unit:
                raise ValueError(
                    f"{input_name} must use unit {expected_unit}; "
                    f"received {input_value.unit}"
                )


class DissolvedOxygen1DTransport(_UnitValidatedRunner):
    model_code = "DO_TRANSPORT_1D"
    model_version = "1.0.0"
    source_report = "FORMULAS_IMPLEMENTACION_GEMELO_ACUICULTURA"
    required_inputs = {
        "concentrations_mg_l": "mg/L_series",
        "saturation_mg_l": "mg/L_series",
        "biomass_kg": "kg_series",
        "q_over_area_m_h": "m/h",
        "reaeration_rate_h_1": "h^-1",
        "fish_respiration_rate_mg_h_kg": "mg/h/kg",
        "area_m2": "m2",
        "dx_m": "m",
        "dt_h": "h",
    }
    required_outputs = {"concentrations_next_mg_l": "mg/L_series"}
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="deterministic",
        name="Modelo 1D de transporte de oxigeno disuelto",
        source_reference="formulas_implementacion_gemelo_acuicultura.md seccion 2.5",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=["Diferencia upwind para adveccion y condicion CFL simple."],
    )

    def predict(self, model_input: ModelInput, context: ModelRunContext) -> ModelOutput:
        values = update_do_1d(
            concentrations=_series(model_input, "concentrations_mg_l"),
            saturation=_series(model_input, "saturation_mg_l"),
            biomass=_series(model_input, "biomass_kg"),
            q_over_area_h=_float(model_input, "q_over_area_m_h"),
            k_rear_h_1=_float(model_input, "reaeration_rate_h_1"),
            respiration_rate=_float(model_input, "fish_respiration_rate_mg_h_kg"),
            area_m2=_float(model_input, "area_m2"),
            dx_m=_float(model_input, "dx_m"),
            dt_h=_float(model_input, "dt_h"),
        )
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "concentrations_next_mg_l": ModelOutputValue(
                    value=values,
                    unit="mg/L_series",
                )
            },
            unit_map=self.required_outputs,
            explanation="1D dissolved oxygen transport calculated by upwind discretization.",
        )


class RASOxygenBalanceModel(_UnitValidatedRunner):
    model_code = "RAS_OXYGEN_BALANCE"
    model_version = "1.0.0"
    source_report = "FORMULAS_IMPLEMENTACION_GEMELO_ACUICULTURA"
    required_inputs = {
        "do_previous_mg_l": "mg/L",
        "average_weight_g": "g",
        "water_temperature_c": "degC",
        "stocking_density_kg_m3": "kg/m3",
        "fish_count": "count",
        "volume_m3": "m3",
        "biomass_kg": "kg",
        "dt_h": "h",
    }
    required_outputs = {
        "do_next_mg_l": "mg/L",
        "oxygen_required_mg_l_h": "mg/L/h",
        "fish_respiration_mg_l_h": "mg/L/h",
        "biofilter_consumption_mg_l_h": "mg/L/h",
        "nitrification_consumption_mg_l_h": "mg/L/h",
        "pipe_flow_oxygen_mg_l_h": "mg/L/h",
    }
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="deterministic",
        name="Balance de oxigeno RAS",
        source_reference="formulas_implementacion_gemelo_acuicultura.md seccion 3",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=["Amoniaco completo no se predice; nitrificacion solo consume oxigeno."],
    )

    def predict(self, model_input: ModelInput, context: ModelRunContext) -> ModelOutput:
        values = ras_oxygen_balance(
            do_previous_mg_l=_float(model_input, "do_previous_mg_l"),
            average_weight_g=_float(model_input, "average_weight_g"),
            temperature_c=_float(model_input, "water_temperature_c"),
            stocking_density_kg_m3=_float(model_input, "stocking_density_kg_m3"),
            fish_count=_float(model_input, "fish_count"),
            volume_m3=_float(model_input, "volume_m3"),
            biomass_kg=_float(model_input, "biomass_kg"),
            dt_h=_float(model_input, "dt_h"),
            feed_rate_percent_body_weight_day=model_input.parameters.get(
                "feed_rate_percent_body_weight_day"
            ),
            bod5_mg_o2_kg_day=float(model_input.parameters.get("bod5_mg_o2_kg_day", 2160.0)),
            pump_cycle_h=float(model_input.parameters.get("pump_cycle_h", 0.0)),
            pump_frequency_h_1=float(model_input.parameters.get("pump_frequency_h_1", 0.0)),
            pump_efficiency=float(model_input.parameters.get("pump_efficiency", 0.0)),
            oxygen_transfer_rate_g_h=float(
                model_input.parameters.get("oxygen_transfer_rate_g_h", 0.0)
            ),
        )
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                key: ModelOutputValue(value=value, unit=self.required_outputs.get(key, "scalar"))
                for key, value in values.items()
                if key in self.required_outputs
            },
            unit_map=self.required_outputs,
            explanation="RAS oxygen demand and next DO calculated from fish respiration, nitrification, biofilter and pump flow.",
            explainability={k: v for k, v in values.items() if k not in self.required_outputs},
        )


class YiGrowthModel(_UnitValidatedRunner):
    model_code = "YI_ENVIRONMENTAL_GROWTH"
    model_version = "1.0.0"
    source_report = "FORMULAS_IMPLEMENTACION_GEMELO_ACUICULTURA"
    required_inputs = {
        "water_temperature_c": "degC",
        "dissolved_oxygen_mg_l": "mg/L",
        "fish_weight_g": "g",
        "t_min_c": "degC",
        "t_opti_c": "degC",
        "t_max_c": "degC",
        "do_min_mg_l": "mg/L",
        "do_crit_mg_l": "mg/L",
        "k_min": "coefficient",
        "s": "coefficient",
        "kappa": "fraction",
        "phi": "fraction",
        "h": "coefficient",
        "feeding_level": "fraction",
        "m": "coefficient",
        "n": "coefficient",
    }
    required_outputs = {
        "fish_growth_rate_g_day": "g/day",
        "tau": "fraction",
        "delta": "fraction",
        "catabolism_coefficient": "coefficient",
    }
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="deterministic",
        name="Modelo ambiental de crecimiento Yi",
        source_reference="formulas_implementacion_gemelo_acuicultura.md seccion 4",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=["phi puede ser 1.0 hasta validar un modelo completo de NH3 no ionizado."],
    )

    def predict(self, model_input: ModelInput, context: ModelRunContext) -> ModelOutput:
        values = yi_growth_rate(
            temperature_c=_float(model_input, "water_temperature_c"),
            dissolved_oxygen_mg_l=_float(model_input, "dissolved_oxygen_mg_l"),
            fish_weight_g=_float(model_input, "fish_weight_g"),
            t_min_c=_float(model_input, "t_min_c"),
            t_opti_c=_float(model_input, "t_opti_c"),
            t_max_c=_float(model_input, "t_max_c"),
            do_min_mg_l=_float(model_input, "do_min_mg_l"),
            do_crit_mg_l=_float(model_input, "do_crit_mg_l"),
            k_min=_float(model_input, "k_min"),
            s=_float(model_input, "s"),
            kappa=_float(model_input, "kappa"),
            phi=_float(model_input, "phi"),
            h=_float(model_input, "h"),
            feeding_level=_float(model_input, "feeding_level"),
            m=_float(model_input, "m"),
            n=_float(model_input, "n"),
        )
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                key: ModelOutputValue(value=value, unit=self.required_outputs.get(key, "scalar"))
                for key, value in values.items()
                if key in self.required_outputs
            },
            unit_map=self.required_outputs,
            explanation="Yi growth rate calculated with temperature and dissolved oxygen factors.",
            explainability={k: v for k, v in values.items() if k not in self.required_outputs},
        )


class SoderbergGrowthModel(_UnitValidatedRunner):
    model_code = "SODERBERG_LINEAR_GROWTH"
    model_version = "1.0.0"
    source_report = "FORMULAS_IMPLEMENTACION_GEMELO_ACUICULTURA"
    required_inputs = {
        "water_temperature_c": "degC",
        "fish_length_mm": "mm",
    }
    required_outputs = {
        "daily_length_gain_mm_day": "mm/day",
        "next_length_mm": "mm",
        "estimated_weight_g": "g",
        "feed_percentage_body_weight": "%",
    }
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="deterministic",
        name="Crecimiento lineal Soderberg/Taylor",
        source_reference="formulas_implementacion_gemelo_acuicultura.md seccion 5",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=["Por defecto usa especie nile tilapia y FCR desde parametros."],
    )

    def predict(self, model_input: ModelInput, context: ModelRunContext) -> ModelOutput:
        species = str(model_input.parameters.get("species", "nile tilapia"))
        growth = soderberg_delta_l(_float(model_input, "water_temperature_c"), species)
        length = _float(model_input, "fish_length_mm")
        next_length = length + float(growth["daily_length_gain_mm_day"])
        fcr = float(model_input.parameters.get("feed_conversion_ratio", 1.5))
        feed_percent = haskell_feed_rate(fcr, float(growth["daily_length_gain_mm_day"]), length)
        weight = nile_tilapia_weight_from_length(next_length) if growth["species"] == "nile tilapia" else 0.0
        outputs = {
            "daily_length_gain_mm_day": ModelOutputValue(
                value=growth["daily_length_gain_mm_day"],
                unit="mm/day",
            ),
            "next_length_mm": ModelOutputValue(value=next_length, unit="mm"),
            "estimated_weight_g": ModelOutputValue(value=weight, unit="g"),
            "feed_percentage_body_weight": ModelOutputValue(value=feed_percent, unit="%"),
        }
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs=outputs,
            unit_map=self.required_outputs,
            explanation="Soderberg/Taylor linear length growth and Haskell feed rate.",
            explainability=growth,
        )


class ZootechnicIndexesModel(_UnitValidatedRunner):
    model_code = "ZOOTECHNIC_INDEXES"
    model_version = "1.0.0"
    source_report = "FORMULAS_IMPLEMENTACION_GEMELO_ACUICULTURA"
    required_inputs = {
        "final_weight_g": "g",
        "initial_weight_g": "g",
        "final_length_cm": "cm",
        "days": "day",
        "final_fish_count": "count",
        "initial_fish_count": "count",
        "feed_consumed_g": "g",
    }
    required_outputs = {
        "condition_factor": "index",
        "final_biomass_kg_m3": "kg/m3",
        "daily_gain_g_fish_day": "g/fish/day",
        "specific_growth_rate_percent_day": "%/day",
        "adjusted_feed_conversion_ratio": "ratio",
        "feeding_rate_percent_biomass": "%",
        "mortality_percent": "%",
    }
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="deterministic",
        name="Indicadores zootecnicos",
        source_reference="formulas_implementacion_gemelo_acuicultura.md seccion 7",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
    )

    def predict(self, model_input: ModelInput, context: ModelRunContext) -> ModelOutput:
        values = zootechnic_indexes(
            final_weight_g=_float(model_input, "final_weight_g"),
            initial_weight_g=_float(model_input, "initial_weight_g"),
            final_length_cm=_float(model_input, "final_length_cm"),
            days=_float(model_input, "days"),
            final_fish_count=_float(model_input, "final_fish_count"),
            initial_fish_count=_float(model_input, "initial_fish_count"),
            feed_consumed_g=_float(model_input, "feed_consumed_g"),
            biomass_removed_mortality_g=float(
                model_input.parameters.get("biomass_removed_mortality_g", 0.0)
            ),
            biomass_sampled_g=float(model_input.parameters.get("biomass_sampled_g", 0.0)),
            tank_to_m3_factor=float(model_input.parameters.get("tank_to_m3_factor", 1.666)),
        )
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                key: ModelOutputValue(value=value, unit=self.required_outputs.get(key, "scalar"))
                for key, value in values.items()
                if key in self.required_outputs
            },
            unit_map=self.required_outputs,
            explanation="Zootechnic indicators calculated for feeding phase.",
            explainability={k: v for k, v in values.items() if k not in self.required_outputs},
        )
