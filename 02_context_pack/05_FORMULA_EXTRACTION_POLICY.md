# 05_FORMULA_EXTRACTION_POLICY.md

## Política para fórmulas, imágenes y tablas convertidas desde DOCX

Los informes originales contienen texto, imágenes, diagramas, tablas y ecuaciones. Al convertir DOCX a Markdown:

- Algunas ecuaciones quedaron como LaTeX/texto.
- Algunas tablas quedaron como Markdown.
- Algunas figuras, diagramas y ecuaciones incrustadas quedaron como imágenes en carpetas `*_media/`.

## Regla crítica

Cuando una fórmula no esté completamente legible como texto, NO se debe inventar.

Debe usarse este placeholder:

```text
FORMULA_PENDING_EXTRACTION
```

Y crear un registro de deuda técnica:

```yaml
formula_pending:
  source_report: "INFORME016"
  markdown_file: "Informe016_Oxigeno_Disuelto.md"
  location: "Tabla 2 / imagen correspondiente"
  equation_number: "si existe"
  known_variables:
    - variable_1
    - variable_2
  action_required: "Extraer manualmente desde imagen o validar contra paper fuente"
```

## Uso correcto en implementación

Si el modelo requiere una fórmula pendiente:

1. Crear clase del modelo con contrato.
2. Crear esquema de entradas/salidas.
3. Crear placeholders de parámetros.
4. Bloquear ejecución productiva con error explícito:

```text
Cannot execute model: formula pending extraction from source report.
```

5. Permitir solo modo `dry_run` o `metadata_only` hasta validar la fórmula.

## Modelos con mayor probabilidad de fórmulas pendientes

- `DO_DYNAMIC_0D_ROYER_2021`
- `DO_MASS_BALANCE_RAS`
- `AMMONIA_PREDICTIVE_MODEL`
- `BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010`
- `INGESTION_OPTIMAL_MODEL`
- `ASSIMILATION_DIET_MODEL`
- `FECES_PRODUCTION_MODEL`
- `FASTING_CATABOLISM_MODEL`

## Prioridad de extracción manual

1. Fórmulas de OD dinámico y balance de masa.
2. Fórmulas de bioenergética principal.
3. Fórmulas de alimentación y crecimiento.
4. Fórmulas de amonio/nitrificación.
5. Fórmulas auxiliares de métricas.
