**INFORME DE ACTIVIDADES N°018-2026-REAJ**

1.  **Presentación de informe**

**Entidad Ejecutora :** UNIDAD EJECUTORA 002 - INICTEL-UNI

**Contrato :** N° PE501091609-2024-PROCIENCIA

**Proyecto de Investigación :** "Validación de una estación de monitoreo
de calidad de agua y dosificación de Floc bacteriano para crianza masiva
de peces en piscigranjas artificiales con geomembrana utilizando
aprendizaje automático e Internet de las Cosas"

**Responsable Técnico :** Ing. Rubén Acosta Jacinto

**Resolución Directoral :** N° 000047-2025-INICTEL-UNI/DE

**Periodo de Informe :** abril 2026

| **DESCRIPCIÓN DE LAS ACTIVIDADES REALIZADAS** | **TOTAL**  |
|-----------------------------------------------|------------|
| \- Revisión de modelos bioenergéticos         | S/. 700.00 |

-----------------------------------------------

Rubén Eusebio Acosta Jacinto

Investigador Principal

N°PE501091609-2024-PROCIENCIA

2.  **Avances**

**Revisión de modelos bioenergéticos**

Los investigadores (Brigolin et al., 2010), desarrollaron un modelo
individual para pez Sparus Aurata, en base al efecto de la temperatura
del agua, disponibilidad de alimento y la composición de la dieta sobre
la tasa de crecimiento. Posteriormente, se calibró y validó utilizando
datos de campo originales recopilados en dos piscifactorías italianas
ubicadas en los mares Adriático y Tirreno, respectivamente. El balance
de masa de alimento no consumido y heces se calculó utilizando el modelo
en cada piscifactoría. La tasa de ingestión óptima de un pez se calculó
en función de su peso húmedo y la temperatura del agua, mientras que la
estimación de las heces consideró la diferente digestibilidad de los
lípidos, carbohidratos y proteínas de la dieta. Desde una perspectiva
aplicada, el uso futuro de este modelo de crecimiento en relación con la
selección y el monitoreo de sitios de maricultura podría ser, por lo
general, estimar tanto el rendimiento como la cantidad de alimento no
consumido y heces descargadas de una jaula de peces. La descripción
matemática del crecimiento del pez S. aurata en función del tamaño
corporal, la proporción de alimentos y la temperatura se basa en un
presupuesto energético referida en la ecuación (1):

$\frac{dw}{dt} = \frac{(A - C)}{\varepsilon_{T}}$…………..(1)

Donde:

- *W*, es el peso húmedo del pez.

- *A*, se denomina «anabolismo neto» y representa el ingreso neto de
  energía a través de la alimentación, (J/día).

- *C*, que cuantifica las pérdidas de energía de un individuo en ayunas,
  se denomina «catabolismo en ayunas» (J/día).

- $\varepsilon_{T},\ $contenido energético del tejido somático (KJ/g).

En la ecuación (1), el balance energético entre A y C se convierte en un
balance de masa mediante el parámetro ε<sub>T</sub>, que cuantifica el
contenido energético promedio de 1 g de tejido somático y es una función
del peso húmedo del pez. El conjunto completo de ecuaciones 2 y 3, que
especifican el balance energético, se presenta en la Tabla 1. El ingreso
energético es el resultado de los procesos de ingestión y absorción. La
tasa de ingestión, *I*, es proporcional al tamaño del intestino, que a
su vez se considera proporcional a **w<sup>m</sup>**, y a la función
H(*T<sub>w</sub>*), que considera la dependencia de la ingestión con la
temperatura del agua. 1. Expresiones funcionales para el anabolismo
neto:

$I = I_{\max}H\left( T_{w} \right).W^{m}$…….(2)

$H\left( T_{w} \right) = \left( \frac{T_{m} - T_{w}}{T_{m} - T_{0}} \right)^{b\left( T_{m} - T_{0} \right)}e^{b\left( T_{w} - T_{0} \right)}$……(3)

Donde:

- La tasa de ingestión *I* está limitada por el umbral superior.

- W, peso fresco (g).

- $T_{w}$, temperatura del agua °C

- *I<sub>max</sub>*: Tasa de ingestión máxima (día<sup>-1</sup>).

- $T_{0}$: temperatura óptima °C para el pez Sparus. Aurata

- $T_{m}$: temperatura letal máxima para el pez Sparus. Aurata.

- b, coeficiente de forma para la función H(T<sub>w</sub>)

- m, exponente de peso para el anabolismo

- *I<sub>ración </sub>* Cantidad de alimento proporcionada por el
  agricultor por gramo de alimento individual.(día<sup>-1</sup>)

- *I<sub>ración</sub>*, que varía con el tiempo y representa la cantidad
  de alimento disponible, calculada a partir de los datos sobre la
  cantidad de alimento y el número de individuos presentes en la jaula;
  véase la ecuación 4.

> $\left\{ \begin{array}{r}
> I = I_{ración\ \ }cuando\ I \geq I_{ración} \\
> I = 0\ cuando\ T < 12{^\circ}C \\
> .
> \end{array} \right.\ \ \ $……………(4)

Cuando estos datos no están disponibles, como en el caso del EIA
preliminar, asumimos que no hay limitación de alimento y, por lo tanto,
*I<sub>raión</sub>* siempre es igual a *I*.

Esto se tuvo en cuenta en la Ecuación (5), donde los parámetros
$\beta_{p}\beta_{c}\beta_{l}\ \ $representan, respectivamente, la
fracción de proteínas, carbohidratos y lípidos en el alimento para peces
que realmente se puede asimilar.

$A = (1 - \alpha).I.\left\lbrack C_{p}\varepsilon_{p}\beta_{p} + C_{c}\varepsilon_{c}\beta_{c} + C_{l}\varepsilon_{l}\beta_{l} \right\rbrack$…………..(5)

Donde:

α : coeficiente de catabolismo alimentario

C<sub>p</sub> : % de proteínas en los alimentos ingeridos.

C<sub>c</sub> : % de carbohidratos en los alimentos ingeridos

C<sub>l</sub> : % de lípidos en los alimentos ingeridos

β<sub>p</sub>: coeficiente de asimilación de proteínas;

$\varepsilon_{p}:$ contenido energético de la proteína (KJ
g<sup>-1</sup>)

$\varepsilon_{c}$: contenido energético de los carbohidratos (KJ
g<sup>-1</sup>)

Los parámetros de digestibilidad se utilizan en la Ecuación (6) para
calcular específicamente la tasa de producción fecal individual, F.

$F = I.\left\lbrack C_{p}\left( 1 - \beta_{p} \right) + C_{c}\left( 1 - \beta_{c} \right) + C_{l}\left( 1 - \beta_{l} \right) \right\rbrack$……..(6)

El parámetro α, en la Ecuación (5), cuantifica los costos energéticos
relacionados con la digestión, asimilación, transporte y tratamiento
bioquímico del alimento. Se considera que estas pérdidas de energía son
proporcionales a los alimentos asimilados. Las siguientes ecuaciones
funcionales del catabolismo en ayunas.

$C = \varepsilon_{o2}k_{0}K\left( T_{w} \right)W^{n}$……..(7)

$K\left( T_{w} \right) = e^{p_{k}T_{w}}$………(8)

Donde:

$\varepsilon_{o2}$: energía consumida por la respiración de 1 g de
oxígeno (KJ g<sup>-1</sup>)

$\varepsilon_{t}$: contenido energético del tejido somático (KJ
g<sup>-1</sup>).

p<sub>k</sub>: coeficiente de temperatura para el catabolismo en ayunas
(°C<sup>-1</sup>)

k<sub>0</sub>, catabolismo en ayunas a 0°C (día<sup>-1</sup>).

m: exponente de peso para el anabolismo;

n: exponente de peso para el catabolismo

Tabla 1 Parámetros utilizados en el modelo de crecimiento del pez S.
aurata y sus fuentes

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image1.png"
style="width:4.32394in;height:3.58768in" />

La descripción cuantitativa del crecimiento del pez la dorada requiere
*la especificación de 16 parámetros*, que se estimaron con base en la
literatura específica y las observaciones de campo, el subconjunto de
parámetros que especifica el anabolismo neto se determinó con base en la
bibliografía. Los parámetros de catabolismo en ayunas r<sub>0</sub> y
p<sub>k</sub> se estimaron con base en las mediciones del consumo de
oxígeno. El *parámetro b de la ecuación (3)*, que define la forma de la
función de temperatura anabólica, se calibró ajustando el modelo a los
datos de campo no publicados recopilados en Porto Ercole. Dado que
buscábamos una estimación del catabolismo en ayunas, consideramos la
tasa mínima de consumo de oxígeno a una temperatura dada.

Los valores de r<sub>0</sub> y p<sub>k</sub> reportados en la Tabla 1 se
obtuvieron ajustando las tasas de consumo de oxígeno medidas a 16, 21 y
24 °C mediante la siguiente ecuación (9).

$\frac{d_{o2}}{dt} = k_{0}e^{\left( p_{k}T_{w} \right)}W^{n}$…………..(9)

El parámetro b, que define la forma de la función de temperatura
utilizada en el término anabólico H(Tw), se calibró comparando el
resultado del modelo con una serie temporal de datos de campo.

Los 16 parámetros restantes se determinaron basándose en varios estudios
fisiológicos específicos de cada especie. La decisión de calibrar un
solo parámetro tuvo como objetivo aumentar la robustez de la estimación.
La calibración del modelo se realizó minimizando la función objetivo, de
la ecuación (10)

$\Gamma = \sum_{i = 1}^{n}\left( W_{i} - W_{i}^{\land} \right)^{2}$………..(10)

Donde Wi y ^Wi representan el peso húmedo observado y previsto del pez,
respectivamente. El mínimo de $\Gamma$ se buscó mediante un algoritmo
simplex.

Los investigadores (Aguilar et al., 2010) evaluaron el efecto del
*procesamiento de alimento* (extruido frente a peletizado) sobre el
desempeño productivo de tilapia nilótica durante un ciclo comercial de
producción. Se utilizaron 504 alevinos reversados que fueron alimentados
con un sistema de alimentación por fases (alevinaje, crecimiento 1,
crecimiento 2 y finalización) con niveles de proteína cruda para cada
fase de 43,10%, 36,40%, 31,50% y 28,65% respectivamente. Las dietas
fueron procesadas (extruidas o peletizadas) en micro extrusora para
laboratorio exteec (exteec máquinas, Brasil). El análisis de los
indicadores acumulados mostró que el proceso de extrusión generó un
mayor crecimiento y una mayor eficiencia en el uso de alimento hasta la
fase de crecimiento 2 (P\<0,05). La investigación fue realizada en el
Laboratorio de nutrición de Peces de la estación Piscícola La Terraza
ubicada en la ciudad de Villavicencio, departamento del Meta. Se
utilizaron 504 alevinos reversados, los cuales fueron obtenidos de una
granja comercial de producción y alojados en un *sistema de
recirculación* con 14 tanques plásticos de 600 L, con biofiltro y
aireación continua. La densidad inicial fue de 36 peces por tanque y
disminuyó en función del tiempo debido a la mortalidad y al sacrificio
periódico de algunos peces para la realización de un estudio adicional
sobre el efecto del procesamiento del alimento sobre la dinámica de la
composición corporal, diariamente fue registrada la temperatura y
semanalmente se realizaron determinaciones de oxígeno disuelto, pH,
nitrógeno amoniacal total, amonio, nitrito, dureza y alcalinidad
llevando a cabo los manejos correspondientes para garantizar óptimas
condiciones de calidad de agua para el desarrollo de la especie. Durante
el estudio se utilizó un sistema de alimentación por fases, en el cual
la transición de una dieta a otra se realizó cuando los animales de al
menos una unidad experimental (tanque) de uno de los tratamientos
alcanzaron en promedio pesos corporales superiores al peso objetivo de
cada fase (32 g en alevinaje, 112 g en crecimiento 1, 480 g en
crecimiento 2 y 800 g en finalización). La frecuencia de alimentación
fue decreciente a lo largo del estudio, inició con 8 suministros diarios
en la fase de alevinaje y concluyó con 2 en la de finalización. La
oferta de alimento en cada suministro fue a saciedad aparente. Las
dietas incluyeron recursos alimenticios de uso corriente en la
manufactura de alimentos balanceados para tilapia, y propendieron por
cumplir con las recomendaciones nutricionales para esta especie (tabla
1).

Tabla 1. Inclusión de ingredientes en las dietas del sistema de
alimentación (%)

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image2.png"
style="width:4.31852in;height:2.79045in" />

Las dietas fueron procesadas de dos maneras: peletizada o extruida en
una micro extrusora para laboratorio exteec® (exteec máquinas, Brasil).

Modificando las condiciones de procesamiento (velocidad de paso y
configuración del cañón y tornillo) fue posible obtener los gránulos
extruidos o peletizados que fueron secados en horno con circulación
forzada a 55 ºC durante 24 h, posteriormente enfriados a temperatura
ambiente. La densidad calórica en término de energía digestible (ed)
calculada de las dietas fue de 3,74; 3,59; 3,52 y 3,48 Mcal/kg para las
fases de alevinaje, crecimiento 1, crecimiento 2 y finalización,
respectivamente. Quincenalmente se realizaron pesajes y mediciones para
lo cual los peces fueron atrapados en redes y anestesiados usando una
solución de aceite de clavo (eugenol-10 ppm). Para cada una de las fases
de alimentación se calcularon los siguientes indicadores de desempeño
productivo:

$Factor\ de\ condición = 100*\frac{P}{{Lt}^{3}}\ $……………..(1)

Donde:

P: Peso corporal de cada uno de los peces muestreados al final de cada
fase.

Lt: Longitud total de cada uno de los peces muestreados al final de cada
fase

$$Biomasa\ final\ \left( \frac{Kg}{m^{3}} \right) = (Pf*Nf)*1.666\ldots\ldots\ldots\ldots..(2)$$

Donde:

Pf: Promedio de peso corporal final de los peces en cada tanque.

Nf: Número de peces vivos en cada tanque al final de cada fase

1.666: factor que permite convertir los resultados por tanque a valores
por metro cúbico.

$Ganancia\ diaria\ (\frac{g}{pez}) = \frac{(Pf - Pi)}{t}$……………(3)

Donde:

Pf: Promedio de peso corporal final de los peces en cada tanque.

Pi: Promedio de peso corporal inicial en cada tanque.

t: tiempo de duración de la fase en días.

$Tasa\ específica\ de\ crecimiento\ \left( \frac{\%}{día} \right) = 100*\frac{\left( \ln{Pf} - \ln{Pi} \right)}{t}$………….(4)

$Conversión\ alimenticia\ ajustada = \frac{CAL}{GBT}$…………….(5)

Donde:

CAL: consumo de alimento por cada tanque

GBT: ganancia de biomas total (biomasa final del tanque + biomasa
retirada por mortalidad + biomasa extraída para el estudio de
composición corporal)

$Tasa\ de\ alimentación\ (\%\ de\ la\ biomasa) = 100*\frac{CAMP}{PCPP}$……….(6)

Donde:

CAMP: consumo de alimento promedio por pez durante la fase.

PCPP: promedio de peso corporal de los peces a lo largo de la fase

$$Mortalidad\ (\%) = 100*\frac{Nm}{36}$$

Nm: Número de peces muertos en cada estanque

36: número inicial de peces por tanque

El peso corporal promedio obtenido en la primera unidad experimental que
logró el peso objetivo de cada de una de las fases y la duración de las
mismas se presentan en la tabla 3

Tabla 3. Peso corporal objetivo y obtenido, y duración de cada una de
las fases de alimentación.

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image3.png"
style="width:5.29293in;height:1.64789in" />

En la tabla 4, se presenta el efecto del procesamiento del alimento
sobre el desempeño productivo de tilapia nilótica en un ciclo comercial
durante la fase de alevinaje (0-45 días).

Tabla 4.

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image4.png"
style="width:4.76768in;height:2.91841in" />

En la tabla 5, se muestra el efecto del procesamiento del alimento sobre
el desempeño productivo de tilapia nilótica en un ciclo comercial
durante la fase de crecimiento 1 (46-77 días).

Tabla 5.

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image5.png"
style="width:5.24242in;height:2.17226in" />

En la tabla 6, se muestra el efecto del procesamiento del alimento sobre
el desempeño productivo de tilapia nilótica en un ciclo comercial
durante la fase de crecimiento 2 (78-177 días).

Tabla 6.

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image6.png"
style="width:5.30303in;height:2.20928in" />

En la tabla 7, se muestra el efecto del procesamiento del alimento sobre
el desempeño productivo de tilapia nilótica en un ciclo comercial
durante la fase de finalización (178-249 días).

Tabla 7.

<img
src="Informe018_Modelos_Bioenergeticos_media/media/image7.png"
style="width:5.25758in;height:2.18782in" />

En la fase de finalización los desempeños fueron similares entre los
tipos de procesamiento, respuesta que podría estar asociada con una
mayor densidad en términos de biomasa alcanzada por el grupo alimentado
con alimento extruido generando así que el desempeño global del ciclo no
presentara diferencias entre los tratamientos.

1.  **Logros.**

> El modelo bioenergético está basado en el ajuste de las tasas de
> consumo de oxígeno.

2.  **Resultados alcanzados.**

> A través de los artículos científicos leídos respecto al presupuesto
> energético, nos indica que, no sólo depende el rendimiento y
> crecimiento de los peces del oxígeno disuelto sino también del tamaño
> corporal, la proporción de alimentos y la temperatura.

**Referencias**

Aguilar, F., Afanador, G., & Muñoz, A. (2010). Efecto Del Procesamiento
De La Dieta Sobre El Desempeño Productivo De Tilapia Niolitica En Un
Ciclo Comercial De Produccion. *Revista de La Facultad de Medicina
Veterinaria y de Zootecnia*, *57*, 7.

Brigolin, D., Pastres, R., Tomassetti, P., & Porrello, S. (2010).
Modelling the biomass yield and the impact of seabream mariculture in
the Adriatic and Tyrrhenian Seas (Italy). *Aquaculture International*,
*18*(2), 149–163. https://doi.org/10.1007/s10499-008-9232-4
