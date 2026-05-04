**INFORME DE ACTIVIDADES N°017-2026-REAJ**

1.  **Presentación de informe**

**Entidad Ejecutora :** UNIDAD EJECUTORA 002 - INICTEL-UNI

**Contrato :** N° PE501091609-2024-PROCIENCIA

**Proyecto de Investigación :** "Validación de una estación de monitoreo
de calidad de agua y dosificación de Floc bacteriano para crianza masiva
de peces en piscigranjas artificiales con geomembrana utilizando
aprendizaje automático e Internet de las Cosas"

**Responsable Técnico :** Ing. Rubén Acosta Jacinto

**Resolución Directoral :** N° 000047-2025-INICTEL-UNI/DE

**Periodo de Informe :** marzo 2026

| **DESCRIPCIÓN DE LAS ACTIVIDADES REALIZADAS**      | **TOTAL**  |
|----------------------------------------------------|------------|
| \- Revisión de mecanismos del crecimiento de peces | S/. 700.00 |

-----------------------------------------------

Rubén Eusebio Acosta Jacinto

Investigador Principal

N°PE501091609-2024-PROCIENCIA

2.  **Avances**

**Revisión de mecanismos del crecimiento de peces**

Los investigadores (Chen et al., 2020) en acuicultura, la predicción
precisa del consumo de alimento en grupos de peces se considera crucial
para cualquier sistema de alimentación. Estudios previos utilizaron
principalmente estadística matemática para establecer la relación entre
el consumo de alimento y los factores que lo influyen. El resultado se
veía fácilmente afectado por la experiencia subjetiva. Para solucionar
estos problemas, este artículo propone un modelo de predicción del
consumo de alimento para grupos de peces mediante una red neuronal de
retropropagación (BPNN) y un algoritmo evolutivo mental (MEA). En primer
lugar, se seleccionaron cuatro factores, como la temperatura del agua,
el oxígeno disuelto, el peso promedio de los peces y el número de peces,
como entrada para el modelo BPNN. En segundo lugar, el peso inicial y el
umbral de la BPNN se optimizaron mediante el MEA para mejorar la
precisión de la coincidencia. Todas [las truchas
arcoíris](https://www.sciencedirect.com/topics/agricultural-and-biological-sciences/oncorhynchus-mykiss) ( Oncorhynchus
mykiss ) fueron proporcionadas:

- La trucha arcoíris prefiere vivir en aguas cristalinas, bajas
  temperaturas, alto contenido de oxígeno disuelto y abundante caudal.

- La temperatura y el oxígeno disuelto son los principales factores
  ambientales que afectan su alimentación.

- Cuando la temperatura es inferior a 7 °C o superior a 20 °C, su
  apetito disminuye y su crecimiento es lento.

Por otro lado, cuando la concentración de oxígeno disuelto es inferior a
5 mg/L, la frecuencia respiratoria aumenta. Cuando es inferior a 4,3
mg/L, las enfermedades son propensas a brotes. El experimento se realizó
en el laboratorio RAS de la Estación Experimental Nacional Xiaotangshan
para Agricultura de Precisión. El sistema experimental comprendió 3
tanques (diámetro de 1,5 m y una profundidad de agua de 1 m). Había 30
peces en cada tanque, y el peso inicial fue de 200 ± 21 g, 400 ± 26 g y
600 ± 39 g, respectivamente. Antes del experimento, los peces se criaron
durante 3 semanas para adaptarse al entorno. Los peces fueron
alimentados dos veces al día (08:00, 17:00). Durante cada alimentación,
se utilizó la alimentación de punto fijo para entregar el alimento
granulado, y cada ronda se dividió en múltiples tiempos, cada intervalo
de alimentación: (60 ± 3) s, cada cantidad de alimentación: (20 ± 3) g.
Además, se adoptó el pellet que se hunde en este estudio. En este
trabajo, los parámetros ambientales se obtuvieron mediante un monitor
multiparamétrico de calidad del agua.

Los rangos efectivos fueron:

- Temperatura del agua: 0–60 °C,

<!-- -->

- Concentración de oxígeno disuelto: 0–20,00 mg/L.

- El peso de los peces se obtuvo mediante una báscula electrónica (TCS
  150, Yongkang Huaying Weighing Apparatus Co., Ltd.), con un rango de
  pesaje de 0–50 kg.

- Se registraron la temperatura del agua y el oxígeno disuelto en cada
  alimentación.

- Estos parámetros de calidad del agua se recopilaron en tiempo real y
  se exportaron mediante el módulo inalámbrico.

- El intervalo de muestreo de datos fue de 2 s.

Según la experiencia en piscicultura, el peso de los peces no cambiaba
significativamente en una semana. Por lo tanto, el peso promedio de los
peces se obtenía semanalmente mediante pesaje de muestras. Dado que el
apetito de los peces podía verse afectado por el pesaje, se alimentaban
al día siguiente. Debido a que los peces morían repentinamente por
enfermedades u otras causas, se debía registrar el número de peces en
cada alimentación. Los peces fueron alimentados en múltiples rondas de
saciedad. Las reacciones a la alimentación de los peces incluyen
principalmente las siguientes cuatro situaciones:

- Los peces nadan libremente para alimentarse continuamente hasta que el
  cebo es ingerido por completo.

- Los peces se alejan de la posición original y regresan a la suya
  después de terminar el alimento.

- Los peces solo comen el alimento que cae frente a ellos.

- Los peces no reaccionan a la caída del cebo.

- Cuando el comportamiento de alimentación se ajusta a la cuarta
  condición, detenga la alimentación.

De lo contrario, podrían quedar residuos en el fondo del tanque, lo que
no solo causaría un desperdicio de alimento, sino que también
contaminaría el medio ambiente. Finalmente, se registró la cantidad
total de alimento. Los valores de los atributos de los registros de
conexión de red tienen mediciones diferentes. Al calcular la brecha
entre muestras, el atributo con un rango de valores amplio ocupa una
posición dominante, lo que debilita considerablemente la contribución de
los atributos con un rango de valores pequeño.

$X_{norm} = \frac{X_{t} - X_{\min}}{X_{\max} - X_{\min}}$…………………(1)

Donde:

Xt: Valor medido

Xnorm: Valor normalizado

Xmin: Valor mínimo del parámetro medido

Xmax: Valor máximo del parámetro medido.

BPNN (Back-Propagation Neural Networks) es uno de los modelos de redes
neuronales más utilizados. Es una red de propagación hacia adelante
multicapa, que se entrenó de acuerdo con el algoritmo de
retropropagación de errores. El modelo de predicción consta de tres
capas, que incluyen: una capa de entrada, una capa de salida y una o más
capas ocultas. Generalmente, la ingesta de alimento para peces se vería
afectada por muchos factores internos y externos. Los factores externos
son principalmente factores ambientales como: la temperatura del agua y
el oxígeno disuelto. Y el factor interno es principalmente la etapa de
crecimiento. Estos factores deben considerarse. Por lo tanto, los
factores anteriores se utilizaron como entrada. La estructura de la capa
oculta se determinó principalmente por el número de variables de
entrada. El nodo de entrada es *n* y el nodo de salida es *l* . El
número de nodos de la capa oculta se determina de acuerdo con la
ecuación [(2)](https://www.sciencedirect.com/science/article/pii/S2214317319300964#e0010) .

$$m = \sqrt{(n + l)} + \alpha\ldots\ldots\ldots\ldots.(2)$$

Donde: *m* , *n* y *l* son el número de nodos de las capas oculta, de
entrada y de salida, respectivamente.

- *m* es una constante entre 1 y 10. (número de nodos de capa oculta)

<!-- -->

- *n es un número de nodos de entrada.*

- *l es un número de nodos de salida. (Ingesta de alimento-Feed Intake)*

En esta investigación, se seleccionó el método experimental paso a paso
para determinar la estructura de la capa oculta. Primero, se estableció
un valor inicial y se incrementó gradualmente. Luego, comparando el
rendimiento de la predicción, se seleccionó el número de nodos
correspondientes con el mejor rendimiento. Por lo tanto, el número de
nodos ocultos se determinó finalmente en 10. La estructura de BPNN fue
"4-10-1" y su estructura de red se muestra en [fig.
1](https://www.sciencedirect.com/science/article/pii/S2214317319300964#f0005) .

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image1.png"
style="width:2.27341in;height:2.05676in" />

Figura 1. Estructura de red de la BPNN de tres capas

Los pesos y umbrales de la red neuronal BP optimizados por algoritmos GA
/MEA. En la BPNN, se seleccionaron como entrada cuatro factores:

- temperatura del agua,

- oxígeno disuelto,

- peso promedio y

- número.

- El consumo de alimento se consideró como salida, y

- se estableció un modelo de predicción de la BPNN.

- Antes de entrenar la BPNN, fue necesario normalizar la entrada y la
  salida.

Donde 

- *n* representa la inicialización de los nodos de la capa de entrada, 

- *m* y *l* son los nodos de la capa oculta y los nodos de la capa de
  salida, respectivamente. 

- *W <sub>ij</sub>* representa los pesos de conexión entre las neuronas
  de la capa de entrada y la de salida.

- *W <sub>jk</sub>* representa los pesos entre las neuronas de la capa
  oculta y la de salida, *y*

- *a* y *b* son los umbrales iniciales de las capas oculta y de salida.

- La tasa de aprendizaje *η* y

- la función de excitación neuronal *f* son fijas.

- Los pesos y los umbrales de la red neuronal se inicializan
  generalmente de forma aleatoria con números aleatorios en intervalos
  de \[−0,5; 0,5\].

El calculo de la salida de la capa oculta

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image2.png"
style="width:5.65693in;height:0.2344in" />

Donde *X* es la variable de entrada; *H <sub>j</sub>* es la salida de la
capa oculta.

El calculo de la salida de la capa de salida

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image3.png"
style="width:5.54745in;height:0.3448in" />

Donde *Y<sub>k</sub>* es la capa de salida.

Finalmente, se obtuvo el modelo de predicción tras el entrenamiento. Los
resultados experimentales mostraron que el coeficiente de correlación
entre los valores predichos y medidos alcanzó 0,96. El error cuadrático
medio, el error cuadrático medio, el error absoluto medio y el error
porcentual absoluto medio del modelo fueron de 6,89, 47,53, 6,17 y 0,04,
respectivamente. Además, el método propuesto presentó una mejor
capacidad de ajuste no lineal que BPNN y GA-BP. Mediante un algoritmo de
optimización inteligente, se estableció automáticamente la relación
entre la ingesta de peces y los factores ambientales, evitando así la
subjetividad de los métodos tradicionales. Por lo tanto, sienta las
bases teóricas para el desarrollo de equipos de alimentación
inteligentes y satisface las necesidades de la pesca inteligente.

Los investigadores (Yu et al., 2025), indicaron que en el campo de la
acuicultura de agua dulce, la calidad del agua impacta
significativamente en los productos acuícolas. Las fluctuaciones en la
calidad del agua pueden obstaculizar el crecimiento de los organismos
cultivados, provocar enfermedades frecuentes e incluso causar mortalidad
masiva. Por lo tanto, predecir con precisión la calidad del agua es
crucial. Para reducir la tasa de error que puede ocurrir al usar modelos
tradicionales de redes de memoria a corto y largo plazo (LSTM) para la
predicción de la calidad del agua, este artículo propone un modelo de
predicción de la calidad del agua Pearson-LSTM-AM. Inicialmente, se
utiliza el algoritmo de prueba de correlación de Pearson para la
selección de características de entrada, y luego se integra un mecanismo
de atención para mejorar la capacidad de la red neuronal LSTM para
aprender las características clave, específicamente para predecir el
indicador de oxígeno disuelto (OD) de la calidad del agua.

El experimento se llevó a cabo en los estanques de acuicultura de una
empresa ubicada en la ciudad de Hangzhou, provincia de Zhejiang, China,
con una superficie total de 120 acres y una profundidad de agua de 3 a 4
metros. Como se muestra en la
Figura  [**2**](https://onlinelibrary.wiley.com/doi/full/10.1111/jwas.70041#jwas70041-fig-0001) ,
el diagrama del modelo del estanque de acuicultura ilustra la
distribución y las características principales del montaje experimental.
Los estanques se diseñaron para simular condiciones reales, permitiendo
al mismo tiempo una experimentación controlada.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image4.png"
style="width:4.01482in;height:2.18451in" />

Figura 2. Diagrama modelo del estanque de acuicultura.

A finales de abril de 2023, se introdujeron 6000 alevines de lubina
negra en los estanques 1 a 3 y 5000 alevines en los estanques 4 a 6, con
un peso aproximado de 10 g por aleta. Tras la introducción de los peces,
se llevó a cabo un experimento de acuicultura, alimentándolos dos veces
al día (a las 7:00 y a las 18:00) con una ración del 2 % al 3 % de su
peso corporal. El ciclo completo de acuicultura se extendió hasta
finales de octubre, con una duración total del experimento de 7 meses.
La
Tabla  [**1**](https://onlinelibrary.wiley.com/doi/full/10.1111/jwas.70041#jwas70041-tbl-0001) presenta
los detalles de la implementación de la acuicultura desde abril de 2023
hasta octubre de 2023, incluyendo el número de alevines de lubina negra
en los estanques, su crecimiento y el consumo de alimento.

**TABLA 1. **Implementación de la acuicultura de abril a octubre de
2023: Número de alevines de lubina negra en estanques, crecimiento en
tamaño, uso de alimento.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image5.png"
style="width:3.09489in;height:1.90365in" />

Los datos para este proyecto provienen de los datos de calidad del agua
de los estanques proporcionados por la empresa de acuicultura,
incluyendo el valor de pH, la temperatura del agua, el oxígeno disuelto
(OD), el nitrógeno amoniacal, el nitrito, el potencial redox (ORP) y la
turbidez. Se tomaron muestras de agua de cada estanque antes de que
comenzara la alimentación todos los días, y el nitrógeno amoniacal y
otros datos del cuerpo de agua se midieron en el laboratorio utilizando
un analizador de tres nitrógenos. La temperatura del agua, el pH y otros
datos del cuerpo de agua de acuicultura se midieron mediante sensores y
se guardaron en la nube, con un total de 1903 puntos de datos
recopilados.

En el aprendizaje automático, los datos se dividen generalmente en dos
partes: el conjunto de entrenamiento y el conjunto de prueba. Al dividir
el conjunto de datos en conjuntos de entrenamiento y prueba, se puede
evitar el sobreajuste al construir modelos predictivos, y el modelo
final se puede evaluar y verificar de forma independiente a través del
conjunto de prueba, lo que garantiza su capacidad de generalización y
rendimiento.

En esta investigación, los datos de abril de 2023 a octubre de 2023 se
dividieron en dos partes en una proporción de 8:2. Los datos del 1 de
abril de 2023 al 20 de septiembre de 2023 se utilizaron como conjunto de
entrenamiento para entrenar el modelo de predicción de la calidad del
agua y obtener los mejores parámetros. Los datos del 21 de septiembre de
2023 al 30 de octubre de 2023 se utilizaron como conjunto de prueba para
evaluar el efecto predictivo del modelo. Los datos de calidad del agua
suelen presentar correlaciones temporales, ya sean mediciones horarias,
diarias o mensuales. Las redes LSTM funcionan bien para capturar
dependencias dentro de las series temporales. Por lo tanto, esta
investigación propone un modelo de predicción de la calidad del agua
basado en una red neuronal LSTM optimizada con pruebas de correlación de
Pearson y un mecanismo de atención (en adelante, Pearson-LSTM-AM). La
estructura específica del modelo se muestra en la
Figura  [3.](https://onlinelibrary.wiley.com/doi/full/10.1111/jwas.70041#jwas70041-fig-0003) El
modelo se divide en una capa de entrada, una capa LSTM, una capa de
atención y una capa de salida. Tras el preprocesamiento del conjunto de
datos, se seleccionan las características fuertemente correlacionadas
con el oxígeno disuelto (OD) mediante pruebas de correlación de Pearson,
mientras que se descartan las características menos correlacionadas.
Mediante el aprendizaje combinado de las capas LSTM y de atención, el
modelo puede explorar y capturar en profundidad los patrones intrínsecos
de las características, logrando así predicciones precisas, que
finalmente se presentan en la capa de salida.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image6.png"
style="width:3.40876in;height:4.07572in" />

Figura 3.Estructura del modelo de predicción Pearson-LSTM-AM. LSTM:
redes de memoria a corto y largo plazo.

Las descripciones básicas de cada capa del modelo son las siguientes:

1.  *Capa de entrada* : Inicialmente, preprocesa los datos de muestra y
    utiliza el método de prueba de correlación de Pearson para
    seleccionar elementos con una alta correlación con el OD.

2.  *Capa LSTM* : Utiliza la red neuronal de memoria a corto y largo
    plazo (LSTM) para procesar datos de series temporales, recibiendo
    datos de la capa de entrada y aprendiendo sus relaciones temporales.
    La LSTM consta de una serie de unidades de memoria, cada una con
    tres unidades de activación y un estado de celda: la puerta de
    entrada, la puerta de olvido y la puerta de salida. Estas unidades
    de activación controlan el flujo de información mediante funciones
    de activación (generalmente la función sigmoide), lo que permite a
    la LSTM recordar u olvidar selectivamente la información en la
    secuencia.

La red LSTM modela las dependencias a largo plazo en secuencias mediante
la combinación de sus unidades de activación. En cada paso de tiempo, la
red recibe la entrada actual y el estado oculto del paso anterior, y
actualiza ambos estados basándose en los cálculos de las unidades de
activación. Esto permite a la red predecir el siguiente estado o salida
a partir de la información contextual de la secuencia. La
figura  [**4**](https://onlinelibrary.wiley.com/doi/full/10.1111/jwas.70041#jwas70041-fig-0004) ilustra
la estructura de la red neuronal LSTM.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image7.png"
style="width:4.9708in;height:2.58373in" />

Figura 4. Diagrama estructural de una red neuronal de memoria a corto y
largo plazo (LSTM).

3.  Capa de atención: Los vectores de salida generados por la capa de
    red LSTM tras el procesamiento de activación se pasan a la capa de
    atención.

Esta capa asigna los valores de probabilidad de peso correspondientes a
los diferentes vectores de características según su mecanismo de
asignación y se ajusta continuamente para optimizar la configuración de
pesos de la matriz de parámetros. La estructura del mecanismo de
atención se muestra en la Figura 5.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image8.png"
style="width:3.97917in;height:3.11779in" />

Figura 5. Diagrama estructural del mecanismo de atención.

Aquí, h<sub>t</sub> (donde t ∈ \[1,n\]) representa los valores de
distribución de probabilidad asignados a la capa LSTM, e<sub>t</sub>
denota los pesos, α<sub>t</sub> representa los pesos finales, e Y es el
valor de salida. Las fórmulas de cálculo específicas son las siguientes:

$e_{t} = sigmoid\left( {Wh}_{t} + b \right)$………..(1)

$$\alpha_{t} = \frac{\exp\left( e_{t} \right)}{\sum_{i = 1}^{t}{\exp\left( e_{i} \right)}}\ldots\ldots\ldots\ldots\ldots.(2)$$

$Y = \sum_{i = 1}^{t}\alpha_{i}h_{i}$……………….(3)

4\. Capa de salida: La salida de la capa del mecanismo de atención sirve
como entrada para la capa de salida.

Los resultados experimentales demuestran que el método propuesto mejora
significativamente el modelo Pearson-LSTM y el modelo LSTM en términos
de error cuadrático medio (RMSE), error porcentual absoluto medio
(MAPE), error absoluto medio (MAE) y el coeficiente de determinación
R<sup>2</sup>

En la investigación, se usaron cuatro métricas de evaluación, entre las
que se incluyen el error cuadrático medio (RMSE), el error absoluto
medio (MAE), el error porcentual absoluto medio (MAPE) y el coeficiente
de determinación (R²), ampliamente utilizadas en la investigación
predictiva. El RMSE es uno de los indicadores más comunes para medir el
grado de ajuste del modelo predictivo a los datos. Cuanto menor sea el
valor del RMSE, mejor se ajustará el modelo a los datos. El MAE es
también uno de los indicadores para medir el rendimiento del modelo
predictivo. Cuanto menor sea el valor del MAE, menor será el error de
predicción del modelo. El MAPE es otro indicador utilizado para evaluar
el modelo predictivo. Cuanto menor sea el valor del MAPE, menor será el
error relativo del modelo. El coeficiente de determinación R² es uno de
los indicadores que miden el grado de ajuste del modelo predictivo a los
datos. Representa la medida en que el modelo explica la varianza de los
datos observados, con un rango de 0 a 1. Cuanto más cerca de 1, mejor se
ajusta el modelo a los datos; cuanto más cerca de 0, peor se ajusta. Los
datos de calidad del agua, recopilados mediante diversos procesos,
pueden verse afectados por numerosos factores que interfieren, lo que
potencialmente genera ruido y datos faltantes.

El uso directo de datos brutos de calidad del agua para análisis
experimentales sin preprocesamiento puede ocultar patrones en los
cambios de datos y afectar gravemente la precisión del entrenamiento del
modelo. Por lo tanto, es esencial preprocesar los datos de calidad del
agua para mejorar su calidad y la fiabilidad de los resultados
analíticos.

En el preprocesamiento de datos, los métodos comunes para manejar los
valores faltantes incluyen ignorar, eliminar o imputar datos. Ignorar
implica no tener en cuenta el impacto de los datos faltantes, mientras
que eliminarlos simplemente los borra. La eliminación es adecuada cuando
el conjunto de datos original está prácticamente completo, pero eliminar
información válida sustancial puede sesgar el análisis.

El método más eficaz es la imputación, que completa los valores
faltantes con valores especiales, promedios o múltiples imputaciones
derivadas de distribuciones estadísticas. Este estudio emplea
interpolación lineal para imputar valores faltantes, lo que supera a la
imputación de la media en la preservación de las características de
tendencia de los datos de series temporales. Para filtrar los valores
atípicos, se aplica el criterio de Pauta (regla de 3σ).

Este criterio presupone que un conjunto de datos contiene únicamente
errores aleatorios. Al calcular la desviación estándar (σ) de los datos,
se puede cuantificar el grado de dispersión de los puntos de datos
alrededor de la media (μ) en una distribución normal. Las formulaciones
matemáticas son las siguientes:

$\mu = \frac{1}{N}\sum_{i = 1}^{N}X_{i}$………………(4)

$\sigma = \sqrt{\frac{\sum_{i = 1}^{N}\left( X_{i} - \mu \right)^{2}}{N}}$……………………(5)

Al predecir la calidad del agua, los diferentes indicadores suelen tener
unidades distintas, lo que puede afectar significativamente la precisión
del modelo.

Para mejorarla, es necesario normalizar los parámetros de entrada,
limitándolos a un rango de 0 a 1. Esto ayuda a prevenir el sobreajuste
debido a parámetros excesivamente grandes. En esta investigación, se
utiliza el método de normalización min-max para asegurar que los
parámetros de entrada se encuentren dentro de un rango adecuado,
mejorando así la estabilidad del modelo de evaluación de la calidad del
agua.

$x^{'} = \frac{x - \min_{x}}{\max(x) - min(x)}$……………………(6)

Sea x el valor del indicador de calidad del agua que se va a medir,
donde min(x) y max(x) denotan los valores mínimo y máximo del indicador,
respectivamente. X<sup>’</sup> representa el resultado normalizado.

(Soderberg, 2006), desarrollaron un modelo de crecimiento lineal para
tilapia nilótica para cultivo intensivo eficiente que predijo con
precisión el crecimiento diario en incrementos de longitud en función de
la temperatura. Para dicha experiencia se utilizó peces de diferentes
tamaños, pero de la misma procedencia con reversión sexual a andrógenos
en un rango de temperaturas durante dos años.

En la experiencia **del año 2002** los peces crecieron con un peso
inicial de 1.8 g y longitud de 47 mm a un rango de pesos de 5.0 a 26 g
con longitudes de 67 a 112 mm, en un **tiempo de 50 días** en un rango
de temperaturas de 21 a 30 °C. El crecimiento de los peces (mm/día)
mostró una alta correlación con la temperatura (r<sup>2</sup> = 0,99).

**En el año 2005**, fue realizado otra experiencia con peso inicial de
47 g (137 mm) creciendo a un peso final de 107 y 219 g (178 a 225 mm) en
un tiempo de 70 días, el coeficiente R<sup>2</sup> fue de 0.94. Las dos
pendientes no difirieron (P \< 0,05), por lo que conllevó a presentar
una ecuación (1) para predecir las tasas de crecimiento de la tilapia
del Nilo en cultivo en agua corriente para el rango de temperatura de
21–30 °C:

ΔL = -1,6707 +0,09682T ……..(1)

Obteniéndose un R² = 0,95.

Donde ΔL es el crecimiento predicho (mm/d) y T es la temperatura (°C).

El peso (W; g) se puede calcular en función a la longitud (L; mm) para
la tilapia del Nilo macho, a través de la ecuación (2)

W (g) =1,861×10<sup>-8</sup> L³…………....(2)

La ​​ecuación (3) de crecimiento lineal para la tilapia azul (O. aureus)
es:

ΔL = -0,853 + 0,048T………….(3)

Donde

- ΔL es el crecimiento diario en longitud (mm/d).

- T es la temperatura (°C)

Tradicionalmente, **las tasas de crecimiento de la tilapia** se han
reportado en gramos por día. Con el uso de dietas completas en estanques
de agua estancada, las tasas de crecimiento de la tilapia han oscilado
entre 1,59 y 2,80 g/día.

Estos valores tienen una aplicación limitada al cultivo de peces en agua
corriente, debido a que no se especifican las temperaturas ni el peso
inicial de los peces, y a que los factores ambientales que afectan el
crecimiento de los peces son diferentes en los sistemas de agua
estancada que en los de agua corriente.

También informaron que el crecimiento de la tilapia del Nilo en agua a
28–30 °C osciló entre 0,5 g/día para peces de 5–20 g y 2,9 g/día para
peces de 250–450 g (Tabla 1).

Al convertir estos datos de crecimiento a milímetros por día, mediante
la conversión de peso (W, g) a longitud (L, mm) con la ecuación (4)

W = 2,330 × 10 <sup>-8</sup> L<sup>3</sup>……(4)

se obtienen valores de ΔL que varían entre 0,68 y 1,17 mm/día (Tabla 1).
El valor relativamente constante de ΔL, que promedia 1,145 mm/día para
peces de hasta 250 g, demuestra la naturaleza lineal del crecimiento de
los peces. La menor tasa de crecimiento en la etapa final del cultivo
(Tabla 1) puede atribuirse a influencias endógenas. Pocos estudios sobre
el crecimiento de la tilapia han reportado datos para peces de más de
350 g. La mayoría de los informes sobre el cultivo de tilapia en agua
estática muestran un crecimiento lineal hasta un tamaño aproximado de
250 g.

TABLA 1: Tasas de crecimiento (Growth rate) de la tilapia del Nilo en
gramos por día y convertidas a milímetros por día mediante la ecuación
peso-longitud: W = 2,330 × 10<sup>-8</sup> L³ (Soderberg, 2006).

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image9.png"
style="width:4.0138in;height:1.62879in" />

La ecuación presentada por la tilapia azul predice tasas de crecimiento
de 0,49 mm/día a 28 °C y 0,59 mm/día a 30 °C. Estas tasas de crecimiento
son claramente demasiado bajas para la tilapia del Nilo. El objetivo de
este estudio fue desarrollar un modelo de crecimiento lineal para la
tilapia del Nilo para su aplicación en la acuicultura en agua corriente,
como en sistemas de flujo continuo, reutilización en serie o
recirculación.

En el Experimento del 2002, cada lado de cuatro sistemas de cultivo en
canal se repobló con 54 tilapias del Nilo macho de 1,8 g, procedentes de
un criadero comercial de Nuevo México. Las temperaturas de prueba fueron
de 21, 25, 28 y 30 °C. El experimento finalizó 50 días después de la
repoblación. Las temperaturas se mantuvieron dentro de un margen de 0,5
°C del valor seleccionado. En el experimento de 2005, cada lado de tres
sistemas de cultivo en canal se repobló con veintiún tilapias del Nilo
macho de 47 g, procedentes de la misma fuente que en 2002. Las
temperaturas de prueba fueron de 23, 27 y 30 °C. Las temperaturas se
mantuvieron dentro de un margen de 0,5 °C del valor seleccionado. Este
ensayo se llevó a cabo durante 70 días. Durante el experimento del 2002,
las temperaturas medias reales del agua en los ocho canales fueron de
20,9, 21,1, 25,0, 25,2, 28,1, 28,3, 29,9 y 30,18 °C. La longitud final
de los peces osciló entre 67,2 y 112,5 mm (5–26 g), y las tasas de
crecimiento diarias variaron entre 0,40 y 1,31 mm/d (Tabla 2). El
crecimiento estuvo altamente correlacionado con la temperatura (r =
0,99), y la ecuación (5) de crecimiento resultante fue:

ΔL = -1,6623 + 0,097021T ………(5)

- Las concentraciones de oxígeno disuelto nunca descendieron por debajo
  de 3,5 mg/L (74 mm Hg a 30 °C).

- El amoníaco total alcanzó 1,35 mg N/L, y el NH₃ alcanzó 0,0067 mg N/L.

- Los niveles de nitrito alcanzaron 1,22 mg/L. No se observaron
  diferencias significativas en las variables químicas del agua (P \>
  0,05) entre los tratamientos de temperatura.

TABLA 2.—Aumento de longitud de tilapias del Nilo macho cultivadas a
diversas temperaturas durante 50 días en sistemas cerrados en la
Universidad de Mansfield, Mansfield, Pensilvania, en 2002. La longitud
inicial de los peces en todos los grupos fue de *47 mm*.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image10.png"
style="width:4.0303in;height:1.78785in" />

En el experimento del 2005, las temperaturas medias reales del agua
durante 2005 en los seis estanques fueron de 23,5, 23,6, 26,8, 26,5,
29,2 y 29,8 °C. La longitud final de los peces osciló entre 177,6 y
225,5 mm (107-219 g), y las tasas de crecimiento diarias variaron entre
0,55 y 1,28 mm/d (Tabla 3). El crecimiento estuvo altamente
correlacionado con la temperatura (r = 0,94), y la ecuación (6) de
crecimiento resultante fue:

ΔL = -1,7147 + 0,097794T……………(6)

No se observaron diferencias significativas en las variables químicas
del agua (P \> 0,05) entre los tratamientos de temperatura.

- Las concentraciones de oxígeno disuelto en 2005 nunca descendieron por
  debajo de 4,7 mg/L (100 mm Hg a 30 °C).

- El amoníaco total alcanzó 0,9 mg N/L, y el NH₃ alcanzó 0,0106 mg N/L.

- Los niveles de nitrito alcanzaron 0,03 mg/L. No se observaron
  diferencias significativas en las variables químicas del agua (P \>
  0,05) entre los tratamientos de temperatura.

No se registró mortalidad de peces en ninguno de los experimentos.
Ninguna de las hipótesis sobre la igualdad de pendientes e
intersecciones de las dos líneas de regresión fue rechazada (P \> 0,05;
Figura 6), por lo que combiné los datos de los dos años en una sola
regresión y determiné la siguiente ecuación para predecir las tasas de
crecimiento de la tilapia del Nilo en el rango de temperatura de 21–30
°C:

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image11.png"
style="width:3.83333in;height:2.72281in" />

FIGURA 6.—Regresión de la tasa de crecimiento diario en función de la
temperatura para tilapias del Nilo macho criadas en estanques de cultivo
en la Universidad de Mansfield, Mansfield, Pensilvania, en 2002 y 2005.
Las pendientes y las intersecciones no presentan diferencias
significativas (P \> 0,05).

TABLA 3.—Aumento de longitud en tilapias del Nilo macho cultivadas a
diferentes temperaturas durante 70 días en sistemas cerrados en 2005.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image12.png"
style="width:3.99236in;height:1.75764in" />

ΔL = -1,6707 + 0,09682T……….(1)

Donde

- ΔL es el crecimiento previsto (mm/día) y T es la temperatura.

- El peso se puede convertir a longitud para la tilapia del Nilo macho
  mediante la expresión W = 1,861 × 10 <sup>-8</sup> L³, que es la media
  de los dos valores obtenidos.

La calidad del agua fue mejor en 2005 que en 2002, pero todos los
parámetros de calidad del agua se mantuvieron dentro de los estándares
aceptables y, por lo tanto, probablemente no influyeron en el
crecimiento. La ausencia de pendientes significativas en las regresiones
de los parámetros de calidad del agua y la temperatura experimental
demuestran que los tratamientos de temperatura no afectaron la calidad
del agua. La diferencia en K entre los peces más grandes en 2005 y los
más pequeños en 2002 fue leve y no causaría errores prácticos al
convertir la longitud a peso.

Por ejemplo, un pez de 200 mm tendría un peso estimado de 145 g según el
valor de K de 2002 de 1,811×10<sup>-8</sup> y un peso estimado de 153 g
según el valor de 2005 de 1,911 ×10<sup>-8</sup>. Creo que este error es
lo suficientemente pequeño como para justificar la recomendación del
valor medio de K de 1,861 ×10<sup>-8</sup> como punto de partida al
evaluar las relaciones longitud-peso específicas de cada sitio para la
tilapia del Nilo.

La acuicultura intensiva eficiente requiere que las raciones de alimento
se calculen con precisión mediante la ecuación (7)

F = \[(3 x C x ΔL)/L\] x100…………..(7)

Donde

- F es la ración diaria de alimento en porcentaje del peso corporal por
  día,

- C es la conversión de alimento,

- ΔL es la tasa de crecimiento diaria en incrementos de longitud y

- L es la longitud del pez el día de la alimentación.

El modelo de crecimiento lineal presentado aquí puede utilizarse para
estimar la tasa de crecimiento diaria.

En la acuicultura intensiva, los peces se pesan periódicamente, pero su
peso diario, necesario para determinar la ración diaria de alimento, se
estima a partir de la longitud proyectada.

El peso se puede convertir a longitud para la tilapia del Nilo macho con
ecuación (2)

W = 1,861 × 10 <sup>-8</sup>L³……….(2)

La técnica de estimación descrita aquí probablemente no sea aplicable al
crecimiento de la tilapia en aguas naturales o estanques de agua
estancada debido al acceso a alimentos naturales, las fluctuaciones de
temperatura y otros factores exógenos que no se presentan en la
acuicultura en agua corriente.

Las relaciones longitud-peso, las tasas de crecimiento y las
conversiones de alimento variarán entre las cepas de tilapia del Nilo y
entre las diferentes formulaciones de dieta. Los valores y
procedimientos aquí descritos deberían proporcionar pautas útiles para
el cultivo intensivo de tilapias. (Taylor & Soderberg, 2011) indicaron
que el crecimiento de los peces se suele proyectar en función de las
unidades de *temperatura* necesarias por cada incremento de *longitud*.
Estas unidades de temperatura son *grados-día* o grados-mes y se
obtienen representando el crecimiento en el eje horizontal y la
temperatura en el eje vertical.

Los peces de agua fría presentan una intersección con el eje vertical
cercana a 0 °C, mientras que la gráfica del crecimiento de los peces de
agua cálida probablemente cruce el eje vertical a una temperatura
considerablemente más alta. Esta temperatura teórica de crecimiento cero
debe restarse de la temperatura media del agua para obtener un modelo de
crecimiento preciso. Se han descrito unidades de temperatura para las
escalas Fahrenheit y Celsius para el crecimiento incremental, tanto en
unidades inglesas como métricas, con y sin la corrección de la
intersección. Las diferentes definiciones de unidades de temperatura y
escalas de medición, junto con los cálculos complejos y confusos
necesarios para predecir el crecimiento de los peces de esta manera,
hacen necesario un método universal más sencillo. Un modelo de
crecimiento de peces simple y útil se obtiene mediante la regresión de
la variable dependiente (crecimiento) frente a la variable independiente
(temperatura), y la predicción del crecimiento a partir de la
temperatura con la ecuación de regresión resultante.

En este artículo, se presentó ecuaciones de crecimiento lineal para la
trucha de arroyo (Salvelinus fontinalis), la trucha arcoíris
(Oncorhynchus mykiss), la trucha de lago (Salvelinus namaycush), la
trucha arcoíris anádroma (steelhead), el salmón del Atlántico (Salmo
salar), el bagre de canal (Ictalurus punctatus), el lucio tigre (Esox
masquinongy x E. lucius) y la tilapia azul (Tilapia aurea).

Cuando se analizó el crecimiento de la tilapia azul (Tilapia aurea u
Oreochromis aureus) a diferentes temperaturas mediante el procedimiento
TU, que consiste en representar el crecimiento en el eje horizontal y la
temperatura en el eje vertical, la intersección para un crecimiento
teórico nulo fue de 17,8 °C. Cuando se aplicó el mismo procedimiento a
los datos de crecimiento del bagre de canal (Ictalurus punctatus).
Debido a la confusión asociada con los diferentes modelos de unidades de
temperatura que presentan distintas intersecciones y unidades de medida,
Soderberg, propuso que la variable independiente, la temperatura, se
analizara en función del crecimiento según el modelo lineal general. El
valor ΔL, necesario en la ecuación de tasa de alimentación y en la
proyección del crecimiento de los peces, se puede calcular a partir de
la ecuación (8) de regresión.

ΔL = *α* + *bT*…………..(8)

Donde:

- α es la intersección,

- b es la pendiente y

- T es la temperatura.

- ΔL incremento de la longitud del crecimiento.

En este artículo se presentó ecuaciones de regresión que pueden
utilizarse para predecir la longitud de la cadena alimenticia (ΔL) para
la trucha de arroyo, la trucha arcoíris, la trucha de lago, la trucha
steelhead, el salmón del Atlántico, el bagre de canal, el lucio tigre y
la tilapia azul. Para el canal artificial, los datos de crecimiento en
unidades de peso de Andrews et al. (1972) se convirtieron a unidades de
longitud mediante la ecuación (9):

$L^{3} = \frac{W}{0.0002877}$……………….(9)

Donde:

L = longitud en pulgadas y W = peso en libras. Estos datos se sometieron
a un análisis de regresión para obtener un modelo de crecimiento lineal

Los peces crecen de forma más eficiente dentro de rangos de temperatura
relativamente estrechos.

La ecuación de crecimiento más precisa corresponde al rango de
temperatura de 7 a 16 °C (Tabla 1).

TABLA 1.— Modelos lineales para el crecimiento de peces en criaderos.
T=temperatura (°C);

ΔL = crecimiento diario (mm/d); R<sup>2</sup> es el coeficiente de
determinación.

<img
src="Informe017_Crecimiento_Alimentacion_ML_media/media/image13.png"
style="width:5.38194in;height:2.82394in" />

El primer paso para utilizar estas ecuaciones es seleccionar la que
tenga el coeficiente de determinación más alto para el rango de
temperatura en el que se requiere ΔL.

Por ejemplo, si se requiere el crecimiento de la trucha arcoíris a 10
°C, se debe usar la ecuación ΔL = -0,167 + 0,066T, ya que las otras dos
ecuaciones presentadas para esta especie se determinaron en rangos de
temperatura mayores y, por lo tanto, tienen coeficientes de
determinación más bajos, lo que indica que son menos precisas. Este
valor de ΔL calculado se introduce luego en la ecuación (10) de tasa de
alimentación de Haskell (1959).

$F = \frac{(3xCx\mathrm{\Delta}L)}{L}$ x 100……….(10)

F = porcentaje del peso corporal del alimento suministrado por día.

C = conversión de alimento, y

L = longitud del pez (en las mismas unidades que ΔL).

La tasa de alimentación cambia diariamente porque ΔL se suma al valor de
L del día anterior. Por lo tanto, la longitud proyectada se tabula
diariamente. Al realizar el inventario de peces, la longitud proyectada
se compara con la longitud real y se ajusta AL para tener en cuenta
cualquier desviación específica de la piscifactoría con respecto al
modelo de crecimiento. El procedimiento descrito anteriormente requiere
la conversión matemática de longitud a peso.

1.  **Logros.**

Dentro de los mecanismos o modelos descritos para el crecimiento de los
peces y consumo de alimento con respecto a factores que influyen en
estos, se propuso los siguientes modelos:

- Modelo de predicción del consumo de alimento para grupos de peces
  mediante una red neuronal de retropropagación (BPNN) y un algoritmo
  evolutivo mental (MEA) que está relacionado con cuatro factores de
  entrada como: la temperatura del agua, el oxígeno disuelto, el peso
  promedio de los peces y el número de peces, así como el peso inicial y
  el umbral de la BPNN.

- Después se revisó el modelo de predicción de la calidad del agua
  Pearson-LSTM-AM.

- Se mencionó al modelo para predecir el crecimiento de peces tilapias
  nilóticas en cultivo intensivo simple mediante la regresión lineal de
  la variable dependiente (crecimiento o incremento ΔL expresado en mm
  por día) frente a la variable independiente (temperatura en °C). luego
  el peso se puede predecir con relación a su longitud final dada en mm.

- Por otro lado, se revisó la relación de la ración diaria de alimento
  en porcentaje del peso corporal por día, respecto a la conversión de
  alimento, tasa de crecimiento (ΔL) y la longitud del pez.

  1.  **Resultados alcanzados.**

<!-- -->

- Se encontró una ecuación de regresión lineal para predecir las tasas
  de crecimiento de la **tilapia del Nilo** en cultivo en agua corriente
  para el rango de temperatura de 21–30 °C, definida por la ecuación:

ΔL = -1,6707 +0,09682T ……..(1)

**Referencias**

Chen, L., Yang, X., Sun, C., Wang, Y., Xu, D., & Zhou, C. (2020). Feed
intake prediction model for group fish using the MEA-BP neural network
in intensive aquaculture. *Information Processing in Agriculture*,
*7*(2), 261–271. https://doi.org/10.1016/j.inpa.2019.09.001

Soderberg, R. W. (2006). A Linear Growth Model for Nile Tilapia in
Intensive Aquaculture. *North American Journal of Aquaculture*, *68*(3),
245–248. https://doi.org/10.1577/a05-030.1

Taylor, P., & Soderberg, R. W. (2011). *The Progressive Fish-Culturist
Linear Fish Growth Models for Intensive Aquaculture Linear Fish Growth
Models for Intensive Aquaculture*. *May 2013*, 37–41.

Yu, W., Wu, M., & Ha, Z. (2025). Research on a Pearson-LSTM-AM-based
water quality prediction model for freshwater aquaculture. *Journal of
the World Aquaculture Society*, *56*(4), 1–16.
https://doi.org/10.1111/jwas.70041
