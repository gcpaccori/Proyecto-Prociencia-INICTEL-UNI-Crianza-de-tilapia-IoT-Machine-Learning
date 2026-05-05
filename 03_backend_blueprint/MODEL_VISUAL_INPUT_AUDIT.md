# Auditoria visual de modelos e inputs

## Conexion frontend

El frontend debe consumir el backend publico en `http://37.60.226.53:8000`.

Si se despliega en Vercel, la variable visual/API debe apuntar a ese backend. Si queda vacia, el navegador consulta el dominio de Vercel y aparecen 404 en `/health`, `/farms`, `/ponds` y demas rutas.

El backend acepta rutas con `/api/v1` y tambien rutas directas para el frontend compilado: `/health`, `/farms`, `/ponds`, `/sensors`, `/measurements/clean`, `/ponds/{pond_id}/timeseries`, `/models`, `/alerts`, `/recommendations`, `/actuators`.

## Datos reales disponibles

La base viva `sismapiscis` se usa solo como lectura. La aplicacion trabaja sobre su propia base `aquaculture_digital_twin`.

Datos que hoy si llegan automaticamente:

- Granja y piscina reales.
- Sensores virtualizados desde mediciones historicas.
- Temperatura del agua.
- pH.
- Oxigeno disuelto.
- Ion nitrato.
- Actuadores virtuales: aireador, alimentador y bomba.

Datos que hoy no existen en la base viva:

- Biometrias reales.
- Peso promedio.
- Longitud de pez.
- Conteo de peces.
- Biomasa.
- Historial de alimentacion confiable.
- Imagenes o frames para vision.
- Artefactos entrenados de ML y vision.

## Grafico principal

El grafico de serie temporal debe iniciar con temperatura del agua. Esa serie ya queda optimizada por defecto para no mezclar pH, oxigeno y nitrato en una sola linea.

Visualmente debe verse como un grafico de variable seleccionable:

- Temperatura.
- pH.
- Oxigeno disuelto.
- Ion nitrato.

Cada cambio de variable debe redibujar una sola linea, con el ultimo valor visible y la unidad junto al selector.

## DO_DYNAMIC_0D_ROYER_2021

Autocompleta:

- Oxigeno disuelto actual como oxigeno inicial.
- Temperatura del agua.
- Volumen de piscina si existe en metadata.

Formulario necesario:

- Oxigeno de entrada.
- Caudal.
- Biomasa de peces.
- Suministro de oxigeno.
- Reaireacion.
- Horizonte de simulacion.

Estado visual: mostrar como no predictivo productivo. Solo dry-run o metadata hasta validar la formula fuente.

## BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010

Autocompleta:

- Temperatura del agua.

Formulario necesario:

- Peso humedo individual.
- Racion diaria.
- Fraccion proteica.
- Fraccion lipidica.
- Fraccion carbohidratos.
- Digestibilidades.
- Energia del tejido somatico.

Estado visual: mostrar como no predictivo productivo hasta validar formulas y parametros fuente.

## FEEDING_SATIETY_RULES

Autocompleta:

- No depende de sensores actuales.

Formulario necesario:

- Categoria de comportamiento alimentario.
- Si queda alimento remanente.
- Observacion corta de reaccion de peces.

Estado visual: listo. Debe mostrarse como formulario operativo simple con resultado inmediato: detener alimentacion, riesgo de desperdicio y recomendacion.

## DAILY_RATION_MODEL

Autocompleta:

- Nada confiable con la base actual.

Formulario necesario:

- Factor de conversion alimentaria.
- Crecimiento diario.
- Longitud del pez.
- Peso individual.

Estado visual: listo si el operador completa biometria. Debe vivir en una seccion de alimentacion/biometria, no en sensores.

## BPNN_MEA_FEED_INTAKE

Autocompleta:

- Temperatura del agua.
- Oxigeno disuelto.

Formulario necesario:

- Peso promedio del pez.
- Numero de peces.

Estado visual: bloqueado para prediccion real hasta cargar artefacto entrenado. Puede mostrar auditoria de inputs y dry-run.

## PEARSON_LSTM_ATTENTION_WQ

Autocompleta como serie:

- pH.
- Temperatura.
- Oxigeno disuelto.

Formulario o nueva captura necesaria:

- Amoniaco nitrogenado.
- Nitrito.
- ORP.
- Turbidez.

Estado visual: bloqueado para prediccion real hasta cargar artefacto LSTM y completar sensores faltantes.

## FISH_COUNTING_MODEL

Autocompleta:

- Nada desde la base actual.

Formulario necesario:

- Imagen o frame.
- Calibracion de camara.

Estado visual: bloqueado hasta existir carga de imagen/frame y artefacto de vision.

## FISH_SIZE_WEIGHT_ESTIMATION

Autocompleta:

- Especie puede sugerirse como tilapia.

Formulario necesario:

- Imagen o frame.
- Parametros de calibracion.
- Especie confirmada.

Estado visual: bloqueado hasta existir carga de imagen/frame y artefacto de vision.

## Pantallas que no deben quedar al aire

Inicio operativo:

- Estado de API.
- Granja activa.
- Piscina activa.
- Ultimos valores reales.
- Grafico por variable.
- Alertas/recomendaciones.

Modelos:

- Catalogo de modelos.
- Auditoria de inputs por modelo.
- Campos autocompletados visibles como bloqueados o prellenados.
- Campos faltantes como formulario.
- Estado claro: listo, requiere formulario, requiere artefacto, requiere validacion de formula.

Actuacion:

- Aireador, alimentador y bomba como actuadores disponibles.
- Toda orden debe salir como pendiente de aprobacion manual.

