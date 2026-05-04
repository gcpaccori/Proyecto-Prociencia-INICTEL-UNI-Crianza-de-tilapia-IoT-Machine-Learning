# 01_CONTEXT_MASTER.md

## Contexto maestro del proyecto

Este proyecto implementa un backend Python experto para acuicultura de precisión basado en Gemelo Digital, Internet de las Cosas, modelos matemáticos, modelos bioenergéticos, modelos predictivos de Machine Learning, modelos de Deep Learning, visión artificial, motor de recomendaciones y posible actuación sobre dispositivos físicos.

El proyecto base es:

> "Validación de una estación de monitoreo de calidad de agua y dosificación de Floc bacteriano para crianza masiva de peces en piscigranjas artificiales con geomembrana utilizando aprendizaje automático e Internet de las Cosas".

El backend NO debe entenderse como una simple API REST. Debe entenderse como un motor de Gemelo Digital acuícola que:

1. Recibe datos reales de sensores IoT, cámaras, alimentación, biomasa, mortalidad y operación manual.
2. Guarda datos crudos y datos limpios con trazabilidad.
3. Normaliza unidades y valida calidad de datos.
4. Ejecuta modelos matemáticos, bioenergéticos, predictivos y visuales.
5. Simula oxígeno disuelto, calidad de agua, crecimiento, alimentación, biomasa y riesgos.
6. Genera alertas y recomendaciones justificadas.
7. Registra qué modelo generó cada resultado, con versión, parámetros, entradas y procedencia.
8. Permite integración futura con actuadores: aireadores, bombas, válvulas, oxigenación y comederos.

## Fuentes documentales obligatorias

### Informe 015 - Gemelo Digital aplicado a acuicultura

Archivo Markdown: `../01_markdown_reports/Informe015_Gemelo_Digital.md`

Rol dentro del backend:

- Define el concepto de Gemelo Digital.
- Describe el flujo físico-digital con observación, interpretación, decisión y actuación.
- Separa componentes: agua y peces.
- Indica que el sistema debe trabajar con sensores en tiempo real, datos históricos, modelos matemáticos y retroalimentación al sistema real.
- Contiene diagramas del flujo conceptual, delimitación del objeto físico, modelos bioenergético + OD, servicios de alimentación, monitoreo ambiental, salud, visión artificial y acuicultura inteligente.

### Informe 016 - Estimación de oxígeno disuelto

Archivo Markdown: `../01_markdown_reports/Informe016_Oxigeno_Disuelto.md`

Rol dentro del backend:

- Define modelos dinámicos de oxígeno disuelto.
- Incluye el modelo 0D de OD en canal de cultivo.
- Considera caudal, concentración de OD, temperatura, biomasa, respiración, reaireación y suministro de oxígeno.
- Describe consumo de oxígeno con patrón sinusoidal diario.
- Incluye calibración con RMSE.
- Incluye modelos de balance de oxígeno en RAS, demanda suplementaria y predicción de OD/amoniaco.

### Informe 017 - Crecimiento, alimentación y modelos ML

Archivo Markdown: `../01_markdown_reports/Informe017_Crecimiento_Alimentacion_ML.md`

Rol dentro del backend:

- Define BPNN + MEA para predicción de consumo de alimento.
- Entradas principales: temperatura del agua, oxígeno disuelto, peso promedio de peces y número de peces.
- Arquitectura reportada: 4-10-1.
- Define normalización Min-Max.
- Describe reglas prácticas de saciedad alimentaria.
- Incluye Pearson-LSTM-AM para predicción de calidad de agua.
- Variables de calidad de agua: pH, temperatura, OD, nitrógeno amoniacal, nitrito, ORP y turbidez.
- Incluye preprocesamiento: interpolación lineal, regla 3 sigma, normalización y métricas RMSE, MAE, MAPE, R2.

### Informe 018 - Modelos bioenergéticos

Archivo Markdown: `../01_markdown_reports/Informe018_Modelos_Bioenergeticos.md`

Rol dentro del backend:

- Define modelo bioenergético individual para Sparus aurata.
- Incluye anabolismo neto, catabolismo en ayunas, ingestión, asimilación, digestibilidad, alimento no consumido y producción fecal.
- Usa peso húmedo, temperatura, disponibilidad de alimento y composición de dieta.
- Considera proteínas, carbohidratos, lípidos, energía, digestibilidad y calibración de parámetros.

## Definición estricta de "modelo"

Cuando el usuario diga "modelo", NO se debe asumir automáticamente Machine Learning. En este proyecto, "modelo" puede significar:

- modelo de Gemelo Digital;
- modelo matemático/mecanicista;
- modelo bioenergético;
- modelo de calidad de agua;
- modelo de oxígeno disuelto;
- modelo de amonio/nitrificación;
- modelo de crecimiento;
- modelo de alimentación;
- modelo ML clásico;
- modelo Deep Learning;
- modelo de visión artificial;
- modelo de reglas;
- modelo de decisión;
- modelo de base de datos/dominio.

El archivo `02_MODEL_CATALOG.yaml` es la fuente principal para resolver esta ambigüedad.

## Niveles funcionales del sistema

### Nivel 1: Datos

- Sensores IoT.
- Cámaras.
- Registros manuales.
- Alimentación.
- Biomasa.
- Mortalidad.
- Calidad de agua.
- Operación de dispositivos.

### Nivel 2: Modelos especializados

- OD dinámico.
- Balance de oxígeno.
- Amonio/nitrificación.
- Bioenergética.
- Crecimiento.
- Alimentación.
- BPNN-MEA.
- Pearson-LSTM-AM.
- Visión artificial.

### Nivel 3: Gemelo Digital

- Estado actual.
- Diagnóstico.
- Predicción.
- Simulación.
- Escenarios.
- Riesgos.

### Nivel 4: Decisión y actuación

- Alertas.
- Recomendaciones.
- Acciones manuales.
- Acciones automáticas con aprobación.
- Auditoría.

## Principio de implementación

No crear scripts sueltos. Todo debe integrarse como backend modular con contratos, repositorios, servicios, workers, registry de modelos, almacenamiento de ejecuciones y auditoría.
