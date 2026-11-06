# Paquete de contexto backend - Gemelo Digital Acuícola

Este paquete convierte los informes DOCX a Markdown y agrega archivos de contexto para que GPT/Codex no tenga que adivinar qué significa "modelos".

## Estructura

```text
00_original_docx/
  Informes originales en DOCX.

01_markdown_reports/
  Informes convertidos a Markdown.
  Cada informe tiene su carpeta *_media/ con figuras, diagramas, tablas e imágenes extraídas.

02_context_pack/
  01_CONTEXT_MASTER.md
  02_MODEL_CATALOG.yaml
  03_BACKEND_IMPLEMENTATION_RULES.md
  04_CODEX_MASTER_PROMPT.md
  05_FORMULA_EXTRACTION_POLICY.md

03_backend_blueprint/
  ARCHITECTURE_MASTER_PLAN.md
  DATABASE_BLUEPRINT.md
  API_ENDPOINTS.md
  BACKEND_MODULE_MAP.md
```
```

Cambia el contenido de `LICENSE` para poner tu nombre/organización donde aparece `<Nombre del autor>`.


## Reproducir la evaluación de modelos de crecimiento (2026)

La reproducción auditada de los modelos TGC, von Bertalanffy, SISMAPISCIS Ridge y SISMAPISCIS gaussiano —con código Python, datos agregados, pruebas 8/8, métricas y capturas PNG/SVG— está documentada en [reproducibility/growth_2026/README.md](reproducibility/growth_2026/README.md). No requiere credenciales ni acceso a la base de datos productiva.
