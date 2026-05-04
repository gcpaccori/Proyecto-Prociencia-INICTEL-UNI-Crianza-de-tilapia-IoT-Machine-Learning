# 03_BACKEND_IMPLEMENTATION_RULES.md

## Regla 1: No interpretar "modelo" genéricamente

Cuando el usuario diga "modelo", primero revisar `02_MODEL_CATALOG.yaml`.

Un modelo puede ser:

- `digital_twin`
- `mechanistic`
- `bioenergetic`
- `bioenergetic_submodel`
- `machine_learning`
- `deep_learning`
- `computer_vision`
- `rule_based`
- `decision_engine`
- `actuation_policy`
- `database_entity`

No programar nada sin identificar el `model_code`.

## Regla 2: Todo modelo debe tener trazabilidad

Cada ejecución debe guardar:

- `run_id`
- `model_code`
- `model_version`
- `source_report`
- `source_reference`
- `input_data`
- `parameters`
- `output_data`
- `warnings`
- `confidence`
- `created_at`
- `execution_status`
- `error_message`, si aplica

## Regla 3: Nunca mezclar datos crudos con datos limpios

Toda medición IoT debe guardarse en dos capas:

1. `raw_measurement`: dato original, payload original, unidad original.
2. `clean_measurement`: dato validado, normalizado y listo para modelos.

Nunca sobrescribir el dato crudo.

## Regla 4: Las unidades son obligatorias

Todo valor numérico debe tener unidad explícita.

Unidades estándar iniciales:

- temperatura: `degC`
- oxígeno disuelto: `mg/L`
- biomasa: `kg`
- peso individual: `g`
- alimento: `g` o `kg`
- caudal: `L/h` o `m3/h`
- volumen: `L` o `m3`
- tiempo: `s`, `h`, `day`
- pH: `pH`
- ORP: `mV`
- turbidez: `NTU`

## Regla 5: No inventar fórmulas faltantes

Si una ecuación aparece como imagen o no se puede leer claramente, crear placeholder:

```text
FORMULA_PENDING_EXTRACTION
```

Registrar:

- `source_report`
- `markdown_file`
- `page_or_figure_reference`, si existe
- `equation_number`, si existe
- `variables_known`
- `status: pending_manual_extraction`

## Regla 6: Separar modelos físicos, ML, visión y orquestación

Estructura obligatoria:

```text
models_engine/
  base/
  mechanistic/
  bioenergetic/
  ml/
  vision/
  orchestrators/
```

El Gemelo Digital orquesta. No debe contener toda la lógica interna de cada modelo.

## Regla 7: Cada modelo debe implementar contrato común

Cada modelo debe implementar:

```text
validate_inputs()
preprocess()
predict()
postprocess()
explain()
save_run()
```

Salida mínima obligatoria:

```json
{
  "model_code": "...",
  "model_version": "...",
  "source_report": "...",
  "prediction": {},
  "unit_map": {},
  "confidence": null,
  "warnings": [],
  "explanation": "...",
  "run_id": "..."
}
```

## Regla 8: Base de datos común y especializada

Debe existir base común para:

- granjas;
- estanques/canales;
- sensores;
- especies;
- ciclos productivos;
- lotes;
- alimentación;
- biomasa;
- modelos;
- predicciones;
- auditoría.

Y tablas especializadas para:

- series temporales IoT;
- resultados de modelos;
- visión artificial;
- entrenamiento ML;
- actuadores;
- recomendaciones.

## Regla 9: No crear notebooks como backend

Los notebooks pueden usarse para validación científica, pero el backend productivo debe vivir en servicios, repositorios, workers y modelos versionados.

## Regla 10: Si falta contexto, buscar primero en los Markdown convertidos

Antes de inventar, buscar en:

```text
../01_markdown_reports/Informe015_Gemelo_Digital.md
../01_markdown_reports/Informe016_Oxigeno_Disuelto.md
../01_markdown_reports/Informe017_Crecimiento_Alimentacion_ML.md
../01_markdown_reports/Informe018_Modelos_Bioenergeticos.md
```

Si una imagen o fórmula no está textual, revisar la carpeta `*_media/` correspondiente.
