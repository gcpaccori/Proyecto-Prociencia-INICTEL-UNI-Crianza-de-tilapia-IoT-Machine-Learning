from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)


FORMULA_PENDING_EXTRACTION = "FORMULA_PENDING_EXTRACTION"


class FormulaPendingExtractionError(RuntimeError):
    pass


class DissolvedOxygen0DRoyer2021(BaseModelRunner):
    model_code = "DO_DYNAMIC_0D_ROYER_2021"
    model_version = "0.1.0"
    source_report = "INFORME016"

    required_inputs = {
        "do_initial_mg_l": "mg/L",
        "do_influent_mg_l": "mg/L",
        "water_temperature_c": "degC",
        "flow_rate_l_h": "L/h",
        "raceway_volume_l": "L",
        "fish_biomass_kg": "kg",
        "oxygen_supply_rate_mg_l_h": "mg/L/h",
        "reaeration_rate_h_1": "h^-1",
        "simulation_horizon_minutes": "min",
    }
    required_outputs = {
        "do_forecast_mg_l": "mg/L",
        "oxygen_consumption_rate": "mg/L/h",
        "oxygen_demand": "mg/L",
        "hypoxia_risk": "risk_level",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="mechanistic",
        name="Modelo dinamico 0D de oxigeno disuelto",
        source_reference="Royer et al., 2021; Informe016 Tabla 2",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "Agua del canal bien mezclada.",
            "Sin actividad fotosintetica dentro del canal.",
            "Consumo de oxigeno incluido unicamente por respiracion de peces.",
            "Incluye intercambio con la atmosfera.",
            "Incluye entrada/salida por caudal y suministro controlable de oxigeno.",
        ],
    )

    formula_pending = {
        "status": FORMULA_PENDING_EXTRACTION,
        "source_report": source_report,
        "markdown_file": "01_markdown_reports/Informe016_Oxigeno_Disuelto.md",
        "location": "Tabla 2 / image2.png",
        "known_variables": [
            "Q",
            "S",
            "MR",
            "V",
            "do_initial_mg_l",
            "do_influent_mg_l",
            "reaeration_rate_h_1",
        ],
        "action_required": (
            "Extraer manualmente la ecuacion de balance de masa desde la imagen "
            "o validar contra el paper fuente antes de habilitar prediccion."
        ),
    }

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
        metadata_only = bool(model_input.parameters.get("metadata_only", False))
        dry_run = bool(model_input.parameters.get("dry_run", False))
        if not (metadata_only or dry_run):
            raise FormulaPendingExtractionError(
                "Cannot execute model: formula pending extraction from source report."
            )

        warnings = [
            "FORMULA_PENDING_EXTRACTION: Informe016 Tabla 2 equation is stored as image2.png.",
            "Execution allowed only for dry_run or metadata_only.",
        ]
        outputs = {
            "do_forecast_mg_l": ModelOutputValue(value=None, unit="mg/L"),
            "oxygen_consumption_rate": ModelOutputValue(value=None, unit="mg/L/h"),
            "oxygen_demand": ModelOutputValue(value=None, unit="mg/L"),
            "hypoxia_risk": ModelOutputValue(
                value="not_computed_formula_pending",
                unit="risk_level",
            ),
        }
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs=outputs,
            unit_map=self.required_outputs,
            confidence=None,
            warnings=warnings,
            explanation="Formula pending manual extraction from Informe016 Tabla 2.",
            explainability={
                "formula_status": self.formula_pending,
                "assumptions": self.metadata.assumptions,
                "inputs": self.metadata.inputs,
                "outputs": self.metadata.outputs,
            },
        )

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
