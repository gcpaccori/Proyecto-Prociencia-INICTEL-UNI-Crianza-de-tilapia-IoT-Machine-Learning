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


class BioenergeticSparusAurataBrigolin2010(BaseModelRunner):
    model_code = "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010"
    model_version = "0.1.0"
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
        source_reference="Brigolin et al., 2010; Informe018 equations 1-10",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "Modelo individual para Sparus aurata.",
            "El crecimiento depende de peso humedo, temperatura, alimento y dieta.",
            "La produccion fecal depende de digestibilidad de proteinas, lipidos y carbohidratos.",
            "Los parametros fisiologicos deben validarse contra la fuente antes de ejecucion productiva.",
        ],
    )

    formula_pending = {
        "status": FORMULA_PENDING_EXTRACTION,
        "source_report": source_report,
        "markdown_file": "01_markdown_reports/Informe018_Modelos_Bioenergeticos.md",
        "location": "Equations 1-10 and converted Table 1 context",
        "known_variables": [
            "W",
            "A",
            "C",
            "epsilon_T",
            "I",
            "I_max",
            "T_w",
            "T_0",
            "T_m",
            "b",
            "m",
            "alpha",
            "C_p",
            "C_c",
            "C_l",
            "beta_p",
            "beta_c",
            "beta_l",
            "k_0",
            "p_k",
            "n",
        ],
        "action_required": (
            "Validar ecuacion 4, tabla de parametros y unidades energeticas "
            "contra el informe original o paper fuente antes de habilitar prediccion."
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
        metadata_only = bool(model_input.parameters.get("metadata_only", False))
        dry_run = bool(model_input.parameters.get("dry_run", False))
        if not (metadata_only or dry_run):
            raise FormulaPendingExtractionError(
                "Cannot execute model: formula pending extraction from source report."
            )

        warnings = [
            "FORMULA_PENDING_EXTRACTION: Informe018 equations require manual parameter validation.",
            "Execution allowed only for dry_run or metadata_only.",
        ]
        outputs = {
            "predicted_weight_g": ModelOutputValue(value=None, unit="g"),
            "net_anabolism_j_day": ModelOutputValue(value=None, unit="J/day"),
            "fasting_catabolism_j_day": ModelOutputValue(value=None, unit="J/day"),
            "feed_intake_day_1": ModelOutputValue(value=None, unit="day^-1"),
            "uneaten_feed_g": ModelOutputValue(value=None, unit="g"),
            "feces_production_g_day": ModelOutputValue(value=None, unit="g/day"),
        }
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs=outputs,
            unit_map=self.required_outputs,
            confidence=None,
            warnings=warnings,
            explanation=(
                "Formula and parameter set pending manual validation from Informe018."
            ),
            explainability={
                "formula_status": self.formula_pending,
                "assumptions": self.metadata.assumptions,
                "inputs": self.metadata.inputs,
                "outputs": self.metadata.outputs,
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
