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

## Cómo usarlo con GPT/Codex

Pega este mandato al inicio de la tarea:

```text
Lee primero 01_CONTEXT_MASTER.md, 02_MODEL_CATALOG.yaml y 03_BACKEND_IMPLEMENTATION_RULES.md. Luego usa los Markdown completos de 01_markdown_reports como fuente de verdad. No interpretes "modelo" como ML solamente. Cada implementación debe respetar model_code, procedencia, entradas, salidas, unidades, supuestos, parámetros y trazabilidad.
```

## Nota sobre fórmulas e imágenes

Pandoc convirtió texto, tablas y ecuaciones legibles a Markdown/LaTeX cuando fue posible. Las figuras, tablas como imagen, diagramas y fórmulas que estaban incrustadas como imagen se conservaron en las carpetas `*_media`. Si una fórmula no queda textual, debe tratarse como pendiente de extracción manual, no como permiso para inventarla.

## Preparar y subir a GitHub

Para preparar este proyecto y subirlo a GitHub, sigue estos pasos locales desde la raíz del proyecto.

- 1) Asegúrate de tener `git` y, opcionalmente, la CLI `gh` instalada.
- 2) Ignora archivos no deseados (ya añadimos `.gitignore`).

Inicializa el repositorio y haz el primer commit:

```bash
git init
git branch -M main
git add .
git commit -m "Initial commit"
```

Crear el repositorio remoto y subir (opción recomendada: usar `gh`):

```bash
# usando la CLI de GitHub
gh repo create <USERNAME>/<REPO_NAME> --public --source=. --remote=origin --push

# o, si creas el repo en github.com manualmente, agrega el remote y sube:
git remote add origin git@github.com:<USERNAME>/<REPO_NAME>.git
git push -u origin main
```

Antes de subir, puedes ejecutar tests localmente (recomendado):

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

Cambia el contenido de `LICENSE` para poner tu nombre/organización donde aparece `<Nombre del autor>`.
