# Crecimiento adaptativo ML v0.3.0

El RF anterior no aprovechaba la trayectoria de las biometrias. Este cambio
añade un candidato Extra Trees que aprende la tasa futura a partir del peso,
duración, tasa reciente, tasa anterior y cambio de tasa. Es ML supervisado con
pesos observados. La diferencia respecto de la tendencia reciente se devuelve
como corrección aprendida; no se ajustó una fórmula de crecimiento a mano.

## Resultado de desarrollo ejecutado

| Cuatro fechas locales, mismos objetivos | MAE |
|---|---:|
| Extra Trees nuevo | 12,7617 g |
| RF anterior | 14,3689 g |
| Tendencia reciente | 17,1026 g |

La mejora es 11,2% frente al RF anterior y 25,4% frente a tendencia. El error de
agosto sigue siendo 28,95 g. Todas las biometrias ya eran conocidas; esto es una
repetición retrospectiva de desarrollo, no una nueva evaluación ciega.
No se usó el resultado local para elegir entre los 16 candidatos.

## Datos y elección del candidato

- Arabia Saudita: 147 pesos publicados en 21 filas de réplica, siete tratamientos,
  W0–W6. Solo ensayo preliminar de Alrashada et al. (2023), DOI
  [10.1371/journal.pone.0293727](https://doi.org/10.1371/journal.pone.0293727).
  Suplemento S1, exp1.pdf, primera página. Fuente con licencia de atribución.
- Piura: 22 medias semanales observadas, DOI
  [10.21503/CienciayDesarrollo.2012.v15i2.05](https://doi.org/10.21503/CienciayDesarrollo.2012.v15i2.05).
  Persiste un conflicto documental en el tamaño de muestra. No se utilizaron
  las edades ni los parámetros ajustados de la tabla secundaria.
- Local: siete medias de una campaña, entregadas mediante un archivo privado.
  Se habían verificado contra sus detalles en el trabajo anterior. No se guardan
  esas biometrias privadas en Git.

Se construyeron 368 ejemplos externos cuyos extremos son pesos realmente
observados, con horizontes de 7, 14, 21 o 28 días. Son ejemplos correlacionados,
no 368 nuevas biometrias ni experimentos independientes. Los 169 pesos externos
siguen siendo 169. La versión de servicio añade ocho ejemplos locales de
intervalos observados de hasta 60 días, derivados de siete medias locales.

Se compararon Ridge, RF, Extra Trees y boosting, con o sin historia adicional,
prediciendo tasa directa o residual: 16 especificaciones fijas. Cada pliegue
excluye un estudio completo. La selección minimiza el promedio por estudio del
MAE relativo al de tendencia, con igual peso por estudio durante entrenamiento.
Las réplicas saudíes permanecen juntas. Ningún identificador de estudio o
tratamiento es una variable para memorizar el resultado.

El mejor candidato fue Extra Trees: 120 árboles, profundidad 3, mínimo cinco
ejemplos por hoja, semilla 20261021, objetivo de tasa directa. En la comparación
de desarrollo por estudios obtuvo MAE 6,4074 vs 8,1739 g de tendencia en Piura
y 4,7621 vs 6,7626 g en Arabia Saudita, agregando los cuatro horizontes.
La puntuación macro relativa fue 0,7440. Estos pliegues también eligieron el
modelo: son evidencia de selección, no una estimación final independiente.

**Límites que se conservan:** a siete días, Arabia Saudita favorece tendencia
(1,7489 vs 2,7605 g del ML, todos los tratamientos). Una comprobación temporal
dentro de Piura también favorece tendencia (7,2787 vs 8,8827 g). Las métricas
por horizonte y esa comprobación se guardan completas. El candidato no gana
siempre y no se publica una certeza cercana a uno.

Kamble queda fuera del nuevo entrenamiento por el conflicto de duración/SGR.
La serie de Brasil no se usa para seleccionar ni entrenar el nuevo candidato.
El modelo y protocolo originales v0.2 se conservan; no se sobrescriben.

## Sensores y luz

La API admite predicciones de temperatura, oxígeno, pH y luz con versión,
fecha de emisión, fin de entrenamiento y validez. Rechaza fechas futuras,
pronósticos vencidos, unidades fuera de rango y mezclas de cohortes.

Una variable de sensor solo entra al entrenamiento cuando hay al menos diez
orígenes de pronóstico distintos, emparejados con crecimiento observado y con
variación dentro de al menos dos estudios. Repetir un pronóstico en varios
horizontes no aumenta ese contador. Las constantes ambientales declaradas en
un artículo no se hacen pasar por predicciones archivadas de sensores.

El conjunto actual no cumple ese criterio: `sensor_keys=[]`. El API devuelve
qué modelos de sensor recibió y por qué no fueron utilizados. **El nuevo
candidato aprende de la historia biométrica; todavía no demuestra un aporte
predictivo aprendido de los sensores ni de la luz.**

La lectura automática de la piscina incluye un inventario de luz. Mantiene
`sensor_clock_alignment_verified=false`: agua y ambiente usan fechas de origen
distinto, y el contador de oscuridad de la luz requiere verificación física.
No se desplazaron relojes ni se modificaron umbrales o datos sin evidencia.

## API e instalación experimental

- GET `/api/v1/models/tilapia-growth-adaptive/status`
- POST `/api/v1/models/tilapia-growth-adaptive/predict`
- GET `/api/v1/ponds/1/models/tilapia-growth-adaptive/forecast?projection_days=14`

El POST necesita al menos dos biometrias observadas y ordenadas de la misma
cohorte; con tres obtiene la tasa anterior. Preserva la fecha del último peso.
La proyección cuenta el tiempo desde esa observación hasta el objetivo, aunque
el peso tenga varios días de antigüedad. Nunca etiqueta un peso antiguo como
medido hoy. El muestreo local solo registra día: la ruta automática declara su
suposición de hora inicial del día en America/Lima.

El GET consulta las últimas tres biometrias de la última campaña/especie de esa
piscina. No mezcla etapas de campañas distintas. Usa consultas de lectura y
conserva los identificadores de fuente y el instante de disponibilidad.
El modelo devuelve las variables fuera de su dominio, la referencia de tendencia,
la corrección aprendida y `production_ready=false`. No se inventan intervalos de
predicción calibrados.

El piloto usa **0.0.0.0:8013 dentro de aquaculture_backend**, exclusivamente en la
red Docker compartida con Laravel, sin publicar ese puerto en el host. Exige una
clave bearer en todas las rutas (incluida documentación). Laravel la lee de un
archivo privado, nunca del navegador ni de variables Vite. El servicio
`tilapia-growth-adaptive-pilot.service` en vmi2770917. `install_pilot.py` restaura
archivos tras recreación del contenedor y rechaza sobrescribir código distinto.
`stop_pilot.py` detiene solo el ejecutable exacto de este piloto. No se cambia
el enrutador de la aplicación pública que ya corre en el servidor.

El registro de Git incorpora el router nuevo para su integración normal en el
backend. La instalación experimental y la aplicación pública son despliegues
distintos; un HTTP 200 del piloto no valida crecimiento biológico.

La vista Laravel se describe en `integration/README.md`. Para retirar la
integración, primero deshabilitar el timer, restaurar las fuentes y el manifiesto
Vite respaldados y retirar las dos rutas y archivos nuevos; después detener solo
el piloto adaptativo. No eliminar los pronósticos ya emitidos ni sus artefactos.

### Verificación real de esta entrega

El servicio quedó activo y habilitado el 21/10/2026. Estado, pronóstico de piscina
y POST respondieron HTTP 200. Pronóstico de sensor futuro y cohorte mezclada
respondieron HTTP 422. El piloto anterior siguió respondiendo HTTP 200 y el
contenedor de la aplicación pública conservó su instante de arranque.
La suite completa, incluida la autenticación nueva, terminó con **124 pruebas de software aprobadas**; esos checks
no son validación biológica.

Se guardaron pronósticos prospectivos a 7, 14 y 28 días antes de conocer los pesos
futuros, con SHA256 del artefacto servido. Son predicciones aún sin puntuar.
Los horizontes evaluados en estudios externos se miden desde el último peso
observado, no desde una emisión que ocurre varios días después de ese peso.
Por eso una proyección a 28 días desde hoy puede superar el horizonte externo
de 28 días desde la biometría; se conserva la edad del ancla en cada respuesta.

## Reproducción

Desde la raíz del repositorio:

```bash
PYTHONPATH=. python research/tilapia_growth_meta_20261021/execute.py \
  --biometrics /ruta/privada/biometrias.json --out /ruta/privada/evidencia
python -m pytest
```

Cada entrada privada contiene `id`, `date` ISO y `weight_g`. Las fechas deben
estar ordenadas. Para las figuras:

```bash
python research/tilapia_growth_meta_20261021/plot_results.py \
  --evidence /ruta/privada/evidencia \
  --old-results /ruta/privada/local_evaluation.csv --out /ruta/privada/figuras
```

El servicio carga JSON portable, no pickle. La exportación se contrasta con
sklearn y las pruebas verifican fechas, cohorte, anclas, soporte de sensores y
respuestas HTTP. Los archivos de evidencia y los datos locales quedan fuera de
Git. La validación futura debe usar resultados posteriores a pronósticos fechados.
El modo de repetición histórica exige un artefacto disponible antes de la emisión;
no permite presentar un reajuste posterior como una predicción pasada.

Método de evaluación: documentación primaria de
[scikit-learn: validación cruzada](https://scikit-learn.org/stable/modules/cross_validation.html)
y [prevención de filtraciones](https://scikit-learn.org/stable/common_pitfalls.html).
