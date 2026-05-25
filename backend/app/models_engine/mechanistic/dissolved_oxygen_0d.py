from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.deterministic import do_saturation, update_do_0d


class FormulaPendingExtractionError(RuntimeError):
    pass


class DissolvedOxygen0DRoyer2021(BaseModelRunner):
    model_code = "DO_DYNAMIC_0D_ROYER_2021"
    model_version = "1.0.0"
    source_report = "INFORME016"

    required_inputs = {
        "do_initial_mg_l": "mg/L",
        "do_influent_mg_l": "mg/L",
        "water_temperature_c": "degC",
        "flow_rate_l_h": "L/h",
        "raceway_volume_l": "L",
        "fish_biomass_kg": "kg",
        "fish_respiration_rate_mg_h_kg": "mg/h/kg",
        "oxygen_supply_rate_mg_l_h": "mg/L/h",
        "reaeration_rate_h_1": "h^-1",
        "simulation_horizon_minutes": "min",
    }
    required_outputs = {
        "do_forecast_mg_l": "mg/L",
        "oxygen_consumption_rate": "mg/L/h",
        "oxygen_demand": "mg/L",
        "do_saturation_mg_l": "mg/L",
        "hypoxia_risk": "risk_level",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="mechanistic",
        name="Modelo dinamico 0D de oxigeno disuelto",
        source_reference=(
            "Royer et al., 2021; formulas_implementacion_gemelo_acuicultura.md "
            "seccion 2.1"
        ),
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "Agua del canal bien mezclada.",
            "Euler explicito para la EDO de balance de masa.",
            "DO_sat se calcula con el polinomio del documento de formulas.",
            "El consumo de oxigeno se ingresa como mg h^-1 kg^-1.",
        ],
    )

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
            if input_name != "water_temperature_c":
                self._require_non_negative_number(input_name, input_value.value)

        self._require_positive_number(
            "raceway_volume_l",
            model_input.inputs["raceway_volume_l"].value,
        )
        self._require_positive_number(
            "simulation_horizon_minutes",
            model_input.inputs["simulation_horizon_minutes"].value,
        )

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        do_value = float(model_input.inputs["do_initial_mg_l"].value)
        temp_c = float(model_input.inputs["water_temperature_c"].value)
        do_sat = do_saturation(temp_c)
        horizon_minutes = float(model_input.inputs["simulation_horizon_minutes"].value)
        dt_minutes = float(model_input.parameters.get("dt_minutes", 1.0))
        if dt_minutes <= 0:
            raise ValueError("dt_minutes must be positive")

        elapsed = 0.0
        while elapsed < horizon_minutes:
            step_minutes = min(dt_minutes, horizon_minutes - elapsed)
            do_value = update_do_0d(
                x_prev=do_value,
                x_in=float(model_input.inputs["do_influent_mg_l"].value),
                q_l_h=float(model_input.inputs["flow_rate_l_h"].value),
                volume_l=float(model_input.inputs["raceway_volume_l"].value),
                s=float(model_input.inputs["oxygen_supply_rate_mg_l_h"].value),
                k_rear=float(model_input.inputs["reaeration_rate_h_1"].value),
                do_sat=do_sat,
                biomass_kg=float(model_input.inputs["fish_biomass_kg"].value),
                respiration_rate=float(
                    model_input.inputs["fish_respiration_rate_mg_h_kg"].value
                ),
                dt_h=step_minutes / 60.0,
            )
            elapsed += step_minutes

        volume_l = float(model_input.inputs["raceway_volume_l"].value)
        consumption_rate = (
            float(model_input.inputs["fish_biomass_kg"].value)
            * float(model_input.inputs["fish_respiration_rate_mg_h_kg"].value)
            / volume_l
        )
        oxygen_demand = consumption_rate * (horizon_minutes / 60.0)
        hypoxia_risk = self._hypoxia_risk(do_value)
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "do_forecast_mg_l": ModelOutputValue(value=do_value, unit="mg/L"),
                "oxygen_consumption_rate": ModelOutputValue(
                    value=consumption_rate,
                    unit="mg/L/h",
                ),
                "oxygen_demand": ModelOutputValue(value=oxygen_demand, unit="mg/L"),
                "do_saturation_mg_l": ModelOutputValue(value=do_sat, unit="mg/L"),
                "hypoxia_risk": ModelOutputValue(value=hypoxia_risk, unit="risk_level"),
            },
            unit_map=self.required_outputs,
            confidence=None,
            explanation="0D dissolved oxygen forecast calculated with explicit Euler balance.",
            explainability={
                "formula": (
                    "dx/dt = Q(x_in - x)/V + S + k_rear(DO_sat - x) - M R / V"
                ),
                "dt_minutes": dt_minutes,
                "simulation_steps": int(round(horizon_minutes / dt_minutes)),
            },
        )

    @staticmethod
    def _hypoxia_risk(do_mg_l: float) -> str:
        if do_mg_l < 3:
            return "high"
        if do_mg_l < 5:
            return "medium"
        return "low"

    @staticmethod
    def _require_non_negative_number(name: str, value: object) -> None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if numeric_value < 0:
            raise ValueError(f"{name} must be non-negative")

    @staticmethod
    def _require_positive_number(name: str, value: object) -> None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if numeric_value <= 0:
            raise ValueError(f"{name} must be positive")
