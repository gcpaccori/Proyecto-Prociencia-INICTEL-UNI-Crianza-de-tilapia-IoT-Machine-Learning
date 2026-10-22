# Gaussiano de peso de tilapia — 22/10/2026

Un único proceso gaussiano recibe tiempo e historial medido de temperatura, OD y
pH y aprende el peso medio en gramos. Sus etiquetas son **siete biometrias reales**
de la campaña/especie 2, piscina 1, verificadas contra **220 pesos individuales**
en MySQL `sismapiscis` de vmi2770917. No aprende de una línea interpolada, de pesos
diarios inventados, del modelo anterior ni de predicciones de otros sensores.

## Datos y semántica

`export_mysql.py` hace una lectura coherente `REPEATABLE READ` mediante la conexión
del backend existente, sin trasladar credenciales. Se reexportaron las biometrias,
detalles y medias horarias de agua/luz desde siete días antes del primer peso.
Snapshot privado SHA256:
`99fd157cbf6bfccc3eb03e4c53c5bf6216db62de79a568759aebc8d4676dbdf4`.
Contiene 3.390 bins de agua y 311 de luz. Los bins se etiquetan con su fin de hora:
`floor(fecha_medicion/hora)+1h`. Esto corrige la etiqueta de inicio utilizada en
snapshots anteriores, pero **no verifica el reloj físico ni la disponibilidad**.

Hay una fila de entrenamiento por fecha de biometría. El objetivo es la media de
los pesos individuales; coincide con la media declarada. La varianza muestral de
cada media es `SD²/n`. Se ajustan los niveles de peso directamente: no se duplican
las etiquetas en todos los pares de diferencias y no se introduce su covarianza
compartida. Se supone selección aleatoria representativa e independencia entre
muestras; el diseño no ha sido verificado. Error de balanza/selección o dependencia
podrían invalidar esa aproximación.

La primera biometría (09/05) define el origen temporal, no la edad de nacimiento.
Cada punto usa medias de temperatura y pH y percentil 10 de OD en el historial
medido desde siete días antes de ese origen hasta el punto consultado. Se exige
70% de horas observadas por sensor en esa ventana acumulada. No se interpola agua.
Las escalas físicas de entrada quedan fijadas antes de evaluar: tiempo/30 días,
temperatura/5 °C, OD/2 mg/L y pH/1. Son decisiones experimentales, no óptimos
universales. Se conserva la regla previa que retira los finales de una meseta de
OD 7,22 durante ocho horas consecutivas; no se elige contra estos resultados.

Luz queda sin entrenar por cobertura temporal emparejada insuficiente. Se
conservaron sus mediciones. La base también tiene totales de alimento por biometría
y tablas de alimentación calculadas: no se tratan como entregas diarias medidas
ni se usan como información futura de entrada.

## Entrenamiento y verificación numérica

Se utiliza `GaussianProcessRegressor` de scikit-learn 1.8.0. Un solo kernel conjunto
combina covarianza lineal sobre tiempo, Matérn 3/2 sobre todas las entradas y ruido
blanco. No se fija una ecuación de crecimiento: se aprenden tres amplitudes por
máxima verosimilitud marginal, únicamente con el entrenamiento de cada partición.
La longitud Matérn se fija en 1; no hay búsqueda de arquitecturas contra el test.
La media/desviación del objetivo se ajusta en el prefijo. El ruido de muestreo se
normaliza con esa desviación, antes de pasarlo a `alpha`. Se conserva cualquier
aviso de optimización o de límites del kernel en el artefacto.

Un segundo GP sin sensores, con la misma receta, es una **comparación separada**;
no alimenta al GP con sensores. Se exportan X de entrenamiento, coeficientes,
Cholesky, escala y kernel a JSON. La inferencia portable calcula media y desviación
sin sklearn ni pickle; se contrasta contra sklearn en cada ajuste y en entradas
fuera de las filas ajustadas mediante pruebas numéricas.

## Resultado de desarrollo

Se hacen cuatro estimaciones progresivas: los primeros tres pesos entrenan y el
siguiente se compara sin incorporarlo al ajuste; después se amplía el prefijo.
Fechas: 07/08, 13/09, 26/09, 16/10/2026. **Son nowcasts**: las lecturas de agua hasta
el objetivo ya han ocurrido. No se presentan como pronósticos emitidos desde el
pesaje anterior. El reloj almacenado se usa como orden retrospectivo, sin afirmar
que las lecturas o las correcciones biométricas ya estuvieran disponibles entonces.
Las siete etiquetas ya habían sido examinadas: no hay nueva validación ciega.

| Modelo, mismas cuatro fechas y tarea | MAE (g) |
|---|---:|
| GP con sensores | 11,0074 |
| GP solo tiempo | 11,1208 |
| Tendencia de los dos últimos pesos | 17,1026 |
| Último peso sin cambio | 17,3706 |

La mejora atribuible a añadir sensores es **0,1133 g**, pequeña y no concluyente.
El mayor error vuelve a ser agosto: 113,59 g estimados frente a 84,505 g medidos.
No se compara esta tarea con el MAE del pronosticador anterior, que no usaba las
lecturas del intervalo futuro respecto a su emisión.

Tres de cuatro medias observadas caen dentro de la banda GP condicional nominal
del 95%; cuatro fechas de un lote no calibran una cobertura del 95%. Las bandas
son condicionales al kernel, hiperparámetros ajustados y datos observados, e
incluyen el término blanco del GP, pero no el error muestral de un nuevo pesaje.
No representan la distribución de pesos de peces individuales ni propagan toda
la incertidumbre por datos faltantes, relojes o parámetros estimados.

## Curva entre biometrías

Después de fijar la evaluación, ambos GP se reajustan con los siete pesos. Se
generan 3.259 puntos horarios y diarios, CSV y JSON, entre 09/05 y 16/10. **Son
salidas estimadas, ninguna se vuelve a usar como etiqueta.** La curva usa pesajes
posteriores a cada punto: es reconstrucción, no una emisión histórica previa.
Cada fila informa cobertura y hueco reciente. Agua termina el 05/10 y luz el
06/10 del reloj almacenado: el tramo final tiene un hueco ambiental importante.
La curva del 16/10 aprovecha el peso real de esa fecha y no demuestra que el modelo
hubiera anticipado ese peso.

No se obliga a una curva monótona ni se recortan bandas para aparentar plausibilidad.
La banda puede incluir valores físicamente imposibles bajo una aproximación
gaussiana; los valores fuera de los rangos de entrenamiento quedan señalados.

## Servicio privado

El piloto autenticado incorpora bajo `/api/v1`:

- `GET /models/tilapia-growth-gaussian/status`: versión, soporte y métricas.
- `GET /models/tilapia-growth-gaussian/curve`: puntos diarios reconstruidos y flags.
- `POST /models/tilapia-growth-gaussian/predict`: historial horario medido a peso.

El POST admite solo `current` o `retrospective_fit_diagnostic`. El diagnóstico
informa que puede reutilizar etiquetas y no valida pesos nuevos. `current` queda
bloqueado hasta verificar físicamente relojes mediante configuración confiable
del servidor; también exige datos recibidos a tiempo y huecos <=48 horas.
No se habilitó. Las peticiones no aceptan pronósticos de otros sensores ni pesajes
interpolados. El servicio actual y el panel anterior no se sustituyen.

Fuentes del GP, API, artefacto y curva se conservan en el run privado
`/root/flask_sismapiscis/aquaculture_backend/backend/research_runs/20261022_gaussian_growth/`.
El restaurador del piloto agrega solo esos módulos y artefactos. Se respaldan y
verifican por hash las fuentes de servicio antes del cambio; reinicia solo el
piloto, no el contenedor público. El registro horario incorpora el estado GP.
Para revertir, restaurar las fuentes de servicio respaldadas y reiniciar el piloto.

## Reproducción

Los datos privados y artefactos no se incorporan a Git. Desde la raíz del repo,
con las dependencias de `requirements-training.txt`:

```bash
PYTHONPATH=. python research/tilapia_gaussian_20261022/train_gaussian.py --snapshot /privado/snapshot.json.gz --out /privado/evidence
python research/tilapia_gaussian_20261022/plot_results.py --evidence /privado/evidence --output /privado/resultados.png
python -m pytest -q
```

Los tests usan fixtures numéricos para equivalencia media/desviación, ruido de
muestreo, rechazo de horas duplicadas/futuras, cobertura y semántica de diagnóstico.
Que los sensores modifiquen numéricamente una salida no prueba un efecto biológico.
Referencia primaria: [documentación GP](https://scikit-learn.org/stable/modules/gaussian_process.html).
