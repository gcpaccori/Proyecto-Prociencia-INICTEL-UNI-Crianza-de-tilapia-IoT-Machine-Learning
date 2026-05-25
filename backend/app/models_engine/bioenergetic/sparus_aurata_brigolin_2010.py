from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.bioenergetic.brigolin_math import brigolin_step


class FormulaPendingExtractionError(RuntimeError):
    pass


class BioenergeticSparusAurataBrigolin2010(BaseModelRunner):
    model_code = "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010"
    model_version = "1.0.0"
    source_report = "INFORME018"

    required_inputs = {
        "wet_weight_g": "g",
        "water_temperature_c": "degC",
        "feed_ration_day_1": "day^-1",
        "protein_fraction": "fraction",
        "lipid_fraction": "fraction",
        "carbohydrate_fraction": "fraction",
        "protein_digestibility": "fraction",
        "lipid_digestibility": "fraction",
        "carbohydrate_digestibility": "fraction",
        "energy_content_somatic_tissue_kj_g": "kJ/g",
    }
    required_outputs = {
        "predicted_weight_g": "g",
        "net_anabolism_j_day": "J/day",
        "fasting_catabolism_j_day": "J/day",
        "feed_intake_day_1": "day^-1",
        "uneaten_feed_g": "g",
        "feces_production_g_day": "g/day",
        "temperature_effect": "factor",
    }
    fraction_inputs = {
        "protein_fraction",
        "lipid_fraction",
        "carbohydrate_fraction",
        "protein_digestibility",
        "lipid_digestibility",
        "carbohydrate_digestibility",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="bioenergetic",
        name="Modelo bioenergetico individual Sparus aurata",
        source_reference=(
            "Brigolin et al., 2010; "
            "formulas_implementacion_gemelo_acuicultura.md seccion 6"
        ),
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "Modelo individual para Sparus aurata.",
            "La racion se limita por ingestion maxima y temperatura.",
            "Temperaturas bajo 12 C detienen ingestion.",
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
            self._require_numeric(input_name, input_value.value)

        self._require_positive_number(
            "wet_weight_g",
            model_input.inputs["wet_weight_g"].value,
        )
        self._require_positive_number(
            "energy_content_somatic_tissue_kj_g",
            model_input.inputs["energy_content_somatic_tissue_kj_g"].value,
        )

        for input_name in self.fraction_inputs:
            self._require_fraction(input_name, model_input.inputs[input_name].value)

        diet_fraction_sum = sum(
            float(model_input.inputs[input_name].value)
            for input_name in (
                "protein_fraction",
                "lipid_fraction",
                "carbohydrate_fraction",
            )
        )
        if diet_fraction_sum > 1.0:
            raise ValueError("diet fractions must sum to 1.0 or less")

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        values = brigolin_step(
            wet_weight_g=float(model_input.inputs["wet_weight_g"].value),
            water_temperature_c=float(model_input.inputs["water_temperature_c"].value),
            feed_ration_day_1=float(model_input.inputs["feed_ration_day_1"].value),
            protein_fraction=float(model_input.inputs["protein_fraction"].value),
            lipid_fraction=float(model_input.inputs["lipid_fraction"].value),
            carbohydrate_fraction=float(model_input.inputs["carbohydrate_fraction"].value),
            protein_digestibility=float(
                model_input.inputs["protein_digestibility"].value
            ),
            lipid_digestibility=float(model_input.inputs["lipid_digestibility"].value),
            carbohydrate_digestibility=float(
                model_input.inputs["carbohydrate_digestibility"].value
            ),
            energy_content_somatic_tissue_kj_g=float(
                model_input.inputs["energy_content_somatic_tissue_kj_g"].value
            ),
            dt_day=float(model_input.parameters.get("dt_day", 1.0)),
        )
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                output_name: ModelOutputValue(
                    value=values[output_name],
                    unit=unit,
                )
                for output_name, unit in self.required_outputs.items()
            },
            unit_map=self.required_outputs,
            confidence=None,
            explanation="Brigolin bioenergetic growth step calculated from diet, temperature and fasting catabolism.",
            explainability={
                "formula": "dw/dt = (A - C) / epsilon_T",
                "delta_weight_g_day": values["delta_weight_g_day"],
                "somatic_energy_content_kj_g": values["somatic_energy_content_kj_g"],
            },
        )

    @staticmethod
    def _require_numeric(name: str, value: object) -> None:
        try:
            float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc

    @staticmethod
    def _require_positive_number(name: str, value: object) -> None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if numeric_value <= 0:
            raise ValueError(f"{name} must be positive")

    @staticmethod
    def _require_fraction(name: str, value: object) -> None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if numeric_value < 0 or numeric_value > 1:
            raise ValueError(f"{name} must be between 0 and 1")
