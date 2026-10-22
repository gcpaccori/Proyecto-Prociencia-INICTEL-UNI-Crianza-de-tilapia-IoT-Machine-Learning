# Entrenamiento completo disponible — 21/10/2026, hora de Lima

La ejecución usa el identificador UTC `20261022`, que corresponde a la noche del
21/10/2026 en Perú. Se completaron tres trabajos: reajuste de crecimiento, selección
y reajuste de diez predictores de sensores, y un integrador ML experimental.
No se generaron etiquetas de peso mediante fórmulas, interpolación ni simulación.

## Datos y resultado del crecimiento

Lectura fresca de la base configurada `sismapiscis`: 7 biometrias de un lote, última
16/10/2026; 34.751 lecturas de agua y 2.379 de luz. Se excluyó del agregado una
lectura de agua fechada en 2000. El snapshot contiene 6.637 horas de agua y 311
horas de luz con alguna observación. SHA256 comprimido:
`c46a2c7efa557638948b1fe5eaba2205c3361c743058cf32f878d9f4cd8cf204`.
La base `sismapiscis_test` conserva cuatro biometrias antiguas; no es otra campaña.

Se volvió a ejecutar el protocolo v0.3: 16 candidatos, selección con estudios
externos separados y reajuste final con todos los ejemplos elegibles. Quedó
ExtraTrees, historial activado y tasa directa. 376 ventanas correlacionadas derivan
de 169 pesos externos publicados y 7 medias locales; no son 376 nuevas biometrias.
El nuevo artefacto es idéntico al anterior salvo su instante de disponibilidad.
Se conservó la identidad del artefacto operativo y sus emisiones anteriores.
MAE retrospectivo de desarrollo en cuatro fechas: 12,7617 g; tendencia: 17,1026 g.
Este reajuste no añade evidencia independiente de precisión.

## Diez modelos de sensores entrenados

Variables: temperatura, oxígeno, pH, nitrato en unidades nativas y luz. Por cada
variable se entrenaron modelos para la próxima hora y para la media de las próximas
24 horas. Se probaron siete recetas ML: Ridge con alfa 1/10/100 y RF/ExtraTrees
con profundidad 3/6, 120 árboles y hoja mínima 8. Se eligió por MAE de validación;
se congelaron predicciones del bloque de prueba antes de reajustar el seleccionado
con todas las ventanas observadas. Los artefactos finales son JSON portables.

| Variable | Horizonte | ML elegido | MAE ML | MAE referencia |
|---|---:|---|---:|---:|
| Temperatura, °C | 1 h | Ridge 10 | 0,1958 | 0,1737 |
| Temperatura, °C | 24 h | RF profundidad 6 | 0,8660 | 0,5435 |
| Oxígeno, mg/L | 1 h | Ridge 10 | 0,2417 | 0,3126 |
| Oxígeno, mg/L | 24 h | Ridge 100 | 0,6692 | 0,7904 |
| pH | 1 h | Ridge 1 | 0,0372 | 0,0300 |
| pH | 24 h | Ridge 10 | 0,1701 | 0,1432 |
| Nitrato, unidades sin verificar | 1 h | ExtraTrees profundidad 3 | 2396,62 | 2687,33 |
| Nitrato, unidades sin verificar | 24 h | ExtraTrees profundidad 3 | 1258,02 | 1211,72 |
| Luz, lux declarados | 1 h | ExtraTrees profundidad 6 | 43,12 | 33,85 |
| Luz, lux declarados | 24 h | Ridge 10 | 44,35 | 23,64 |

Menor MAE es mejor. La referencia de 1 h es el último valor observado; la de 24 h,
la media de las 24 horas previas con al menos 18 horas observadas. La meta de 24 h
exige las 24 medias horarias futuras observadas. No se rellenan huecos del objetivo.
El entrenamiento imputa únicamente características, con estadísticas de su bloque.
No hay mezcla aleatoria de filas ni objetivos futuros en el entrenamiento anterior.

Partición cronológica 60/20/20 de orígenes elegibles, purgando los objetivos que
alcanzan el bloque siguiente. Para luz a 24 h, esa partición dejaba cero ventanas
de validación: se aplicó una alternativa 40/30/30 elegida por fechas y cantidades,
no por errores. Quedaron 37 ventanas de entrenamiento, 20 de validación y 36 de
prueba. Las ventanas de un mismo día y horizonte se solapan; no son ensayos
independientes. La campaña y parte de estas fechas ya se habían examinado.

El primer intento está conservado: terminó antes de entrenar luz/24h por ese
problema de cobertura. También se corrigió el límite arbitrario de nitrato 10000
al límite de almacenamiento DECIMAL(8,2), 999999,99. Sus unidades siguen sin
verificar; sus errores numéricos no deben presentarse como mg/L. La regla previa
de OD 7,22 repetido ocho horas excluye 2.829 horas, de forma causal; el motivo es
una señal previamente auditada, no una calibración física demostrada.

Los resultados indican entrenamiento completado, no superioridad universal del ML.
Luz, temperatura y pH perdieron frente a la referencia en estos bloques. Se conserva
el ML entrenado como candidato y se informa el resultado desfavorable.

## Integrador ML de sensores y crecimiento

`train_stack.py` entrena un modelo Ridge que aprende una corrección a la tasa del
ExtraTrees de crecimiento. Sus entradas incluyen las predicciones diarias de
temperatura, oxígeno y pH de tres Ridge anteriores. Es stacking entrenado con
etiquetas de peso observadas, no una corrección prescrita manualmente.

Para reconstruir cada origen histórico, los Ridge de sensores se ajustan solo con
objetivos cuya hora final almacenada no supera el origen. La receta alfa 10 se
mantiene fija; no se elige a partir de resultados locales posteriores. El modelo
base de crecimiento también se reajusta usando solo biometrias anteriores. El
meta-modelo alfa 100 se compara desde que existen dos objetivos anteriores y,
al terminar, se reajusta con los cuatro orígenes elegibles completos.

Estos tres upstream Ridge son parte del propio integrador. No se sustituyen por
los modelos de la tabla si la receta difiere: hacerlo cambiaría la distribución
con la que se entrenó el meta-modelo.

Solo hubo cuatro orígenes utilizables: 24/06, 11/07, 07/08 y 13/09. El 26/09 tuvo
9 horas previas de agua y no cumplió el mínimo 18. Ninguno de los cuatro orígenes
tuvo historial de luz. Se excluyó luz de la entrada entrenada: una columna sin
observaciones no permite aprender su efecto. También se excluyó nitrato por
unidades no verificadas. Hay un lote, cuatro filas y siete características; el
resultado está fuertemente limitado por el tamaño y la falta de variación entre
campañas. La regularización no sustituye datos nuevos.

La comparación temporal usa los objetivos del 13/09 y 26/09/2026. Las filas de
pesos y predicciones quedan en la evidencia privada, fuera de Git.
MAE en esas mismas dos fechas: **28,0550 g del integrador frente a 6,7068 g del
ML base**. Son fechas históricas ya conocidas, no una validación ciega nueva.
El integrador **fue entrenado y quedó sin activar**, porque ese resultado y el
escaso soporte no justifican reemplazar el modelo que sirve el panel.

## Disponibilidad y servicio

Agua conserva fechas de medición del 04/10 con recepciones del 21/10; la última luz
registrada es del 06/10. Los relojes físicos y las zonas horarias de las columnas
no están alineados de forma verificada. Los modelos nuevos tienen proyecciones
offline desde la última hora almacenada, explícitamente distintas de pronósticos
emitidos en tiempo real. No se retrodatan como si hubieran existido en septiembre.
Las capturas operativas previas tampoco tienen biometrias posteriores para puntuar.

El piloto autenticado tiene dos rutas nuevas de inventario, bajo `/api/v1`:

- `GET /models/tilapia-sensor-forecast/status`: los diez modelos, huella, ventanas,
  recetas y resultados. Declara que no están integrados en el modelo operativo.
- `GET /models/tilapia-sensor-forecast/stack-status`: candidato integrador entrenado,
  sus cuatro orígenes, resultado en dos fechas y activación falsa.

Estas rutas no publican un pronóstico actual desde telemetría cuya fecha sea
incierta. El archivo horario conserva también el estado de ambos entrenamientos.
El router de Git incorpora las rutas; el backend público existente no se reinició.
No se activó ni reentrenó por sustitución el SVM OD antiguo de la aplicación.

Artefactos y fuentes persistentes en vmi2770917:
`/root/flask_sismapiscis/aquaculture_backend/backend/research_runs/20261022_full_training/`.
La instalación del piloto usa copias de los JSON en su directorio `serving`,
restaurables tras recreación del contenedor. Se respaldaron las tres fuentes
anteriores antes de cambiarlas y se verificaron sus hashes para no sobrescribir
trabajo ajeno. Las claves no se copiaron al paquete de entrega ni a Git.

## Reproducción

Con las dependencias de `requirements-training.txt` y `PYTHONPATH=.` desde la raíz:

```bash
python research/tilapia_growth_meta_20261021/execute.py --biometrics /privado/biometrics.json --out /privado/growth
python research/tilapia_full_training_20261022/train_sensors.py --snapshot /privado/snapshot.json.gz --out /privado/sensors
python research/tilapia_full_training_20261022/train_stack.py --snapshot /privado/snapshot.json.gz --growth-artifact /privado/growth/serving_model.json --out /privado/stack
python -m pytest
```

La suite completa terminó con 132 pruebas de software aprobadas. Las pruebas nuevas
verifican metas futuras sin incluir la hora actual, rechazo de huecos, ausencia de
influencia de futuras lecturas sobre características pasadas, purga entre bloques,
equivalencia sklearn/JSON y estados de candidatos incompletos o no activados.
El proceso contrasta además inferencia portable en muestras de cada ajuste final.
Estas comprobaciones no son certificación del crecimiento biológico.

Reversión: restaurar `pilot_service.py`, `install_pilot.py` y `capture_prospective.py`
desde `previous_serving_sources/` de esta ejecución, y reiniciar únicamente el piloto
adaptativo. Se pueden conservar los módulos y artefactos adicionales para auditoría.
No borrar pronósticos anteriores ni modificar sus hashes o sus fechas de emisión.
