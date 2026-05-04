**INFORME DE ACTIVIDADES N°016-2026-REAJ**

1.  **Presentación de informe**

**Entidad Ejecutora :** UNIDAD EJECUTORA 002 - INICTEL-UNI

**Contrato :** N° PE501091609-2024-PROCIENCIA

**Proyecto de Investigación :** "Validación de una estación de monitoreo
de calidad de agua y dosificación de Floc bacteriano para crianza masiva
de peces en piscigranjas artificiales con geomembrana utilizando
aprendizaje automático e Internet de las Cosas"

**Responsable Técnico :** Ing. Rubén Acosta Jacinto

**Resolución Directoral :** N° 000047-2025-INICTEL-UNI/DE

**Periodo de Informe :** febrero 2026

| **DESCRIPCIÓN DE LAS ACTIVIDADES REALIZADAS**                                | **TOTAL**  |
|------------------------------------------------------------------------------|------------|
| \- Revisión de la estimación del oxígeno disuelto en el área de acuicultura. | S/. 700.00 |

-----------------------------------------------

Rubén Eusebio Acosta Jacinto

Investigador Principal

N°PE501091609-2024-PROCIENCIA

2.  **Avances**

**Revisión de la estimación del oxígeno disuelto en el área de
acuicultura.**

Sobre el escenario de Acuicultura de Precisión, (Royer et al., 2021)
explicaron la estimación del consumo de oxígeno de la trucha arcoíris en
una piscifactoría de canales, donde identificó un modelo dinámico que
simula la evolución de la concentración de oxígeno disuelto: la
oscilación diaria de la tasa de consumo de oxígeno de los peces se
simuló mediante una función sinusoidal. El modelo se aplicó al conjunto
de datos recopilados durante un estudio de campo de cuatro semanas,
realizado en julio de 2019. La temperatura del agua y la concentración
de oxígeno disuelto se midieron cada hora en el afluente y el efluente
de la piscifactoría. Se estimaron tres parámetros del modelo: la tasa de
respiración diaria promedio, la amplitud de su oscilación diaria y su
fase, ajustando la salida del modelo a la serie temporal de la
concentración de oxígeno disuelto en el efluente. Para la implementación
de la investigación se tuvo que crear un sistema de oxigenación basado
en un oxigeno líquido que se almacena en un tanque que abastece cada
canal de cultivo de forma independiente mediante una red de
distribución. El oxígeno se gasifica y luego se disuelve en agua a
presión atmosférica utilizando un sistema de oxigenación de baja presión
(LHO) diseñado y fabricado por el propio agricultor. El suministro de
oxígeno a cada canal se realiza mediante una válvula manual controlada
por el agricultor y ajustada a un valor nominal. El LHO se caracteriza
por una eficiencia de transferencia de oxígeno (OTE) del 90 %. Durante
la prueba del sistema de acuicultura de precisión, no se activó ningún
procedimiento de emergencia para el canal 6, y el caudal de suministro
de oxígeno puro, LO2, se mantuvo en su valor nominal Tabla 1.

Tabla 1: Parámetros y expresiones funcionales:

<img
src="Informe016_Oxigeno_Disuelto_media/media/image1.png"
style="width:4.30252in;height:4.08954in" />

La biomasa de los peces se monitorizó diariamente combinando los datos
proporcionados por un sistema de última generación para la estimación no
invasiva de la distribución del peso de los peces con el conteo de
mortalidad. El período de monitorización se dividió en dos intervalos de
tiempo, ya que los peces no fueron alimentados durante las dos primeras
semanas. Estos intervalos se dividieron a su vez en un conjunto de
calibración y otro de validación. Los resultados de la calibración
muestran que:

- la tasa de consumo de oxígeno diaria promedio coincide con la
  bibliografía;

- la amplitud de la oscilación diaria, cuando los peces se alimentan
  regularmente, es más del doble de la estimada para peces en ayunas.

Los resultados de la validación sugieren que el modelo podría utilizarse
para implementar un control automático y rentable del suministro de
oxígeno, basado en la predicción a corto plazo de la demanda de oxígeno.
En general, la dinámica del oxígeno disuelto (OD) en el agua de río
depende de la advección y de tres procesos locales: la producción
fotosintética, la respiración del ecosistema y el intercambio de oxígeno
con la atmósfera. Para simular la dinámica del OD dentro de un canal de
cultivo, se hicieron las siguientes suposiciones:

- En esta aplicación preliminar del Acuicultura de Precisión, se aplicó
  un modelo dinámico de OD "0D", asumiendo implícitamente que el agua
  del canal está bien mezclada: en este caso, la representación
  matemática de la dinámica del OD es una ecuación diferencial ordinaria
  (EDO);

- No se tuvo en cuenta la actividad fotosintética dentro del canal;

- El término de consumo de oxígeno incluyó únicamente la respiración
  debida a los peces de cultivo;

- Se tuvo en cuenta el intercambio con la atmósfera.

Tabla 2: Modelo dinámico de Oxígeno Disuelto con respecto a la ecuación
de balance de masas.

<img
src="Informe016_Oxigeno_Disuelto_media/media/image2.png"
style="width:3.41177in;height:3.73298in" />

La ecuación del modelo resultante se presenta en la Tabla 2, donde el
primer término representa la entrada y salida de OD en relación con el
caudal volumétrico (Q); El segundo es el caudal de suministro de
oxígeno, S, que puede ser controlado por la granja; el tercer término es
el intercambio de oxígeno con la atmósfera; y el cuarto es el consumo de
oxígeno debido a la respiración de los peces (MR/V). El caso de estudio
fue un sistema de Acuicultura de Precisión aplicado a una piscifactoría
de truchas en canales ubicada en Trentino-Alto Adige, en el norte de
Italia. La ​​piscifactoría consta de siete canales de cultivo de 200 m de
largo, 8 m de ancho y 0,8 m de profundidad, cubiertos con redes de
protección para evitar la depredación por aves y equipados con sistemas
de suministro de oxígeno. La calidad del agua de entrada varía con el
tiempo, ya que se extrae del río Sarca (Fig. 1).

<img
src="Informe016_Oxigeno_Disuelto_media/media/image3.png"
style="width:5.17647in;height:2.75063in" />

Figura 1. Vista general de los *canales de cultivo de truchas* y del
sistema de Acuicultura de Precisión.

En la estimación del consumo de oxígeno de acuerdo con la terminología
de Acuicultura de precisión, una "variable característica" puede
estimarse a partir de variables animales medidas, y una "variable
objetivo", derivada de las variables características, puede utilizarse
en la toma de decisiones.

En este contexto, R es una variable característica no observable, que
puede estimarse ajustando la salida del modelo a un conjunto de
observaciones. La concentración de oxígeno disuelto (OD) x, se consideró
una "variable objetivo", ya que su nivel puede controlarse ajustando el
suministro de oxígeno, en función de los valores predichos de R, para
mantener el OD en el nivel deseado. R se estimó minimizando el error
cuadrático medio (RMSE), ecuación (1):

<img
src="Informe016_Oxigeno_Disuelto_media/media/image4.png"
style="width:1.39815in;height:0.61419in" />……………..(1)

Donde n es el número de observaciones, y<sub>i</sub> es la concentración
de OD en el efluente en el tiempo t<sub>i</sub>, y ̂y<sub>i</sub> es la
concentración de OD en el tiempo t<sub>i</sub> estimada por el modelo.

El "parámetro metabólico" R depende de varios factores, como la
temperatura del agua, el patrón de respiración circadiana y el patrón de
alimentación diario.

Los ritmos circadianos de alimentación y actividad locomotora han sido
ampliamente descritos.

Diversos estudios demostraron que el metabolismo y la actividad de la
trucha presentan un patrón diario como consecuencia de la combinación de
dos sincronizadores (fenómenos naturales rítmicos que actúan como
señales en la regulación de los ritmos circadianos del organismo): el
Oscilador de Sincronización con la Luz (OSL), en gran medida, y el
Oscilador de Sincronización con la Alimentación (OSA), en menor medida.
Se destacó un patrón sinusoidal en la respuesta metabólica de las
truchas a diferentes horarios de alimentación. Por lo tanto, la
fluctuación diaria del consumo de oxígeno se simuló mediante una función
sinusoidal y el efecto de la temperatura del agua sobre R se modeló
mediante una función exponencial. En este estudio se estimaron la tasa
media diaria, Rm, la amplitud de la oscilación A y la fase, ϕ (véase la
Tabla 2), minimizando la función objetivo (Ec. 1).

El rendimiento del modelo se evaluó mediante una metodología de bondad
de ajuste (GoF) bien establecida, es decir, la regresión entre
observaciones y predicciones. El modelo y el procedimiento de estimación
de parámetros se programaron utilizando el software R (versión 3.4.0),
dentro de R Studio (versión 1.0.143). La ecuación diferencial se
resolvió utilizando el paquete deSolve de R (versión 1.21). Las
concentraciones de oxígeno disuelto (OD) medidas en el efluente al
inicio del período se tomaron como valores iniciales para resolver la
ecuación del modelo. La estimación de los parámetros necesarios como
series temporales de entrada: concentración de oxígeno disuelto (OD) en
el efluente, xout, temperatura del agua, Tw, caudal de oxígeno, S y
biomasa de peces, M. La estrategia de monitorización para la recolección
de estos datos se describe detalladamente a continuación. El sistema de
monitorización (Fig. 1) se instaló en el canal 6: el caudal de entrada
fue de 0,44 m³/s, lo que da un tiempo de residencia de 48 min, es decir,
0,8 h. Uno de los objetivos del proyecto H2020 GAIN - Intensificación de
la Acuicultura Verde en Europa es probar métodos no invasivos para el
monitoreo de variables animales y desarrollar nuevos enfoques de
modelado para la implementación de acuicultura en una variedad de
tipologías de acuicultura, incluyendo canales de trucha arcoíris. La
distribución del peso de los peces se monitoreó en tiempo real (Fig. 1)
utilizando Biomass Daily (BD), producido por Vaki y comercializado en
Italia por Aquatrade L.t.d. El sistema se utiliza para estimar la
distribución del peso en jaulas de salmón del Atlántico, pero, hasta
donde sabemos, no se ha aplicado previamente a la trucha arcoíris en una
granja de canales.

El sistema Biomass Daily consta de un marco sumergido de 80 × 80 cm
conectado a una caja de envío. Una conexión inalámbrica permite
transferir datos a un ordenador remoto.

El sensor, basado en tecnología infrarroja, detecta una señal cuando un
ejemplar cruza el marco. Las señales se procesan en tiempo real y los
pesos individuales estimados se muestran en un panel de control.

Las estadísticas diarias se pueden consultar fácilmente para su
posterior análisis. Todos estos datos son accesibles de forma remota a
través de una interfaz web. Aunque el sistema requiere cierto
mantenimiento, como la limpieza semanal, no supone un esfuerzo adicional
significativo para los operadores. El panel de control es fácil de usar
y los datos se pueden consultar fácilmente para su posterior
procesamiento. El sistema BD también podría utilizarse para la
monitorización no invasiva de toda una granja, moviendo el marco de un
canal a otro: las lagunas de datos podrían cubrirse mediante
interpolación o modelización. En este estudio, el marco se mantuvo en el
canal 6 durante tres meses y las observaciones se compararon con el
muestreo mensual directo de 30 individuos.

La temperatura del agua (Tw) y la concentración de oxígeno disuelto (OD)
se monitorizaron cada hora en el afluente y el efluente (Fig. 1)
mediante dos sensores automáticos multiparamétricos EXO2 idénticos,
comercializados por YSI. Las sondas se colocaron a 70 cm por debajo de
la superficie del agua. Las mediciones de OD se realizaron mediante un
sensor óptico con una precisión de 0,1 mg L⁻¹ dentro del rango de
valores observados.

Las mediciones de temperatura se obtuvieron mediante un termómetro de
resistencia clásico, con una precisión de 0,01 °C. Los sensores incluyen
registradores de datos y pueden conectarse a una plataforma en la nube
para visualizar y procesar los datos en tiempo real.

Las series temporales se desestacionalizaron utilizando la función
‘detrend()’ del software R y, posteriormente, se aplicó un análisis de
Fourier con la función ‘fft()’ del software R. La densidad espectral
asociada a un periodo de 24 horas se cuantificó como una fracción de la
densidad espectral total.

Las series temporales de temperatura del agua y oxígeno disuelto (OD)
medidas en el afluente y el efluente se muestran en las figuras 2a y 2b,
y sus diferencias en las figuras 2c y 2d. Las estadísticas descriptivas,
es decir, el rango, la media, la mediana, la desviación estándar y el
rango intercuartil, se presentan en la tabla 3. Como se puede observar
en las figuras 2a y 2b, ambas variables presentaron un patrón diario
claro, impulsado por los procesos de producción primaria/respiración e
intercambio de calor que ocurren en el río Sarca. La temperatura del
agua osciló aproximadamente entre 11,5 °C y 20,5 °C, y las diferencias
fueron ligeramente diferentes

<img
src="Informe016_Oxigeno_Disuelto_media/media/image5.png"
style="width:3.79343in;height:1.78646in" />

<img
src="Informe016_Oxigeno_Disuelto_media/media/image6.png"
style="width:3.75587in;height:1.79146in" />

Figura 2. Series temporales de la concentración de oxígeno disuelto (a)
y la temperatura del agua (b) en el afluente y el efluente y sus
diferencias (c y d).

positivo, probablemente debido a la disipación de la energía de la
radiación solar en calor dentro del canal de cultivo. Los datos de OD,
Fig. 2a, se caracterizaron por un patrón menos regular, que parece estar
afectado por el régimen de alimentación. En general, el OD en el
efluente fue mayor que en el afluente, véase la Fig. 2c, ya que el
oxígeno se suministró continuamente durante el mes de julio: esto
sugiere que el sistema de control de OD actualmente en funcionamiento
podría mejorarse notablemente. También se observa un patrón diario en
las diferencias de Tw y OD, véase la Fig. 2c-d. En particular, las
oscilaciones diarias de OD fueron menores y más regulares durante la
subventana FAST, pero aumentaron y se caracterizaron por un mayor ruido
durante las dos últimas semanas de julio, cuando los peces se
alimentaron de acuerdo con las tablas de alimentación. La presencia de
un patrón diario se confirma con los resultados del análisis de Fourier,
resumidos

en la tercera columna de la Tabla 3, que muestra el porcentaje de la
densidad espectral asociada a un período diario. El análisis de Fourier
confirma que las diferencias en el oxígeno disuelto se caracterizaron
por un componente diario significativo, que representó el 42 % de la
densidad espectral total.

Tabla 3. Estadísticas descriptivas de las variables ambientales.

<img
src="Informe016_Oxigeno_Disuelto_media/media/image7.png"
style="width:2.73709in;height:1.11034in" />

La tasa de consumo de oxígeno, R, se estimó para las ventanas temporales
FAST y FED, con el fin de detectar cambios debidos a la alimentación. El
valor diario promedio, Rm, se estimó únicamente en la subventana FAST,
en la que los peces no fueron alimentados o fueron subalimentados, ya
que no se puede identificar ninguna tendencia diferenciada en la figura
2c. Los otros dos parámetros se calibraron en ambas ventanas, ya que,
según la bibliografía, el patrón diario de consumo de oxígeno depende
tanto de LEO como de FEO. Para probar la capacidad predictiva del
modelo, los conjuntos de datos FAST y FED se dividieron en dos
subconjuntos: el primero se utilizó para estimar los parámetros y el
segundo para validar las estimaciones. Los resultados del modelo se
comparan con las series temporales de observaciones de OD recopiladas en
cada ventana temporal en las figuras a-d. Una comparación visual muestra
que el modelo logra simular el patrón diario de la dinámica del oxígeno
disuelto (OD) observado en la ventana FAST, aunque subestima los datos
en la subventana de validación. Además, el rendimiento del modelo parece
aceptable también en los primeros cinco días de la subventana de
calibración FED. Por otro lado, el modelo no parece capturar las
características principales de la dinámica del OD observadas en la
ventana de validación FED.

<img
src="Informe016_Oxigeno_Disuelto_media/media/image8.png"
style="width:3.1831in;height:2.97662in" />

Figura 3. Comparación entre la evolución simulada y observada del
oxígeno disuelto (OD) en relación con: a, b) la calibración y validación
del modelo en la ventana temporal FAST; c, d) la calibración y
validación del modelo en la ventana temporal FED.

Los investigadores (Khater et al., 2021) indicaron El oxígeno disuelto
(OD) es un parámetro crucial para determinar la calidad del agua en la
acuicultura, ya que los niveles bajos de OD afectan la palatabilidad del
alimento, lo que reduce la ingesta y, por consiguiente, el crecimiento.
Un bajo nivel de OD en los estanques se relaciona con la presencia de
dióxido de carbono (CO₂) y amoníaco no ionizado (NH₃), sustancias
tóxicas para los peces. Las concentraciones de OD inferiores a 5 mg L⁻¹
afectan gravemente el crecimiento. Los peces no pueden sobrevivir con 2
mg L⁻¹ de oxígeno disuelto.

Un sistema de recirculación de agua (RAS) se define como un sistema
acuícola que reutiliza el 10 % del agua después del tratamiento. El
concepto de RAS consiste en reutilizar un volumen de agua mediante un
tratamiento continuo y su suministro a los organismos cultivados. Para
tratar el agua en un RAS, se requiere un sistema capaz de manejar
grandes volúmenes de agua para producir mayores cantidades de pescado de
forma rentable. Generalmente, este sistema requiere diferentes tipos de
filtros, bombas y tanques para mejorar la calidad del agua, lo que a su
vez controla las enfermedades y garantiza una mayor producción. En los
sistemas de recirculación acuícola (RAS), la aireación es fundamental
para controlar el oxígeno disuelto (OD), ya sea mediante la adición de
oxígeno puro o aire mezclado con alto contenido de oxígeno. *Controlar
el oxígeno disuelto mediante la aireación es crucial en sistemas con
alta capacidad de carga de peces como la tilapia* o el bagre. Sin
embargo, los sistemas comerciales de recirculación acuícola deben contar
con un aireador en lugar de utilizar oxígeno líquido, ya que la
aireación del agua con bajo contenido de oxígeno disuelto hasta el punto
de saturación, mientras que el uso de oxígeno líquido podría provocar
sobresaturación. Uno de los factores limitantes en los sistemas de
recirculación acuícola es la concentración de oxígeno en el agua, ya que
este se disuelve con dificultad. Los valores de saturación para el
crecimiento de especies de agua fría son de 10,08 mg L⁻¹ a 15 °C y de
8,26 mg L⁻¹ a 25 °C. Para el cultivo en aguas cálidas, es necesario
reponer constantemente el oxígeno en el agua para asegurar un
crecimiento eficiente de los peces. El umbral de concentración de
oxígeno para especies de aguas cálidas es del 50 % (valor absoluto de
4,13 mg L⁻¹ a 25 °C) y del 60 % (6,48 mg L⁻¹ a 15 °C) para salmónidos en
el efluente de un tanque de cultivo. El parámetro más crítico de la
calidad del agua es el nivel de oxígeno disuelto (OD) disponible para
los organismos en un sistema de acuicultura, ya que es esencial para el
metabolismo de la mayoría de los peces y crustáceos cultivados. Las
tasas de consumo de oxígeno de los peces dependen de varios factores,
entre ellos: el nivel de actividad ambiental, la concentración de OD, la
temperatura del agua, el tamaño de los peces y el tiempo transcurrido
desde la alimentación. La disminución de los niveles de oxígeno provoca
efectos letales y subletales, entre los que se incluyen: reducción de la
tasa de alimentación y crecimiento, menor eficiencia en la conversión de
alimentos y mayor susceptibilidad a las enfermedades en diversos
organismos acuáticos.

Muchos investigadores han estudiado la simulación de la transferencia de
masa de oxígeno. Encontraron una buena concordancia entre la simulación
y los resultados experimentales. Concluyeron que el nivel de oxígeno
disuelto (OD) en equilibrio disminuía con el aumento de la temperatura y
que la eficiencia de transferencia de oxígeno es mayor para valores
menores de caudal de gas. También encontraron que el sistema de
aireación en acuicultura provocaba una disminución del nivel de OD en
equilibrio debido al consumo de oxígeno por parte de los peces.

En este modelo, el oxígeno disuelto presentaba diversas interacciones a
considerar. El consumo de oxígeno se produce mediante los procesos de
respiración y nitrificación. Por otro lado, el agua recibe oxígeno a
través de la agitación durante su bombeo por el sistema y del generador
de oxígeno. El generador de oxígeno y la aireación por flujo añaden
oxígeno al agua (Fig. 4).

La suplementación de oxígeno requerida es la suma de los componentes
anteriores, como se indica a continuación:

DO<sub>FR</sub> +DO<sub>B</sub> +DO<sub>N</sub> = DO<sub>sup</sub>
+DO<sub>PF</sub>………..(1)

<img
src="Informe016_Oxigeno_Disuelto_media/media/image9.png"
style="width:2.73709in;height:1.88009in" />

Figura 4. Modelo de oxígeno disuelto.

Donde DOFR es el consumo de oxígeno disuelto a través de la respiración
de los peces, g O<sub>2</sub> m<sup>−3</sup> h<sup>−1</sup>. DOB es el
consumo de oxígeno disuelto a través del biofiltro, g O<sub>2</sub>
m<sup>−3</sup> h<sup>−1</sup>. DON es el consumo de oxígeno disuelto a
través de la nitrificación, g O<sub>2</sub> m<sup>−3</sup>
h<sup>−1</sup>. DOPF es la adición de oxígeno disuelto a través del
flujo de la tubería, g O<sub>2</sub> m<sup>−3</sup> h<sup>−1</sup>.
DOsup es el aporte de oxígeno suplementario requerido (generador de
oxígeno), g O<sub>2</sub> m<sup>−3</sup> h<sup>−1</sup>. La tasa de
cambio en la concentración de OD en el tanque de peces:

$\frac{dDO}{dt} = {DO}_{FR} + {DO}_{B} + {DO}_{N} - {DO}_{PF}$ ………………(2)

Donde dDO/dt es la tasa de cambio de la concentración de OD durante el
intervalo de tiempo, g O2 m<sup>−3</sup> h<sup>−1</sup>. dt es la tasa
de cambio de dt en el intervalo de tiempo, h. Después de calcular la
concentración de oxígeno para cada elemento en cada paso de tiempo, el
cambio neto de oxígeno se suma o se resta a la concentración de oxígeno
del paso de tiempo anterior. Las concentraciones de OD se pueden
calcular en cualquier momento (t) como:

${DO}_{t} = {DO}_{t - 1} + \left( \frac{dDO}{dt}.\ dt \right)$……………….(3)

donde DO<sub>t</sub> es la concentración de oxígeno disuelto (g m⁻³) en
el tiempo t. DO<sub>t-1</sub> es la concentración de oxígeno disuelto (g
m⁻³) en el tiempo t-1. La tasa de consumo de oxígeno por la respiración
de los peces se puede calcular a partir de la temperatura del agua y el
peso promedio de los peces. Este cálculo se muestra en la siguiente
ecuación.

FR = 2014.45 + 2.75W − 165.2T + 0.007W<sup>2</sup> + 3.93T<sup>2</sup> −
0.21WT……..(4)

${DO}_{FR} = \frac{FR\ x\ SD}{1000}$………….(5)

Donde

- FR es la tasa de consumo de oxígeno por respiración de los peces, mg
  O₂ kg⁻¹ pez h⁻¹.

- W es la masa promedio de cada pez, g.

- T es la temperatura del agua, °C.

- SD es la densidad de siembra de peces, kg m⁻³.

- El coeficiente de correlación de la ecuación fue de 0,99.

Los datos utilizados para elaborar la ecuación abarcaron un rango de 20
a 200 g de peso de los peces y de 24 a 32 °C.

La tasa de consumo de oxígeno por nitrificación se calcula en función
del Nitrógeno Amoniacal Total (TAN), que se convierte de amoníaco a
nitrato.

La tasa encontrada en la literatura es de 4,57 g O₂ g⁻¹ TAN⁶. El consumo
de oxígeno en el proceso de nitrificación se puede calcular como:

DO<sub>N</sub> = 4.57× K<sub>NR</sub> × Nr/V…………(6)

K<sub>NR</sub> = 0.1(1.08)<sup>(T−20)</sup>……………….(7)

$N_{r} = \frac{0.03\ x\ F_{r}xWxN_{f}}{24\ x\ 1000}$……………..(8)

Donde:

- K<sub>NR</sub> es el coeficiente de nitrificación.

- Nr es la tasa de nitrificación, g TAN h⁻¹.

- Fr es la tasa de alimentación, % del peso corporal de los peces día⁻¹.

- N<sub>F</sub> es el número de peces.

- V es el volumen de agua, m³.

La tasa de alimentación se puede calcular mediante la siguiente
ecuación:

$F_{r} = 17.02\ x\ e^{\left\lbrack \frac{\left( \ln{W + 1.14} \right)^{2}}{- 19.52} \right\rbrack}$…………..(9)

Las bacterias del biofiltro constituyen una segunda fuente de consumo de
oxígeno. Lawson explica que la demanda de oxígeno del biofiltro es
aproximadamente 2,3 veces la DBO tasa de producción de los peces. El
consumo de oxígeno del biofiltro se calcula mediante la siguiente
ecuación:

${DO}_{B} = \frac{(2.3)\left( {BOD}_{5} \right)\left( W_{n} \right)}{(V)(24)(1000)}$………………(10)

Donde

- DBO<sub>5</sub> es la tasa promedio de excreción de DBO<sub>5</sub>
  sin filtrar, 2160 mg O<sub>2</sub> kg<sup>− 1</sup> pez
  día<sup>−1</sup>.

- W<sub>n</sub> es la biomasa, kg de pez.

- El ciclo de bombeo de agua fue una fuente de oxígeno añadido al
  sistema.

- La cantidad de oxígeno añadido a través del ciclo de bombeo de agua se
  calculó cada hora.

- El método para calcular la aireación de una tubería se detalla en la
  referencia.

${DO}_{PF} = \frac{PC\ x\ fx\ \ Ex\ OTR}{V}$……………..(11)

Donde

- PC es la duración del ciclo de bombeo (h),

- f es la frecuencia de bombeo (h⁻¹),

- E es la eficiencia (%).

- OTR es la tasa de transferencia de oxígeno (g O₂h<sup>⁻¹</sup>).

Este modelo suma DO<sub>FR</sub>, DO<sub>B</sub>, DO<sub>N</sub> y
DO<sub>PF</sub> para determinar la demanda suplementaria de oxígeno
disuelto (kg h⁻¹).

Este valor puede utilizarse para estimar el consumo de oxígeno si se
emplea un sistema de transferencia de oxígeno puro.

El crecimiento de los peces se ve afectado por factores ambientales y
físicos, como la temperatura del agua, el oxígeno disuelto, el amoníaco
no ionizado, el fotoperiodo, la densidad de población, la disponibilidad
de alimento y la calidad del alimento.

Para calcular la tasa de crecimiento (g día⁻¹) de cada pez, se utilizó
el siguiente modelo, ya que incluye los principales factores ambientales
que influyen en el crecimiento de los peces: la temperatura, el oxígeno
disuelto y el amoníaco no ionizado (Yi, 1998).

$FGR = \left( 0.2919\tau\kappa\delta\varphi hfW^{m} \right) - k.W^{n}$………….(12)

Donde FGR es la tasa de crecimiento de los peces, g día<sup>− 1</sup>

- τ es el factor de temperatura (0 \> τ \< 1, adimensional).

- k es el factor de fotoperiodo (0 \> k \< 1, adimensional).

- δ es el factor de oxígeno disuelto (0 \> δ \< 1, adimensional)

- φ es el factor de amoníaco no ionizado (0 \> φ \< 1, adimensional).

- h es el coeficiente de consumo de alimentos (g/m³ día⁻¹)

- ƒ es el nivel de alimentación relativo (0 \> ƒ \< 1, adimensional)

- K es el coeficiente de catabolismo. h, m, n son constantes.

La temperatura del agua afecta la ingesta de alimento. Caulton describió
la relación entre la temperatura y la ingesta de alimento en las
tilapias. La tasa de ingesta de alimentos alcanza su valor máximo cuando
la temperatura se encuentra dentro de un rango óptimo. Si la temperatura
está fuera del rango óptimo, la tasa de ingesta de alimentos disminuye.
La ingesta de alimentos se detiene cuando la temperatura alcanza el
rango límite. El factor de temperatura (de 0 a 1) se puede describir
como:

$\tau = EXP\left\{ - 4.6\left\lbrack \frac{T_{opti} - T}{T_{opti} - T_{\max}} \right\rbrack^{4} \right\}\ if\ \ T < T_{opti}$…………..(13)

$\tau = EXP\left\{ - 4.6\left\lbrack \frac{T - T_{opti}}{T_{\max} - T_{opti}} \right\rbrack^{4} \right\}\ if\ \ T \geq T_{opti}$…………..(14)

Donde T<sub>min</sub> es la temperatura por debajo de la cual los peces
dejan de comer (°C). T<sub>max</sub> es la temperatura por encima de la
cual los peces dejan de comer (°C). T<sub>opti</sub> es la temperatura
óptima para que los peces se alimenten (°C).

El término catabolismo también se ve afectado por la temperatura. El
efecto se describe como:

K = K<sub>min</sub> exp\[s(T − T<sub>min</sub>)\]……………(15)

Donde:

- K<sub>min</sub> es el coeficiente de catabolismo en ayunas a
  T<sub>min</sub>, g<sup>1−n</sup> h<sup>−1</sup>. s es una constante.

- El efecto del OD en el crecimiento de los peces se describe en tres
  etapas.

- Cuando el OD está por debajo del nivel límite mínimo,
  DO<sub>min</sub>, la alimentación de los peces se detiene.

- Cuando el OD está por encima de un nivel crítico, DO<sub>crit</sub>,
  el OD no tiene efecto sobre la alimentación.

- Cuando el OD está entre DO<sub>min</sub> y DOc<sub>rit</sub>, la
  alimentación se ve afectada por el OD.

> $\delta = 1.0\ \ \ if\ DO\  > {DO}_{crit}$…………(16)

$\delta = \frac{DO - {DO}_{\min}}{{DO}_{crit} - {DO}_{\min}}\ \ \ \ if\ \ \ {DO}_{\min} \leq DO \leq {DO}_{crit}$…………….(17)

$$\delta = 0.0\ \ \ if\ DO < {DO}_{crit}$$

Todos los cálculos del modelo se realizaron utilizando una hoja de
cálculo de Excel. El programa informático se diseñó para realizar un
balance de masas con el fin de predecir el oxígeno disuelto consumido en
el sistema de recirculación acuícola. La Figura 5 muestra el diagrama de
flujo del modelo. Los parámetros utilizados en el modelo, obtenidos de
la bibliografía, se enumeran en la Tabla 1.

<img
src="Informe016_Oxigeno_Disuelto_media/media/image10.png"
style="width:3.3913in;height:2.61888in" />

Figura 5. Diagrama de flujo del modelo

Tabla 1: Los parámetros utilizados en el balance de masas

<img
src="Informe016_Oxigeno_Disuelto_media/media/image11.png"
style="width:2.06087in;height:2.73761in" />

La programación del ***modelo predictivo de oxígeno disuelto**,* fue
implementado por (Ragab et al., 2022) utilizando Python 3.8.6, se
instalaron y utilizaron los paquetes Matplotlib (v. 3.0.3), Numpy (v.
1.16.2), Tkinter (v. 8.6) y Math (v. 1.2) y usaron el IDE Anaconda para
facilitar el uso de Python. En la figura 6, se muestra el diagrama de
flujo del modelo.

<img
src="Informe016_Oxigeno_Disuelto_media/media/image12.png"
style="width:4.6in;height:3.48674in" />

Figura 6. Diagrama de flujo del modelo predictivo de oxígeno disuelto.

En la figura 7, se muestra el diagrama de flujo del modelo de amoníaco.

<img
src="Informe016_Oxigeno_Disuelto_media/media/image13.png"
style="width:4.53913in;height:3.1019in" />

Figura 7. Diagrama de flujo del modelo predictivo de amoníaco.

Este modelo se distingue de otros modelos mencionados en estudios
anteriores por su facilidad de uso. El modelo se presenta al usuario
como un programa GUI independiente y no requiere la instalación de
ningún otro programa. Otra característica del programa es la ventana de
resultados, que presenta relaciones que ayudan al diseño y la operación.

El modelo combina el consumo de oxígeno disuelto, la producción de
amoníaco y el peso promedio de los peces, prediciendo cuáles son los
parámetros más efectivos con respecto a la productividad del RAS y la
calidad del agua (Sri-uam et al., 2016).

El modelo mostró que el **consumo de oxígeno esperado** disminuyó con el
aumento del peso promedio de los peces **durante el mismo período de
crecimiento**, lo cual coincide con el **consumo real de oxígeno** en
dicho período.

Se desarrolló un modelo matemático para **predecir el oxígeno disuelto**
y el amoníaco en sistemas de acuicultura de recirculación para la cría
de tilapia del Nilo, considerando factores como **el peso promedio de
los peces** y **la temperatura del agua**. El modelo se desarrolló en
Python con algunos paquetes. El resultado es una interfaz gráfica de
usuario (GUI) independiente, denominada Asistente de Diseño y Operación
de Sistemas de Recirculación. Esta GUI estará disponible en línea para
que agricultores, ingenieros, investigadores y diseñadores la utilicen y
desarrollen**. El modelo predijo el oxígeno disuelto y el amoníaco en
diferentes etapas de crecimiento y con distintos pesos de los peces**.
Los resultados del modelo coincidieron con los valores reales.

1.  **Logros.**

<!-- -->

1)  Se revisó algunas publicaciones sobre modelos de predicción de
    oxigeno disuelto aplicado en el área de acuicultura, en el cual
    destaca el modelo dinámico de transporte de OD y la ecuación de
    balance de masa de OD.

2)  Se describió modelo utilizando ecuaciones con derivadas parciales,
    donde interviene el OD, temperatura del agua, densidad de peces y
    tasa de alimentación.

    1.  **Resultados alcanzados.**

<!-- -->

1)  Se describió la programación en Python del modelo predictivo de
    oxígeno disuelto a través de un diagrama de flujo.

**Referencias**

Khater, E. S., Bahnasawy, A., El-Ghobashy, H., Shaban, Y., Elsheikh, F.,
El-Reheem, S. A., & aboegela, M. (2021). Mathematical model for
predicting oxygen concentration in tilapia fish farms. *Scientific
Reports*, *11*(1), 1–15. https://doi.org/10.1038/s41598-021-03604-1

Ragab, A. M., El-Gindy, A. G. M., Kaddour, O., & Ali, S. A. (2022).
Dissolved Oxygen and Ammonia Mass Balance in a Recirculating Aquaculture
System for Raising the Nile Tilapia. *Egyptian Journal of Aquatic
Biology and Fisheries*, *26*(2), 217–237.
https://doi.org/10.21608/EJABF.2022.227771

Royer, E., Faccenda, F., & Pastres, R. (2021). Estimating oxygen
consumption of rainbow trout (Oncorhynchus mykiss) in a raceway: A
Precision Fish Farming approach. *Aquacultural Engineering*,
*92*(November 2020), 102141.
https://doi.org/10.1016/j.aquaeng.2020.102141

Sri-uam, P., Donnuea, S., Powtongsook, S., & Pavasant, P. (2016).
Integrated multi-trophic recirculating aquaculture system for nile
tilapia (oreochlomis niloticus). *Sustainability (Switzerland)*, *8*(7).
https://doi.org/10.3390/su8070592

Yi, Y. (1998). A bioenergetics growth model for Nile tilapia
(Oreochromis niloticus) based on limiting nutrients and fish standing
crop in fertilized ponds. *Aquacultural Engineering*, *18*(3), 157–173.
https://doi.org/10.1016/S0144-8609(98)00028-4
