**INFORME DE ACTIVIDADES N°015-2026-REAJ**

1.  **Presentación de informe**

**Entidad Ejecutora :** UNIDAD EJECUTORA 002 - INICTEL-UNI

**Contrato :** N° PE501091609-2024-PROCIENCIA

**Proyecto de Investigación :** "Validación de una estación de monitoreo
de calidad de agua y dosificación de Floc bacteriano para crianza masiva
de peces en piscigranjas artificiales con geomembrana utilizando
aprendizaje automático e Internet de las Cosas"

**Responsable Técnico :** Ing. Rubén Acosta Jacinto

**Resolución Directoral :** N° 000047-2025-INICTEL-UNI/DE

**Periodo de Informe :** enero 2026

| **DESCRIPCIÓN DE LAS ACTIVIDADES REALIZADAS**                                     | **TOTAL**  |
|-----------------------------------------------------------------------------------|------------|
| \- Revisión de la tecnología Gemelo Digital aplicado al sector de la acuicultura. | S/. 700.00 |

-----------------------------------------------

Rubén Eusebio Acosta Jacinto

Investigador Principal

N°PE501091609-2024-PROCIENCIA

2.  **Avances**

**Revisión de la tecnología Gemelo Digital aplicado al sector de la
acuicultura.**

Un gemelo digital es una **réplica virtual** del comportamiento o
característica de un objeto, sistema o **proceso físico**, que se
**actualiza** en tiempo real a través de sensores, permitiendo simular,
monitorear, analizar dicho comportamiento y predecir fallos del sistema.
El modelo virtual se crea sobre la base de los datos recopilados. En la
figura 1, se muestra un esquema del funcionamiento de un gemelo digital.

<img
src="Informe015_Gemelo_Digital_media/media/image1.png"
style="width:5.90556in;height:2.86111in" />

Fig. Funcionamiento de un gemelo digital.

El gemelo digital no solo recibe y procesa los datos, sino que también
los retroalimenta al sistema real en un bucle de retroalimentación
continuo. Una simulación convencional no puede lograr esto.

Los investigadores (Lima et al., 2022) en su publicación de revisión
indicaron que la contraparte virtual de un objeto físico, denominada
gemelo digital, se deriva del Internet de las Cosas (IoT) e implica la
adquisición y el procesamiento en tiempo real de grandes conjuntos de
datos.

En este escenario, describieron el caso de la aplicación de gemelos
digitales (GD) en acuicultura terrestre de *trucha arcoíris*
(Oncorhynchus mykiss) con el objetivo de ayudar a los *productores a
optimizar las prácticas de alimentación*, *suministración de oxígeno
disuelto y gestión de la población de peces* que mejore el crecimiento.
Para la implementación del gemelo digital en acuicultura utilizaron
modelos matemáticos predictivos con *ingreso de datos en tiempo real*
que permitió la simulación del proceso dinámico que describió los
componentes de entorno acuícola y peces, que fueron representados por el
ciclo de cría de las *truchas arcoíris* que viven a bajas temperaturas y
alta concentración de oxígeno disuelto en una piscifactoría terrestre de
200 m de largo y 8 m de ancho cubiertas por redes de protección, para
evitar la depredación de aves con ingreso de agua dulce del río Sarca de
Italia. Para esta aplicación de GD. La metodología del GD incorporó 4
fases denominadas: observación, interpretación, decisión y actuación que
fueron destinadas al *control del alimento y oxígeno disuelto, así como
la biomasa a lo largo de las fases de crecimiento de los peces,* desde
los alevines hasta el peso comercial.

Por otro lado, los investigadores describieron que los procesos
dinámicos de un GD del tipo de monitoreo aplicado a una piscifactoría
están representados por la calidad de agua y la biomasa de los peces.
dicha calidad de agua, estuvo representada por los valores obtenidos en
tiempo real de los parámetros de temperatura, pH, OD, concentración de
amoniaco y CO<sub>2</sub>, mientras que, para la biomasa es el peso de
los peces. A este GD podría ser del tipo prescriptivo, si el proceso
dinámico utilizaría modelo matemático dinámico con series temporales del
aumento del peso y consumo de OD, que permitiría la optimización de la
alimentación, caudal, suministro de oxígeno y liberación de aguas
residuales. En una piscifactoría, la mayoría de las operaciones
acuícolas, como la alimentación que actúa sobre los peces a través del
agua, el metabolismo de los peces depende en gran medida de la
temperatura del agua y en caso de condiciones ambientales desfavorables,
como temperaturas extremas, anoxia o presencia de contaminantes y
patógenos, toda la población se ve afectada. El cuantificar las
relaciones entre las variables ambientales y animales es una
característica fundamental del modelo matemático que traduce estas
variables en descripciones presentes y futuras del objeto digital. Las
variables animales están relacionadas con el peso y tamaño de los peces,
el número de peces sembrados y muertos. Paralelamente a las variables
ambientales y animales, las representaciones digitales se organizarán en
dos componentes: agua y peces respectivamente. En la figura 1, se
muestra las piscifactorías (granjas) de la cría de truchas arcoíris
perteneciente el grupo ASTRO de Italia, que desarrolló un protocolo
estandarizado que abarca aspectos claves de gestión de la granja como:
la alimentación, densidad de la población de peces, calidad de agua y
calidad del producto final (propiedades fisicoquímicas de la carne) con
certificación de Indicación Geográfica Protegida (IGP).

<img
src="Informe015_Gemelo_Digital_media/media/image2.png"
style="width:5.92492in;height:2.06542in" />

Figura 1. Piscifactorías (Granjas) de la cría de truchas arcoíris.

El diagrama del flujo de información del GD implementado por el grupo
ASTRO está basado en las fases de observación, interpretación, decisión
y actuación. En la figura 2, se muestra una descripción y conexión de
las fases del flujo de información del GD. **La fase de observación**
tiene como objetivo extraer los datos cuantitativos del objeto físico e
insertarlos al modelo matemático. Estos datos derivan del valor de
sensores que miden oxígeno disuelto y temperatura del agua. así como, el
ingreso del alimento, la biomasa y recuento de peces utilizando cámaras
sumergidas en agua durante las fases de crecimiento de los peces en la
piscigranja. El envío de estos datos a la base de datos se registraba
cada 15 minutos o 1 hora. Para la estimación del peso promedio de los
peces en base el ingreso de alimentos con respecto al metabolismo y
excremento se utilizó el modelo matemático bioenergético y para la
determinación del OD, se usó el modelo de transporte de OD.

<img
src="Informe015_Gemelo_Digital_media/media/image3.png"
style="width:3.97196in;height:3.61168in" />

Figura 2. Diagrama de flujo de información para el modelo conceptual del
gemelo digital.

El modelo de transporte de OD, puede estimar la cantidad de OD para la
respiración de los peces en cada fase de crecimiento de los peces. en la
figura 3, se muestra la delimitación del objeto físico.

<img
src="Informe015_Gemelo_Digital_media/media/image4.png"
style="width:4.58878in;height:4.2395in" />

Figura 3. Esquema de delimitación del objeto físico.

**La fase de interpretación** tiene como objetivo simular la evolución
de la biomasa de los peces en base al metabolismo de los peces (ingreso
del alimento, ración) y las variables de la calidad de agua afectada
durante dicha evolución. En la figura 4, se muestran las salidas de los
modelos matemáticos (bioenergético y transporte de OD) deben
proporcionar imágenes en tiempo real de cómo se encuentra el objeto
físico.

<img
src="Informe015_Gemelo_Digital_media/media/image5.png"
style="width:5.90417in;height:3.02986in" />

Figura 4. Esquema de entradas y salidas a los modelos dinámicos
bioenergético y de OD.

El modelo bioenergético simula el crecimiento de la trucha arcoíris con
el registro de la temperatura del agua, la ración de alimentación
(cantidad de alimento en Kg). Para ello el alimento tuvo una composición
química basado en proteínas, lípidos y carbohidratos. Este modelo
considera el cambio del peso (serie temporal) a lo largo del tiempo
derivado de la ingesta del alimento y energía utilizada para el
metabolismo de los peces. Luego el modelo de transporte de OD evaluó la
concentración de OD en los canales de recirculación. En esta aplicación
del GD se aplico la ecuación (1) donde el modelo bioenergético
interacciona con el modelo de transporte de OD.

$\frac{{\partial C}_{(x,t)}}{\partial t} = - \frac{(Q)}{(A)}\frac{{\partial C}_{(x,t)}}{\partial x} + K_{rear}\left( {Csat}_{(x,t)} - C_{(x,t)} \right) - \frac{R_{(t)}}{A}\frac{{\partial M}_{(x,t)}}{\partial_{(x)}}$……(1)

Donde:

- x es la coordenada de la corriente (m)

- t es el tiempo (h)

- <span class="mark">C es la concentración de DO
  (mgL<sup>-1</sup>).</span> Ingreso de OD-aireador.

- <span class="mark">Csat es la concentración de saturación de DO
  (mgL<sup>-1</sup>).</span> Ingreso de OD-aireador.

- <span class="mark">k <sub>rear</sub> es la tasa de reaireación
  (h<sup>-1</sup>).</span> Ingreso de OD-aireador.

- <span class="mark">Q es el caudal de agua (Lh<sup>-1</sup> ).</span>
  Ingreso de OD-caudal-agua.

- <span class="mark">A es el área de la sección transversal del canal de
  recirculación (m<sup>2</sup> ).</span> Ingreso de OD-caudal.

- <span class="mark">R es la tasa de consumo de oxígeno (mg
  h<sup>-1</sup>L<sup>-1</sup> ).</span> Consumo OD-Biomasa.

- <span class="mark">M biomasa de peces acumulada a lo largo dirección
  de la corriente x (kg)</span>. Consumo OD.

Los períodos de tiempo de permanencia del agua en los canales de ingreso
son usados en el modelo de transporte de OD cuya cantidad de
concentración depende de la temperatura del agua, tasa de respiración de
los peces y de la fuente de agua, tal como se muestra en la figura 4. En
este GD el ingreso de datos se divide en componentes agua y biomasa de
peces.

El uso de variables para cada componente se muestra en la figura 5. **El
componente agua** para el Gemelo Digital está formada por los parámetros
del canal que conduce el agua para llenar las piscinas acuícolas como:
*Tasa de flujo* (m<sup>3</sup>/h), *volumen* (m<sup>3</sup>), *tiempo de
residencia del agua en el canal* (h) y *profundidad* (m), también se
selecciona el período de tiempo de 9 días con una fecha inicial
(03-07-2019) a una fecha final (12-07-2019) con *distancia de canal* de
0 a 200 m.

Para desplegar un gráfico se debe seleccionar un parámetro específico
como: temperatura del agua, concentración de OD, concentración de amonio
y densidad de biomasa de peces. **El componente** **biomasa de peces,**
se selecciona el período de 4, 5 meses desde una fecha inicial
(01-07-2020) a una fecha final (20-11-2020) y para desplegar la vista
del resultado con respecto a: el peso del pez, tasa metabólica,
alimentación (consumida/deseada) y limitación de temperatura.

<img
src="Informe015_Gemelo_Digital_media/media/image6.png"
style="width:6.02046in;height:2.68984in" />

Figura 5. Vistas seleccionadas del gemelo digital.

Luego la fase decisiva y de actuación tiene como objetivo realizar el
control del alimento y oxígeno disuelto, así como la biomasa a lo largo
de las fases de crecimiento de los peces, desde los alevines hasta el
peso comercial.

Los investigadores (Føre et al., 2024), indican que la tecnología de
Gemelos Digitales (GD) se ha convertido en una tecnología clave en la
transición hacia la industria 4.0, el cual definen que el GD, es una
representación digital de un activo o sistema físico, que proporciona
una mejor comprensión de su dinámica al *combinar el* *conocimiento
previo* del sistema mediante *modelos matemáticos con los datos
adquiridos en tiempo real de sensores e instrumentos conectados al
sistema físico*. Por otro lado, su aplicación en la acuicultura todavía
está en sus primeras etapas. Estos investigadores explicaron en su
revisión cuales sería los posibles componentes y niveles de un GD, luego
describieron casos prácticos desarrollo de relevancia industrial en las
condiciones de oxígeno disuelto en jaulas marinas, el crecimiento de
peces en las jaulas marinas y la robótica en jaulas marinas. Explicaron
la revisión que una acuicultura intensiva es una actividad importante
generadora de alimento de consumo humano y la importancia del control
activo de las condiciones de cultivo

en una piscicultura intensiva para suministrar alimento. La cría en
jaulas ha crecido rápidamente en los últimos años, tanto en términos de
tonelaje bruto como de escala local (McIntosh et al., 2022). Por
ejemplo, una granja típica de salmón puede contener actualmente entre 10
y 15 jaulas, cada una con una circunferencia de hasta 200 m y una
profundidad de hasta 50 m, y que contienen hasta 200 000 peces. Por otro
lado, explicaron la unión de la piscicultura de precisión a gemelos
digitales, donde se combina sensores con modelos matemáticos en una
plataforma de internet de las cosas, para una mejor interpretación,
presentación y refinamiento de los datos de medición. En esta parte
indicaron que se está estudiando la dinámica de oxígeno en granjas
oceánicas. En la figura 6, se muestra la gráfica que representa la
metodología del Gemelo digital en piscicultura de precisión en 4 fases.

<img
src="Informe015_Gemelo_Digital_media/media/image7.png"
style="width:2.94355in;height:2.85586in" />

Fig. 6. Metodología del GD en piscicultura de precisión con sus cuatro
fases, según (Føre et al., 2017)

Como se sabe los datos históricos de la gestión de la piscifactoría y
los datos obtenidos por sensores en tiempo real del activo físico, se
utilizan junto al conocimiento existente del sistema para construir los
modelos matemáticos predictivos que describen el proceso. También, los
gemelos digitales podrían representar escenarios hipotéticos para
explorar el impacto de situaciones o condiciones del activo sin tener
que exponerlo a ellas. Por otro lado, los modelos basados en
conocimiento (MBC) son herramientas para operacionalizar el conocimiento
a priori existente. Los MBC, se construye su dinámica en ecuaciones
matemáticas para predecir las respuestas del sistema dinámico al ser
sometido a un conjunto de entradas. Los MBC suelen establecer una línea
divisora entre los datos medidos y su análisis.

Los modelos basados en datos (MBD), requiere un conjunto de entrada de
datos conocidos del sistema físico. Luego, se utilizan métodos de
inteligencia artificial (IA) y aprendizaje automático (ML) para
*identificar transformaciones de entrada/salida*, lo que permite
predecir las respuestas del sistema dado un conjunto de entradas
conocidas y condiciones iniciales/límite. Pero puede darse una
combinación de los modelos MBC y MBD, es decir, el MBC se usa para
representar la parte de la dinámica del sistema conocida por la ciencia
y que puede describirse adecuadamente mediante relaciones matemáticas,
mientras que, el MBD se utiliza para describir la dinámica restante. Los
gemelos digitales pueden identificarse de acuerdo con su capacidad de
utilización. Por ejemplo, podemos tener un GD independiente, que se crea
en base al conocimiento existente sobre la dinámica del sistema, no
tiene vínculo con el activo/proceso real en cuestión, es decir, pueden
construirse sobre la especificación propuesta del activo antes de su
realización. Es decir, puede utilizarse para un análisis preliminar de
coste-beneficio. Los gemelos digitales descriptivos utilizan datos
periódicos o en tiempo real de sensores para representar digitalmente el
estado actual y aspectos que no son evidentes a simple vista del activo,
lo que permite una toma de decisiones más informada. Un gemelo digital
de diagnóstico, permite proporcionar funciones como la detección de
fallos y cierto grado de apoyo en la toma de decisiones. La fidelidad de
un Gemelo Digital se logra con una integración más estrecha del flujo de
datos con los modelos matemáticos de estimación lineal o no lineales. El
gemelo digital predictivo, conserva todas las propiedades anteriores y
puede proyectar el estado del futuro para realizar mantenimientos
predictivos y la optimización de activos. El gemelo digital prescriptivo
incluye recomendaciones basadas en hipótesis para la evolución de
riesgos y la cuantificación de la incertidumbre a partir de los
resultados.

El gemelo digital autónomo, consiste en implementar la comunicación del
gemelo digital con el activo físico. Con respecto al medio ambiente, se
indica que las variaciones de los factores ambientales pueden impactar
en el comportamiento de los peces, donde los sensores más utilizados
relacionados a los factores ambientales tenemos: la temperatura, oxígeno
disuelto, salinidad y corriente de aguas. El crecimiento de los peces es
más fácil de cuantificar objetivamente que el comportamiento, y puede
evaluarse mediante muestreo manual (p. ej., comparando el peso de cada
pez en diferentes momentos) o mediante herramientas tecnológicas
diseñadas específicamente para estimar el tamaño de los peces. Esto ha
dado lugar a una base de datos y conocimientos para el desarrollo de
modelos de crecimiento de peces considerablemente más concisa y completa
que la utilizada para el desarrollo de modelos de comportamiento. A
partir de esta base, se ha demostrado que es posible desarrollar modelos
que describen cómo el crecimiento de los peces de cultivo se ve afectado
por los métodos de alimentación y las características ambientales como
la temperatura y el oxígeno disuelto (ajuste de curvas entre el peso y
edad de los peces).

Por otro lado, el modelo basado en datos (MBD) incluye biblioteca de
modelos de aprendizaje automático, abundancia de BIG DATA e
infraestructura computacional económica. Los modelos basados en datos en
el contexto de acuicultura pueden clasificarse en modelos lineales
supervisados y no supervisados. Los supervisados entrenan con datos
etiquetados, donde se conoce la variable objetivo, la regresión lineal y
logística son usados para tareas de predicción, clasificación y
selección de características. Un ejemplo de esto, es que una regresión
sea capaz de predecir el consumo de alimento de peces. Los modelos
lineales no supervisados, donde se desconoce la variable objetivo que
generalmente es usado para la extracción de características y agrupación
en clústeres.

*Los modelos no lineales supervisados* se entrenan con datos
etiquetados, son más flexibles que los modelos lineales como: árboles de
decisión, máquinas de vectores de soporte (MVS) y bosques aleatorios.
Con estos modelos, se pueden capturar relaciones complejas entre las
características y la variable objetivo. Como ejemplo, predecir la
resistencia a enfermedades.

Los modelos no lineales no supervisados, se entrenan con datos no
etiquetados que incluyen modelos como: los mapas autoorganizados (SOM) y
los K-vecinos más cercanos.

Por otro lado, tenemos los modelos de aprendizaje profundo supervisado
que se entrenan con datos etiquetados y arquitecturas complejas como
redes neuronales convolucionales (CNN) para el reconocimiento de
imágenes y redes neuronales recurrentes (RNN) para el procesamiento del
lenguaje natural y las redes neuronales profundas, totalmente conectadas
para tareas de regresión y clasificación. Por ejemplo, las redes
neuronales pueden ser usadas para *predecir la ingesta de alimento de la
trucha arcoíris en función de la temperatura del agua*, oxígeno
disuelto, peso promedio y número de peces, como también, el uso
Q-Learning para rastrear las trayectorias de crecimiento de los peces.

Los investigadores destacaron las condiciones de oxígeno en jaulas
marinas es importante, debido a que, si baja el nivel, puede causar
estrés y podría generar brotes de enfermedades y mortalidad, para ello
se debe garantizar suficiente oxígeno con ventilación activa, mayor
flujo volumétrico de agua que depende de la velocidad de la corriente de
agua, donde la concentración de oxígeno en el agua es menor que en el
aire y también es muy sensible a la temperatura del agua, por eso es
importante monitorear los parámetros del oxígeno disuelto y temperatura
del agua, debido a esto puede existir un mejor control del oxígeno
disuelto con un modelo matemático que muestra cómo el OD se propaga a
través del volumen de producción de una estructura de jaula rígida a
gran escala (Morten Omholt Alver et al., 2022). En una integración de
módulos de un GD es importante la conexión en tiempo real los sensores
con el modelo matemático. Para la integración se requiere una interfaz
para ingresar los datos en el modelo de las condiciones ambientales
como: temperatura del agua, corriente de agua y oxígeno disuelto.

La biomasa es el parámetro más importante para los piscicultores, ya que
les permite optimizar la gestión de las operaciones de la granja, como
la alimentación, y evaluar el valor futuro de la cosecha. La estimación
de la distribución por tallas de los peces también es crucial para la
evaluación del valor, ya que los peces no se venden a granel, sino por
tallas. La precisión de estas aplicaciones podría mejorarse aún más si
se pudiera cuantificar también el número de peces individuales en la
jaula.

Los investigadores (Morten O. Alver et al., 2016) describieron el modelo
de un sistema de *distribución de alimento* en base a las corrientes de
agua, la velocidad de hundimiento de los gránulos y la difusión
turbulenta, el apetito de los peces en función de la temperatura, la
saciedad y la estructura de la población. Por otro lado, Las empresas de
piscicultura y los productores de alimentos para peces realizan
rutinariamente ensayos y experimentos de alimentación para, por ejemplo,
explorar nuevos tipos de alimento, lo que da como resultados conjuntos
de datos que describen tanto el desarrollo del peso como los factores
determinantes de este proceso a lo largo del tiempo. Estos conjuntos de
datos suelen tener acceso restringido al público, ya que pueden contener
información que puede revelar los efectos. El conjunto de datos describe
la diferencia entre el crecimiento esperado (predicciones del modelo) y
crecimiento real (mediciones de crecimiento). Un gemelo digital que
describa el crecimiento de los peces en jaulas marinas podría, ante
todo, proporcionar al piscicultor una mejor visión general de las
propiedades de la biomasa y su desarrollo diario, información importante
para evaluar la eficiencia alimentaria y los efectos de las condiciones
ambientales, así como para planificar la futura comercialización de los
peces.

Los investigadores (Ubina et al., 2023) se centraron en el diseño de una
infraestructura de Gemelo Digital que soporta un sistema de Inteligencia
Artificial (IAoT) para la piscicultura inteligente en acuicultura. Esta
infraestructura incluye: el Internet de las Cosas, la tecnología en la
nube y la Inteligencia Artificial (IA). El objeto físico estuvo equipado
con sensores y actuadores, procesadores, máquinas de alimentación y de
clasificación de peces que recopilan y transmiten macrodatos a la nube
mediante redes de comunicación inalámbricas para la monitorización
remota y en tiempo real. El proyecto de investigación contó con 4
servicios: alimentación de peces para automatizar el proceso de
alimentación, estimación de métricas (conteo, tamaño y peso de peces),
monitorización ambiental (estado del agua, agujero de red y algas
verdes) y monitorización de la salud (vitalidad, mortalidad y
enfermedades).

*El servicio de Gemelo Digital*, fue capaz de realizar funciones como
optimización, predicción, análisis de datos para la toma de decisiones y
optimizar rentabilidad de la producción de peces. por otro lado,
integraron la entidad virtual mediante la WEB y dispositivos móviles, el
cual permite el monitoreo de la piscifactoría y en conjunto, con reglas
de decisión generada por los modelos de aprendizaje automático se
controló dispositivos con actuadores (máquina de alimentación de peces)
para que se descargue o no alimento, así como el monitoreo de la calidad
de agua.

En la figura 7, se muestra el entorno digital de la granja acuícola,
donde los datos sin procesar pasan por diferentes etapas, como:
recopilación, transmisión, almacenamiento, procesamiento, filtración,
análisis y visualización que se accede a través de las aplicaciones. La
estructura está basada en: *Data Source* (dispositivos IoT), *Data
Collection y Data Storage* (datos históricos y en tiempo real
recopilados), *Data Analytics* (capa de análisis de datos) y *Data
Application* (monitoreo de alimentación de peces, estimación de métricas
de peces, monitoreo ambiental y de la salud de los peces).

<img
src="Informe015_Gemelo_Digital_media/media/image8.png"
style="width:5.28125in;height:3.64377in" />

Figura 7. Gemelo digital del entorno de granja acuícola marina.

Los investigadores (Purcell et al., 2023) muestran e la figura 8, el
modelo virtual del GD para comprender y simular los efectos de los
cambios de estado en un producto, proceso o entorno.

<img
src="Informe015_Gemelo_Digital_media/media/image9.png"
style="width:4.49641in;height:2.53125in" />

Fig. 8. Visión general de la tecnología Digital Twin para la
acuicultura.

En este escenario los datos se almacenan y procesan mediante modelos de
aprendizaje automático y técnicas de aprendizaje profundo, representando
el entorno virtual o la entidad capaz de realizar operaciones de
monitoreo de la granja desde un sitio remoto, con esto se monitoreará el
comportamiento de los peces, estimará el crecimiento y monitoreará el
entorno acuícola, incluyendo evaluaciones de la calidad del agua, la
integración de dispositivos de hardware de bajo costo y el desarrollo de
herramientas de software para visualizaciones y resultados de análisis
de big data.

Por otro lado, en la figura 9, se muestra un gemelo digital propuesto
para la acuicultura inteligente con sus componentes básicos
correspondientes como recopilación de datos, computación en la nube y
servicios al usuario.

<img
src="Informe015_Gemelo_Digital_media/media/image10.png"
style="width:3.80625in;height:3.28884in" />

Fig. 9. Esquema conceptual de la arquitectura gemela digital propuesta
para un sistema de piscicultura inteligente.

También integramos sensores de agua para la temperatura, el nivel de pH,
la salinidad, la velocidad del agua y el oxígeno disuelto para el
monitoreo de la calidad del agua. Las máquinas inteligentes, como los
comederos inteligentes, están equipadas con actuadores que pueden
controlarse remotamente y funcionar en el mundo físico. El modelo de
alimentación de peces se ha entrenado mediante modelos de aprendizaje
profundo para evaluar la saciedad de los peces mientras se alimentan.
*El modelo de alimentación determinará el comportamiento de los peces*
durante la alimentación. Los dispositivos de inspección de la calidad
del agua (por ejemplo, sensores de temperatura) pueden utilizar el
protocolo MQTT para que los sensores de la cámara capturen información
vital y confirmen el evento anormal reportado por los dispositivos*. Los
servicios de computación en la nube* garantizan el almacenamiento de
datos, el análisis, las aplicaciones de IoT y los servicios de IA, que
forman parte de la entidad virtual. El análisis de big data proporciona
la digitalización o automatización del monitoreo y la gestión de las
explotaciones agrícolas, lo que conduce a un proceso inteligente y
autónomo que utiliza inteligencia artificial mediante la integración de
aprendizaje automático, minería de datos y metodologías de aprendizaje
profundo para procesar los datos sin procesar y transformarlos en
información significativa o valiosa que ayude a los agricultores a tomar
decisiones inteligentes. El resultado del servicio de análisis de big
data se utilizará para crear representaciones visuales de estos datos
procesados, como se muestra en la Fig. 10 para nuestra canalización de
análisis de big data, que refleja los diferentes procesos, desde la
recopilación de datos hasta los resultados (entregables y acciones) tras
el procesamiento y la transformación de los datos.

<img
src="Informe015_Gemelo_Digital_media/media/image11.png"
style="width:5.2375in;height:2.52938in" />

Figura 10. Microservicios Kubernetes para implementar y gestionar
servicios de datos, análisis de big data y toma de decisiones en la
nube.

El servicio al usuario o plataforma de integración comprende: la
aplicación nativa, la API web, las visualizaciones 3D y el panel de
control, proporcionando la interfaz del gemelo digital. Algunos de los
apoyos que se proporcionarán incluyen: la selección y cosecha oportuna
de peces según las necesidades de tamaño de mercado, la salud de los
peces y el manejo de enfermedades, el programa y la planificación de la
alimentación (cálculo de las raciones diarias de alimento), la
estimación de la longitud y el peso de los peces, y la siembra óptima de
peces según el tiempo y la producción.

El gemelo digital dedicado a la gestión de la alimentación de peces se
centra en: la gestión eficiente del alimento para optimizar el
crecimiento de los peces, reducir los costos de alimentación y eliminar
la contaminación del agua causada por el alimento no consumido. La
gestión de la alimentación de peces es una de las funcionalidades
centrales, más desafiantes y complejas de nuestro sistema AIoT. La
gestión de la alimentación de peces implica: *seleccionar un alimento*
adecuado para la especie, ofrecer *raciones pequeñas y frecuentes* (1-2
veces al día o más para juveniles) para evitar la sobrealimentación,
asegurar una dieta variada, y ajustar la cantidad según la talla,
temperatura y especie para optimizar la digestión y el crecimiento, a
menudo incluyendo un día de ayuno semanal para limpiar su sistema. En la
figura 11, se muestra el diagrama de transición de estados de gestión de
alimentación de peces.

<img
src="Informe015_Gemelo_Digital_media/media/image12.png"
style="width:5.01066in;height:3.58065in" />

Fig. 11. Diagrama de transición de estados de gestión de la alimentación
de peces.

Para alimentar con la máquina, los servicios de IA calculan primero
cuántos peces hay en una jaula específica mediante el método de
estimación de conteo de peces.

En segundo lugar, generan la métrica de los peces estimando el tamaño y
el peso de los peces, obteniendo el peso promedio correspondiente y
enviando el resultado a la nube. La necesidad diaria de alimento para
los peces se calcula inicialmente utilizando el número total de peces,
el peso promedio de los peces y la tasa de alimentación.

Una vez iniciada la alimentación, el sistema de alimentación inteligente
dispensa una *pequeña cantidad de alimento como cebo* para verificar la
ubicación de los peces. En tercer lugar, una vez que los peces comen el
alimento, la estimación de la ubicación determina su posición en la
jaula para estimar la mejor posición del cañón del comedero. A
continuación, se ajusta el cañón para garantizar que distribuya el
alimento directamente a los peces y así reducir el desperdicio.
Finalmente, se verifica la ubicación de los peces durante todo el tiempo
de alimentación para ajustar la posición del barril. También se verifica
la temperatura del agua antes de la alimentación, ya que esto afecta el
consumo de alimento de los peces. Si la temperatura es demasiado baja,
no Se realiza la alimentación. Por otro lado, una temperatura alta
aumenta el apetito de los peces, por lo que la tasa de alimentación
también aumentará para aprovechar este aumento, acelerándolos su
crecimiento o aumento de peso.

El estimador de alimento se encarga de estimar la alimentación de los
peces y envía comandos al controlador de alimentación del alimentador
inteligente sobre la cantidad de alimento a dispensar. La optimización
de la alimentación de los peces se encarga de: mejorar la ganancia de
peso de los peces considerando factores de crecimiento como la tasa de
alimentación y las condiciones de calidad del agua (temperatura y
salinidad).

Por otro lado, el análisis de alimentación de los peces se centra en
estimar los resultados de la alimentación, como la tasa de conversión
alimenticia, considerando la cantidad de alimento consumido en un
período determinado y el peso actual de los peces. Se evalúa
objetivamente el crecimiento de los peces en función de la cantidad de
alimento que se debe administrar o utiliza el peso objetivo de los peces
al final de los días de cultivo para predecir la cantidad de alimento
necesaria*. La estimación de métricas de peces consiste en aproximar el
tamaño de los peces y generar su peso*. Los sensores de cámara
instalados en la granja acuícola capturan vídeo y lo envían al sistema
de almacenamiento en la nube para realizar esta función. *Uno de los
componentes clave de este servicio es el análisis del crecimiento de los
peces,* que proporciona las etapas de crecimiento y la curva de
crecimiento de los peces en un período determinado. También puede
incluir la cantidad de alimento administrado durante estas etapas para
mostrar el estado real de crecimiento de los peces. En la figura 12, se
muestra una cámara en el dispositivo para capturar imágenes de los peces
y enviarlas a la nube para la estimación de las métricas. Los peces
listos para su dispersión y devolver los peces más pequeños a la jaula.

<img
src="Informe015_Gemelo_Digital_media/media/image13.png"
style="width:5.6129in;height:3.84864in" />

Fig. 12. Diagrama de transición de estados de estimación de métricas de
Fish.

Además, el monitoreo inteligente del entorno puede enviar disparadores y
alertas a los sensores para una mayor vigilancia y garantizar que el
entorno submarino se encuentre en óptimas condiciones. Además, envía
alertas al usuario en caso de daños en la red dentro de la jaula para
evitar que los peces escapen y prevenir el riesgo de pérdida. Integramos
modelos de aprendizaje profundo para detectar agujeros en la red y algas
verdes (Red Neuronal Convolucional de Segmentación Rápida). El flujo del
proceso se muestra en la figura 13.

<img
src="Informe015_Gemelo_Digital_media/media/image14.png"
style="width:4.62097in;height:3.27971in" />

Fig. 13. Diagrama de transición de estados de monitoreo del entorno.

La monitorización de la salud de los peces utiliza segmentos de vídeo
para la detección de peces. El sistema de gemelos digitales se
implementa en la arquitectura Kubernetes **(K8s),** que contiene la base
de datos, los servicios de gemelo digital, los objetos de gemelo digital
y las aplicaciones front-end y back-end que realizan análisis basados ​​en
IA y facilitan la toma de decisiones. En la figura 14, se muestra la
infraestructura de implementación del sistema de gemelo digital en la
nube con Docker y Kubernetes (K8s). MongoDB es nuestra plataforma de
base de datos y almacena los datos como un archivo JSON.

<img
src="Informe015_Gemelo_Digital_media/media/image15.png"
style="width:3.95968in;height:2.52933in" />

Fig. 14. Diagrama esquemático de la arquitectura del sistema en la nube.

se utilizó Mongoose para gestionar las relaciones de datos,
proporcionando validación y traducción de esquemas entre objetos y sus
representaciones en MongoDB. Para el back-end, Node.JS proporcionó la
interacción cliente-servidor para la comunicación y el intercambio de
datos. Se utilizó HTML, CSS y JavaScript/JQuery para implementar la
función front-end, específicamente el diseño de la interfaz visual de
gemelo digital. En la figura 15, se muestra cómo un componente
(representado por un proyecto de código) se convierte en un archivo de
imagen y se implementa en K8s.

<img
src="Informe015_Gemelo_Digital_media/media/image16.png"
style="width:4.87903in;height:1.87098in" />

Fig. 15. Diagrama de flujo de la interacción de Docker y Kubernetes.

En la Fig. 16 muestra el análisis de la vitalidad de los peces para
determinar su nivel de intensidad de alimentación.

<img
src="Informe015_Gemelo_Digital_media/media/image17.png"
style="width:4.99542in;height:3.18548in" />

Fig. 16. Análisis de la alimentación de los peces y resultados
prescriptivos.

\(a\) vitalidad de los peces. b) inventario de peces. c) registro de
alimentación.

La detección de peces es un requisito previo para realizar la estimación
del recuento de peces. En La estimación del recuento de peces también
puede utilizarse para la evaluación del inventario de la población de
peces en la jaula y, si se realiza regularmente, puede ayudar a
determinar la mortalidad de los peces. Los resultados de la detección de
peces se muestran en la Fig. 17, utilizando un sistema de cámara estéreo
que utiliza el ojo de pez para realizar la estimación del recuento de
peces.

<img
src="Informe015_Gemelo_Digital_media/media/image18.png"
style="width:5.90139in;height:1.47917in" />

Fig. 17. Resultado de la detección del conteo de peces utilizando ojos
de pez (a) imagen submarina (b) Etiqueta de recuento de ojos de pez real
(c) recuento de ojos de pez detectado.

A medida que los peces crecen, la jaula de red puede saturarse, lo que
impide a los piscicultores visualizar y determinar con precisión la
condición de los peces en el entorno submarino en todo momento. La
información sobre la densidad de peces del sensor de la cámara sonar
ayuda a los piscicultores a monitorear la población para evitar la
sobrepoblación y la posibilidad de una alta incidencia de transmisión de
enfermedades.

Una población de peces fuera de las densidades de población requeridas
también podría afectar: la calidad del agua, el crecimiento de los peces
y su nivel o tolerancia al estrés. Cuando se *distribuye el alimento en
la superficie del agua*, la mayoría de ellos nada cerca de ella.

Se espera que los peces se encuentren cerca de la superficie durante la
alimentación para capturar el alimento, aunque algunos se encuentran a
mayor profundidad.

Esta información proporciona una capacidad adicional de monitoreo
durante el tiempo de alimentación para identificar la actividad de los
peces. Mientras tanto, la estimación de la longitud y el peso de los
peces son servicios clave de este trabajo y son de suma importancia. El
tamaño de los peces es un parámetro crucial para evaluar las poblaciones
de peces, su crecimiento y la tasa de conversión alimenticia, para medir
la eficiencia de los mecanismos de alimentación de los piscicultores.

La Fig. 18 muestra la diversa información proporcionada por la cámara
estéreo sobre el ancho, la altura y el peso de los peces, utilizando
diferentes poblaciones de peces, desde piscifactorías de baja a alta
densidad. Los resultados estimados se calcularon en términos de valor
promedio.

<img
src="Informe015_Gemelo_Digital_media/media/image19.png"
style="width:6.01613in;height:1.17802in" />

Fig. 18. *Los resultados de la estimación de métricas de peces muestran
el número total de peces detectados, el ancho, la longitud y el peso
promedio estimados utilizando un sistema de cámara estéreo.*

La Fig. 19 muestra las diferentes interfaces para monitorear la
estimación de las métricas de los peces y los resultados para el
análisis de datos.

<img
src="Informe015_Gemelo_Digital_media/media/image20.png"
style="width:5.24494in;height:2.54032in" />

Fig. 19. Métricas de peces (a) monitoreo y (b) resultados de análisis de
datos.

Esta función permitirá a los acuicultores a saber si es necesario
trasladar algunos peces a otros estanques para evitar la sobrepoblación,
La tasa de crecimiento de los peces también puede derivarse del análisis
de crecimiento de los peces y una tasa de crecimiento negativa de los
peces refleja un crecimiento deficiente, y los piscicultores deben
realizar intervenciones rápidas e inmediatas para evitar mayores daños a
la salud y el estado general de los peces.

El diseño de la interfaz del sistema de la máquina clasificadora de
peces y los resultados del reconocimiento de imágenes se muestran en la
Fig. 20, donde se muestran: la longitud y la altura corporal, el peso,
la especificación de clasificación, el canal de clasificación, el número
total de peces acumulados y el peso total.

<img
src="Informe015_Gemelo_Digital_media/media/image21.jpeg"
style="width:4.73448in;height:3.24194in" />

Fig. 20. Resultados de la estimación métrica de peces no invasiva
utilizando la máquina contadora de peces.

La Fig. 21 muestra la interfaz de la aplicación para plataformas móviles
y web para la detección de la calidad del agua.

<img
src="Informe015_Gemelo_Digital_media/media/image22.png"
style="width:5.64572in;height:2.55645in" />

Fig. 21. Interfaz de monitoreo del estado de la calidad del agua y
análisis de datos.

La calidad del agua afecta considerablemente la condición física de los
peces. El sistema de monitoreo de calidad proporciona una evaluación y
monitoreo completos del estado actual del agua en la granja. Mediante un
modelo de aprendizaje profundo, se puede realizar predicciones de la
calidad del agua y generar resultados de predicción visualizados.

Puede realizar análisis de la calidad del agua actual y alertas y
notificaciones de alerta temprana en tiempo real como parte de su
capacidad de monitoreo. El intervalo de tiempo para obtener datos de los
sensores de agua en la granja acuícola se puede personalizar y ajustar
según la preferencia horaria de los acuicultores (por ejemplo, 30
minutos).

Con este parámetro, los datos de calidad del agua recopilados se pueden
visualizar para mostrar los puntos de tiempo y su valor correspondiente
durante la recolección, mostrando las tendencias de los datos de calidad
del agua en términos de estabilidad y fluctuación.

La alerta temprana detecta eventos anormales en el estado del agua,
basándose en valores óptimos y rangos razonables o aceptados, según
estudios adecuados para cada parámetro de calidad del agua. Por lo
tanto, la detección temprana **evitará la pérdida de vitalidad**,
posibles enfermedades o incluso la muerte masiva de peces causada por
las malas condiciones del agua en la piscifactoría.

En la Interfaz del gemelo digital de piscicultura los usuarios pueden
acceder a la interfaz del gemelo digital mediante sus ordenadores,
navegadores y dispositivos móviles. Además, se desarrolló una aplicación
móvil específica para dispositivos iOS que puede instalarse como
aplicación móvil para acceder al sistema de información. El usuario debe
verificar su identidad para acceder al sistema; esta funcionalidad se
puede ver en la Fig. 22 para la página web y las aplicaciones móviles.

<img
src="Informe015_Gemelo_Digital_media/media/image23.png"
style="width:4.2582in;height:2.69683in" />

Fig. 22. Interfaz de autenticación de usuario para la aplicación basada
en web (imagen izquierda) y la aplicación basada en móvil (imagen
derecha).

Una vez que el usuario proporcione correctamente sus datos de inicio de
sesión, será redirigido al panel de control (Fig. 23) del sistema de
información para acceder a diversas funciones, como *la calidad del
agua, el crecimiento de los peces y la información sobre la
alimentación.*

<img
src="Informe015_Gemelo_Digital_media/media/image24.png"
style="width:5.90139in;height:2.89722in" />

Fig. 23. Panel de monitoreo de acuicultura inteligente. (a) Información
básica. (b) análisis del crecimiento de los peces (c) Análisis de la
calidad del agua

El panel de control proporciona una interfaz visual para: supervisar la
piscifactoría y muestra informes y resultados del análisis de big data.
Los usuarios también pueden editar los valores o requisitos de los
parámetros según sus necesidades o preferencias. La información se
proporciona mediante visualizaciones de datos, como se muestra en las
figuras anteriores, como gráficos y tablas, que proporcionan información
útil, más fácil y cómoda de entender y brindan asistencia al mostrar
tendencias y resúmenes estadísticos de forma gráfica. Los resultados de
las visualizaciones se obtuvieron de los datos periódicos recopilados
por los sensores en las plantas de acuicultura, almacenados en la base
de datos en la nube. Estos datos se analizaron (por ejemplo,
correlaciones) y se compararon utilizando diferentes variables o
parámetros. Los usuarios de los acuicultores pueden observar los datos
en diferentes intervalos de tiempo. Las visualizaciones proporcionan una
interpretación más sencilla de los datos recopilados. El almacenamiento
en la nube también recopila y almacena continuamente datos para el
análisis de big data (Fig. 24).

<img
src="Informe015_Gemelo_Digital_media/media/image25.png"
style="width:5.61594in;height:2.63055in" />

Fig. 24. Datos de calidad del agua recopilados de sensores almacenados
en la base de datos en la nube con una alerta de color de texto.

El sistema de información también puede evaluar el estado actual de la
granja a través de su panel de control. Esta información proporciona a
los acuicultores una evaluación rápida de la idoneidad y eficacia de sus
métodos de cultivo actuales.

Les permite tomar decisiones y evaluaciones más inteligentes para
alcanzar los objetivos de sus piscifactorías. Si bien esta capacidad es
muy común y no representa una característica innovadora, incluir el
monitoreo de la calidad del agua ayudará a los piscicultores y
trabajadores a realizar monitoreo remoto y reducir la presencia de los
trabajadores en la piscifactoría. Los trabajadores pueden monitorear la
piscifactoría durante un mal funcionamiento, según el componente de un
gemelo digital.

Esto facilita el monitoreo de las piscifactorías por parte de
propietarios y trabajadores, y reduce las visitas frecuentes. Además, el
acceso remoto al estado actual de la piscifactoría y la integración de
modelos virtuales para simulación y análisis pueden ayudar a los
propietarios a reducir costos, ahorrar tiempo y optimizar las
condiciones ambientales, como la calidad del agua y la prevención de
enfermedades. De esta manera, se aumenta la eficiencia y se ayuda a
garantizar la sostenibilidad de las operaciones, lo que puede aumentar
la producción y las ganancias de la piscifactoría.

Si bien la integración de gemelos digitales en la piscicultura parece
prometedora y tiene un enorme potencial, la gestión y el mantenimiento
del sistema, las conexiones, la implementación de sensores y la
transformación de datos representan un desafío. La piscicultura en
acuicultura implica procesos amplios y complejos.

1.  **Logros.**

<!-- -->

1)  Se revisó algunas publicaciones referentes a la implementación de
    gemelos digitales en el área de acuicultura como “Gemelos digitales
    en la acuicultura intensiva: desafíos, oportunidades y perspectivas
    de futuro”, investigado por Føre, M., Alver, M. O., Alfredsen, J.
    A., Rasheed, A., Hukkelås, T., Bjelland, H. V., Su, B., Ohrem, S.
    J., Kelasidi, E., Norton, T., & Papandroulakis, N. Además, el
    trabajo “Gemelos digitales para la acuicultura terrestre: un estudio
    de caso para la trucha arcoíris (Oncorhynchus mykiss)”.

2)  La estructura básicamente de un Gemelo Digital está basada en: *Data
    Source* (dispositivos IoT), *Data Collection y Data Storage* (datos
    históricos y en tiempo real recopilados), *Data Analytics* (capa de
    análisis de datos) y *Data Application* (monitoreo de alimentación
    de peces, estimación de métricas de peces, monitoreo ambiental y de
    la salud de los peces).

    1.  **Resultados alcanzados.**

<!-- -->

1)  Se revisó la existencia de dos parámetros importantes como la
    temperatura del agua, oxígeno disuelto del agua, así como la dosis
    de alimentación y su relación con el crecimiento de peces.

**Referencias**

Alver, Morten O., Skøien, K. R., Føre, M., Aas, T. S., Oehme, M., &
Alfredsen, J. A. (2016). Modelling of surface and 3D pellet distribution
in Atlantic salmon (Salmo salar L.) cages. *Aquacultural Engineering*,
*72*–*73*, 20–29. https://doi.org/10.1016/j.aquaeng.2016.03.003

Alver, Morten Omholt, Føre, M., & Alfredsen, J. A. (2022). Predicting
oxygen levels in Atlantic salmon (Salmo salar) sea cages. *Aquaculture*,
*548* (November 2021). https://doi.org/10.1016/j.aquaculture.2021.737720

Føre, M., Alver, M. O., Alfredsen, J. A., Rasheed, A., Hukkelås, T.,
Bjelland, H. V., Su, B., Ohrem, S. J., Kelasidi, E., Norton, T., &
Papandroulakis, N. (2024). Digital Twins in intensive aquaculture —
Challenges, opportunities and future prospects. *Computers and
Electronics in Agriculture*, *218*(January), 108676.
https://doi.org/10.1016/j.compag.2024.108676

Føre, M., Frank, K., Norton, T., Svendsen, E., Arve, J., Dempster, T.,
Eguiraun, H., Watson, W., Stahl, A., Magne, L., Schellewald, C., Skøien,
K. R., Alver, M. O., & Berckmans, D. (2017). ScienceDirect Special
Issue : Engineering Advances in Precision Livestock Farming Review
Precision fish farming : A new framework to improve production in
aquaculture. *Biosystems Engineering*, *173*, 176–193.
https://doi.org/10.1016/j.biosystemseng.2017.10.014

Lima, A. C., Royer, E., Bolzonella, M., & Pastres, R. (2022). Digital
twins for land-based aquaculture: A case study for rainbow trout
(Oncorhynchus mykiss). *Open Research Europe*, *2*, 1–19.
https://doi.org/10.12688/openreseurope.14145.1

Purcell, W., Neubauer, T., & Mallinger, K. (2023). Digital Twins in
agriculture: challenges and opportunities for environmental
sustainability. *Current Opinion in Environmental Sustainability*, *61*,
101252. https://doi.org/10.1016/j.cosust.2022.101252

Ubina, N. A., Lan, H. Y., Cheng, S. C., Chang, C. C., Lin, S. S., Zhang,
K. X., Lu, H. Y., Cheng, C. Y., & Hsieh, Y. Z. (2023). Digital
twin-based intelligent fish farming with Artificial Intelligence
Internet of Things (AIoT). *Smart Agricultural Technology*, *5*(July),
100285. https://doi.org/10.1016/j.atech.2023.100285
