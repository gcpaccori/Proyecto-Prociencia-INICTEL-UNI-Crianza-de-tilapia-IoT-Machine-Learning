# Tilapia: corpus trazable y piloto de crecimiento por intervalos

Fecha de corte: 21 de octubre de 2026. Modelo: `TILAPIA_INTERVAL_GROWTH_PILOT`, versión `0.1.0-research`.

Este trabajo incorpora observaciones externas y prueba una forma de supervisión correcta. No certifica precisión local ni activa un modelo productivo. No se leyeron ni usaron pesos de biometrías locales nuevas/corregidas. Los ensayos anteriores del proyecto son antecedentes; no forman parte del entrenamiento de este piloto.

## Datos efectivamente normalizados

| Fuente | Datos incluidos | Unidad experimental y alcance |
| --- | --- | --- |
| Kamble et al. (2024), Zenodo 11174309 | 525 registros individuales iniciales y 525 finales de peso/talla; 1.701 celdas de resúmenes ambientales; 21 intervalos de medias de tanque | 7 tratamientos x 3 tanques; un experimento de 60 días. Los 525 renglones iniciales y finales no se interpretan como peces identificados por etiqueta. |
| García, Tume y Juárez (2012), Piura | 22 medias semanales de peso y talla; fechas originales verificadas visualmente en tabla 1, página PDF 4 | Una cohorte; los tamaños de muestra discrepan entre resumen español y método/tabla. No hay sensor horario asociado. |
| Opiyo et al. (2024), Kenia | 4 resúmenes por dieta, tabla 2, página PDF 4 | En cuarentena: duración de 84 días y tasas publicadas no coinciden con los pesos. No se usan para entrenar. |

No se suman los peces muestreados por fecha como si fueran individuos únicos. No se crean etiquetas diarias de peso mediante interpolación. No se asigna a Piura una temperatura u oxígeno inventados para completar columnas faltantes. Los nueve promedios semanales del primer experimento tampoco se convierten en 60 observaciones ambientales medidas.

Control adicional de Kamble: las tasas SGR medias de su tabla 7 no se reconcilian con las distribuciones marginales de pesos iniciales/finales a los 60 días declarados. Por ejemplo, el control publica 1,31 %/día; `kamble_2024_rate_consistency_QC.csv` conserva la comparación aritmética. No se descartan ni se corrigen los pesos originales. El benchmark que sigue usa provisionalmente los extremos observados y los 60 días declarados para probar el pipeline; no convierte ese experimento en un donante aprobado para calibración definitiva. Esta discrepancia requiere aclaración de los autores o evidencia original adicional.

## Resultado del piloto externo

Se compararon dos regresiones regularizadas, con `alpha=10` fijado antes de evaluar. El objetivo es `log(W_final/W_inicial)/días`, un resumen empírico de crecimiento por intervalo. Esta regresión es un benchmark de ingeniería; no se atribuye a un artículo como ley fisiológica.

Se retuvo un tratamiento completo por vez: siete particiones, tres tanques de prueba en cada una. Escalado y ajuste se recalculan dentro de cada partición.

| Variante | MAE (g) | RMSE (g) | MAPE (%) |
| --- | ---: | ---: | ---: |
| Peso inicial | 6,310 | 8,085 | 9,961 |
| Peso inicial + temperatura + OD | 6,492 | 8,185 | 10,212 |

Añadir ambiente no mejoró este benchmark. Hay seis intervalos fuera de al menos un rango de entrenamiento de su partición; el archivo de resultados los identifica. Las medias ambientales por tanque varían poco y el tratamiento alimentario está confundido con otras diferencias entre tanques. No corresponde interpretar los coeficientes como efectos causales. No hay prueba entre estudios ni granjas independientes: sigue siendo un solo estudio con 21 tanques. No se obtuvo un modelo local certero ni una justificación para desplegar este piloto como predictor del proyecto.

## Integración de los modelos de sensores

Los modelos de sensores aportan **predicciones y su procedencia**, no sus archivos de pesos como variables tabulares. Para cada predicción ambiental se necesita fecha de emisión, ventana objetivo, modelo/versión, corte de entrenamiento y, cuando exista, distribución predictiva calibrada. Los residuos de predicción obtenidos cronológicamente sirven para propagar incertidumbre ambiental; no sustituyen la incertidumbre biológica.

`EnvironmentalSegment` e `interval_exposure` integran segmentos de temperatura y OD con duración explícita. Calculan cobertura, mayor hueco, fracción pronosticada, medias ponderadas, grados-día y déficit de oxígeno. Los umbrales son parámetros de exposición declarados; no se presentan como umbrales fisiológicos universales. Se rechazan solapamientos, NaN, fechas sin zona horaria, observaciones futuras, segmentos no disponibles al emitir el pronóstico y modelos entrenados después de generar su predicción.

Dos días con OD medio de 4 mg/L pueden tener exposiciones diferentes: 12 horas a 1 y 12 horas a 7 producen 24 mg*h/L de déficit respecto de 3, mientras 24 horas a 4 producen cero. El promedio diario pierde esa información. Si se dispone solo de resúmenes semanales, no puede calcularse una duración real de hipoxia.

La predicción del piloto recibe `GrowthCovariates`, que no contiene peso final. Por defecto devuelve `weight_g=null` si el peso inicial, duración, temperatura u OD quedan fuera de sus rangos de entrenamiento. Toda salida conserva `production_ready=false` y `confidence=null`. El piloto no se añadió al catálogo activo, API productiva ni actuadores.

## Arquitectura objetivo del modelo de crecimiento

Una extensión defendible es un modelo jerárquico de estado con crecimiento condicionado por tamaño, exposición ambiental, alimento real, densidad, genética y manejo. La evolución de peso es latente entre biometrías; cada muestreo observa la distribución de pesos con su error. Los parámetros poblacionales se aprenden en estudios externos y la variación entre estudio, tanque y campaña se estima de forma explícita. Un término residual ML se incorpora solamente si mejora las pruebas entre estudios y campañas.

Los valores de pH, nitrato, TAN y nitrito deben conservar sus especies químicas y unidades. Nitrato expresado como NO3-N no equivale numéricamente a NO3: factor de conversión aproximado 62/14, aplicable solo después de verificar la definición del laboratorio/sensor. Nitrato medido no permite reconstruir TAN o amoníaco no ionizado sin datos adicionales. Los umbrales operativos de calidad de agua no son por sí solos leyes de crecimiento.

La biomasa debe calcularse desde peso y población viva por separado. Una biometría transversal puede cambiar de media por mortalidad selectiva, selección de muestra o clasificación de tallas; no siempre representa crecimiento de los mismos peces.

## Validación necesaria antes de activar

1. Completar el corpus con ensayos que tengan pesos, tiempos, alimentación y ambiente coincidentes, manteniendo identificadores de estudio, tanque y campaña. Resolver cuarentenas y duplicados.
2. Separar estudios/campañas completos antes de limpiar, imputar, seleccionar variables o ajustar hiperparámetros. Los intervalos adyacentes de la misma cohorte pueden compartir pesos extremos y no deben repartirse aleatoriamente entre entrenamiento y prueba.
3. Comparar persistencia de peso, tendencia reciente, modelo de tamaño/tiempo, TGC y alternativas mecanísticas con y sin ambiente. La selección se hace en entrenamiento/validación, no con la última biometría reservada.
4. Fijar horizontes reales de 1, 7, 14 y 30 días y una hora de emisión única por pronóstico. Separar reconstrucción retrospectiva, pronóstico que se actualiza cada hora y pronóstico fijo a varios días.
5. Congelar modelo, datos y predicciones antes de revelar los pesos nuevos. Reportar todas las fechas reservadas, errores en g y %, sesgo, cobertura de intervalos y casos fuera del dominio. Una prueba en la misma campaña es útil, pero no demuestra transferencia a otras granjas.
6. Acordar tolerancias de negocio antes de mirar las etiquetas finales. No traducir R² ambiental a “certeza” de crecimiento. No reclamar una precisión global a partir de un solo punto temporal.

## Reproducir

Desde la raíz del repositorio, con sus dependencias de ML instaladas:

```bash
python -m unittest backend.app.tests.test_tilapia_interval_growth -v
python -m research.tilapia_growth_20261021.benchmark
python -m research.tilapia_growth_20261021.plot_observations
```

Para regenerar los CSV a partir del DOCX fuente:

```bash
python research/tilapia_growth_20261021/extract_external.py --kamble-docx /ruta/al/documento_original.docx
```

La extracción requiere `python-docx`; los gráficos, `matplotlib`. Los CSV ya extraídos permiten ejecutar el benchmark sin descargar de nuevo los originales. Se conserva una suma SHA256 del DOCX usado y de cada CSV. Los campos `source_table` y `source_row` permiten contrastar los renglones.

## Fuentes, licencias y pendientes de acceso

| Fuente primaria | Utilidad | Estado al cierre |
| --- | --- | --- |
| [Kamble et al., datos](https://doi.org/10.5281/zenodo.11174309), [artículo](https://f1000research.com/articles/13-540/v1) | Peso/talla iniciales y finales, ambiente por réplica | DOCX descargado, tablas extraídas; CC BY 4.0 según metadatos Zenodo. Discrepancia SGR/extremos detectada; benchmark provisional. Los datos se anclan al DOI de Zenodo. |
| [García et al.](https://doi.org/10.21503/CienciayDesarrollo.2012.v15i2.05) | Serie semanal observada | PDF aportado por el usuario; se transcriben observaciones numéricas con atribución, sin republicar el PDF. |
| [Opiyo et al.](https://doi.org/10.5281/zenodo.14555064) | Cuatro dietas, crecimiento y FCR | PDF descargado, tabla revisada visualmente; CC BY 4.0 según metadatos. Datos en cuarentena. |
| [Stoneham et al., Dryad](https://doi.org/10.5061/dryad.1h9g7) | 350 peces, 14 tanques; archivos de peso temporal, alimentación y agua | Metadatos y nombres de archivos verificados. Descarga pública devolvió 403; API de descarga, 401. No contado como datos obtenidos ni analizados. |
| [Amira et al., Mendeley](https://doi.org/10.17632/cdfdd6tpk6.1) | Alevines, dietas de microalgas, crecimiento y agua | Ficha primaria verificada; CC BY 4.0. Archivo sin descargar; tamaño útil pendiente. |
| [Montería, versión 3](https://doi.org/10.17632/8s73jfvgr5.3), [depósito relacionado](https://doi.org/10.17632/3g2b4sh65m.1) | Peso medio y telemetría ambiental | Fichas verificadas; no archivos. Mismos autores, lugar y periodo: no contar como dos estudios antes de comparar bytes y observaciones. Verificar cómo se midió el peso y si se repite/interpola entre filas. |
| [Thermal Acclimation](https://doi.org/10.17632/h5s5nwv6ng.1) | Temperatura cíclica/constante, crecimiento, ingesta y FCR | Ficha primaria de 2026 verificada; CC BY 4.0. Archivos pendientes de acceso, sin conteo inventado. |
| [Mengistu et al., corpus](https://doi.org/10.7910/DVN/LSPNAO), [ficha WorldFish](https://worldfishcenter.org/data/replication-data-systematic-literature-review-major-factors-causing-yield-gap-affecting-growth) | Revisión de 32 artículos incluidos; TGC, FCR, supervivencia y manejo | Fuente prioritaria para ampliar diversidad de condiciones. Harvard respondió 403 desde este entorno; no se descargó ni se incorporó. Los 1.973 artículos encontrados inicialmente no son 1.973 ensayos incluidos. |
| [WorldFish GIFT G19](https://doi.org/10.7910/DVN/1ZEQJJ) | Producción de 63 familias; no equivale a 63 series de crecimiento | Ficha indica archivo restringido y CC BY-NC 4.0. No descargado. No se solicitó acceso ni se contactó a autores. |
| [Fulton y Lyu (2026)](https://doi.org/10.1371/journal.pone.0336890) | Método de ensamble biológico/ML con 9.798 eventos de trucha | Artículo metodológico; no son biometrías de tilapia. No se transfieren parámetros ni exactitud entre especies. |

No se encontró evidencia de una base pública de miles de millones de biometrias de tilapia aptas para este objetivo. Este inventario es una búsqueda dirigida y verificable, no una prueba de inexistencia mundial. Lecturas IoT, bases genómicas, fotogramas y toneladas producidas no se contabilizan como mediciones longitudinales de peso.

## Atribución del conjunto principal

Kamble, Manoj Tukaram; Salin, Krishna R.; Chavan, Balasaheb Ramdas; Medhe, Seema Vijay; Thompson, Kim D.; Pirarat, Nopadon (2024). *Length-weight relationship and condition factor of Nile tilapia (Oreochromis niloticus) fed diets supplemented with guava and star gooseberry leaf extract*. Zenodo. DOI: 10.5281/zenodo.11174309. CC BY 4.0. Modificaciones: extracción de tablas a CSV, incorporación de procedencia y agregación a medias por tanque. No se atribuyen estas transformaciones a los autores originales.
