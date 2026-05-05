# UI_FRONTEND_SYSTEM_BLUEPRINT.md

## Idea central

La interfaz debe sentirse como un centro de operación acuícola: clara, densa, visual y accionable. No debe parecer una landing page. La primera pantalla debe mostrar el estado real del sistema, el estanque seleccionado, las mediciones recientes, el último snapshot del gemelo digital, alertas abiertas, recomendaciones y acciones pendientes.

El frontend consume el backend como API. La base pública actual del backend es:

`http://37.60.226.53:8000/api/v1`

La documentación técnica visible para desarrollo está en:

`http://37.60.226.53:8000/docs`

## Estructura visual principal

La app debe tener una barra superior con nombre del sistema, estado de conexión API, selector de granja y selector de estanque. A la izquierda debe haber navegación fija con estas áreas: Operación, Ingesta, Gemelo Digital, Modelos, Alertas, Actuación y Configuración.

El área central cambia según la vista. Siempre debe conservar el contexto actual: granja, estanque, hora de última actualización y estado general. El usuario no debe perderse entre pantallas.

## Pantalla Operación

Debe ser el dashboard inicial. Arriba se ven tarjetas compactas: oxígeno disuelto, temperatura, biomasa, alimentación, sensores activos, alertas abiertas y última ejecución del gemelo digital.

Debajo debe verse una línea de tiempo o gráfico con mediciones limpias recientes. A la derecha, una columna de prioridad con alertas y recomendaciones. Si no hay datos, la UI debe mostrar claramente que faltan mediciones, no simular valores.

Rutas usadas:

- `GET /health`
- `GET /farms`
- `GET /ponds`
- `GET /sensors`
- `GET /ponds/{pond_id}/state`
- `GET /ponds/{pond_id}/timeseries`
- `GET /digital-twin/{pond_id}/latest`
- `GET /alerts`
- `GET /recommendations`

## Gestión Acuícola

Debe permitir crear y revisar granjas, estanques, sensores y actuadores. Visualmente debe ser una vista de administración simple: tabla principal, panel lateral de detalle y formularios breves.

Cada granja muestra sus estanques. Cada estanque muestra sensores instalados, actuadores disponibles y estado actual. Los sensores deben verse por variable medida; los actuadores por tipo y estado.

Rutas usadas:

- `POST /farms`
- `GET /farms`
- `GET /farms/{farm_id}`
- `POST /ponds`
- `GET /ponds`
- `GET /ponds/{pond_id}`
- `POST /sensors`
- `GET /sensors`
- `GET /sensors/{sensor_id}`
- `POST /actuators`
- `GET /actuators`
- `GET /actuators/{actuator_id}`

## Ingesta de Mediciones

Debe tener una pantalla para cargar mediciones manuales o desde integraciones. El usuario elige granja, estanque, sensor, variable, valor, unidad y fuente.

Después de guardar, la UI debe mostrar dos cosas: la medición raw recibida y la medición clean generada. Si el valor llega vacío o inválido, debe verse como advertencia, no como fallo silencioso.

La parte visual debe incluir una tabla de mediciones raw, una tabla de mediciones clean y un gráfico temporal filtrable por variable.

Rutas usadas:

- `POST /measurements/ingest`
- `GET /measurements/raw`
- `GET /measurements/clean`
- `GET /ponds/{pond_id}/measurements`
- `GET /ponds/{pond_id}/timeseries`

## Gemelo Digital

Debe ser la vista más importante. Visualmente debe tener un botón claro para generar snapshot del estanque actual. Al ejecutarlo, se muestran cuatro bloques: estado actual, salidas de modelos, riesgos y recomendaciones.

El snapshot debe verse como una ficha trazable: ID, fecha, estanque, datos faltantes, modelos ejecutados, modelos omitidos, errores de modelo y alertas generadas. Si un modelo está pendiente de fórmula o artefacto, debe mostrarse como “no ejecutable todavía”, nunca como predicción real.

Rutas usadas:

- `GET /ponds/{pond_id}/state`
- `POST /digital-twin/{pond_id}/snapshot`
- `POST /digital-twin/{pond_id}/snapshots`
- `GET /digital-twin/snapshots/{snapshot_id}`
- `GET /digital-twin/{pond_id}/latest`
- `GET /digital-twin/{pond_id}/risks`
- `GET /digital-twin/{pond_id}/recommendations`

## Modelos

Debe existir un catálogo visual de modelos. Cada tarjeta de modelo debe mostrar código, nombre, tipo, fuente, versión, entradas requeridas, salidas esperadas y estado de preparación.

Al entrar a un modelo, la UI debe mostrar un formulario de ejecución con campos según las entradas del modelo. Los modelos listos pueden ejecutarse. Los modelos pendientes de fórmula o artefacto deben verse bloqueados o en modo dry-run/metadata, según corresponda.

Rutas usadas:

- `GET /models`
- `GET /models/{model_code}`
- `POST /models/{model_code}/run`

Modelos que deben aparecer:

- `DO_DYNAMIC_0D_ROYER_2021`
- `BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010`
- `FEEDING_SATIETY_RULES`
- `DAILY_RATION_MODEL`
- `BPNN_MEA_FEED_INTAKE`
- `PEARSON_LSTM_ATTENTION_WQ`
- `FISH_COUNTING_MODEL`
- `FISH_SIZE_WEIGHT_ESTIMATION`

## Alertas y Recomendaciones

Debe verse como una bandeja operacional. Las alertas se agrupan por severidad y estanque. Las recomendaciones se agrupan por prioridad y riesgo origen.

Cada alerta debe mostrar código, severidad, mensaje, evidencia y snapshot origen. Cada recomendación debe mostrar acción sugerida, explicación, si requiere aprobación y el riesgo que la generó.

Rutas usadas:

- `GET /alerts`
- `GET /recommendations`
- `GET /digital-twin/{pond_id}/risks`
- `GET /digital-twin/{pond_id}/recommendations`

## Actuación Segura

Esta vista no debe parecer un panel de control automático agresivo. Debe sentirse como una cola de aprobación. Primero se ve la recomendación, luego los actuadores disponibles, luego la política de seguridad y finalmente el comando pendiente.

El comando nunca debe mostrarse como ejecutado físicamente. Debe verse como `pending_dispatch`. La UI debe dejar claro quién aprobó, cuándo aprobó y qué actuador fue seleccionado.

Rutas usadas:

- `GET /actuators`
- `POST /actuators`
- `POST /actuation-commands/from-recommendation`
- `GET /actuation-commands`

## Flujo completo esperado

El usuario crea o selecciona una granja. Luego crea o selecciona un estanque. Después registra sensores y actuadores. Ingresa mediciones. El sistema muestra estado actual. El usuario genera un snapshot del gemelo digital. El snapshot produce riesgos, alertas y recomendaciones. Si una recomendación requiere acción, el usuario revisa la evidencia, aprueba manualmente y genera un comando pendiente.

Ese flujo debe sentirse continuo, no como páginas aisladas.

## Estados visuales obligatorios

La UI debe diferenciar claramente estos estados: cargando, sin datos, datos incompletos, modelo no ejecutable, alerta abierta, recomendación pendiente, aprobación requerida, comando pendiente y error de API.

Nunca debe inventar datos para llenar espacios. Si falta información, debe mostrar “dato faltante” o “sin mediciones recientes”.

## Resultado visual esperado

Al usar todo el sistema, una persona debe poder responder rápido:

- qué estanque estoy viendo;
- qué variables están medidas;
- qué datos faltan;
- qué modelos están disponibles;
- qué riesgos existen;
- qué recomienda el gemelo digital;
- qué alertas están abiertas;
- qué acciones fueron aprobadas;
- qué comandos quedaron pendientes.

Ese es el criterio visual principal para el frontend.
