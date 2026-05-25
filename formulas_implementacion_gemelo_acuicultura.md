# Fórmulas exactas y especificación técnica para implementar los componentes viables del Gemelo Digital acuícola

**Proyecto:** estación de monitoreo de calidad de agua y dosificación de floc bacteriano para crianza masiva de peces en piscigranjas artificiales con geomembrana usando IA, IoT y Gemelo Digital.  
**Objetivo del documento:** entregar al GPT programador / Codex una guía directa para programar todos los bloques viables con la base histórica tabular de un año de telemetría.

---

## 0. Regla de alcance

Implementar únicamente los componentes viables con datos tabulares, sensores, modelos matemáticos y modelos de IA entrenables con series temporales.

### Implementar ahora

1. Modelos deterministas de oxígeno disuelto y calidad de agua.
2. Modelos de crecimiento, alimentación y bioenergética.
3. Modelos tabulares supervisados y no supervisados.
4. Redes recurrentes LSTM/RNN y atención para series temporales.
5. Lógica de Gemelo Digital: MBC, MBD, híbrido, independiente, descriptivo, diagnóstico, predictivo, prescriptivo y autónomo.

### No implementar como modelo final todavía

Estos módulos quedan como interfaces, stubs o tareas futuras porque requieren datos no disponibles en la telemetría tabular:

1. CNN de segmentación para detección de agujeros en mallas.
2. CNN/I3D para evaluación de saciedad desde video subacuático.
3. Modelos matemáticos de comportamiento de peces por tracking avanzado.
4. Modelo de distribución de alimento por corrientes y difusión turbulenta CFD.
5. Modelo predictivo completo de amoníaco no ionizado con cinética de biofiltro.  
   Se permite usar TAN/nitrificación como término auxiliar en el balance de oxígeno, pero no venderlo como predictor completo de amoníaco.

---

## 1. Convenciones de variables y unidades

| Variable | Descripción | Unidad esperada |
|---|---|---|
| `t` | tiempo | h, día o timestamp según módulo |
| `dt` | paso temporal | h |
| `x` | coordenada longitudinal del canal | m |
| `DO`, `C` o `x_DO` | concentración de oxígeno disuelto | mg/L o g/m³ |
| `DO_sat`, `Csat` | concentración de saturación de oxígeno | mg/L |
| `T`, `T_w` | temperatura del agua | °C |
| `Q` | caudal de agua | L/h, m³/h o m³/s; normalizar antes de calcular |
| `A` | área transversal del canal | m² |
| `V` | volumen del tanque/canal | L o m³; usar coherencia con la fórmula |
| `M` | biomasa de peces | kg |
| `W` | peso promedio individual | g salvo que se indique otra unidad |
| `N_f` | número de peces vivos | unidad |
| `S` | tasa de suministro de oxígeno | mg L⁻¹ h⁻¹ |
| `R` | tasa de consumo de oxígeno | mg h⁻¹ kg⁻¹ o mg h⁻¹ L⁻¹ según modelo |
| `F_r` | tasa de alimentación | % peso corporal/día |
| `pH`, `TAN`, `ORP`, `EC` | variables fisicoquímicas | según sensor |

Regla de ingeniería: antes de ejecutar cualquier fórmula, convertir todas las entradas a las unidades esperadas por el módulo. No mezclar L/h con m³/h ni mg/L con g/m³ sin conversión explícita.

---

## 2. Modelos deterministas de oxígeno disuelto

### 2.1 Modelo 0D de oxígeno disuelto en canal bien mezclado

Usar cuando se asume que el canal/tanque está bien mezclado. La concentración de OD se modela como una EDO.

$$
\frac{dx}{dt}=\frac{Q(x_{in}-x)}{V}+S+k_{rear}(DO_{sat}-x)-\frac{MR}{V}
$$

Donde:

- `x`: concentración de OD en el canal, mg L⁻¹.
- `x_in`: concentración de OD en el afluente, mg L⁻¹.
- `Q`: caudal volumétrico, L h⁻¹.
- `V`: volumen del canal, L.
- `S`: tasa de suministro de oxígeno, mg L⁻¹ h⁻¹.
- `k_rear`: tasa de reaireación, h⁻¹.
- `DO_sat`: concentración de saturación, mg L⁻¹.
- `M`: biomasa, kg.
- `R`: tasa de consumo de oxígeno, mg h⁻¹ kg⁻¹.

Implementación Euler explícito:

$$
x_t=x_{t-1}+\Delta t\left[\frac{Q(x_{in,t}-x_{t-1})}{V}+S_t+k_{rear}(DO_{sat,t}-x_{t-1})-\frac{M_tR_t}{V}\right]
$$

Firma sugerida:

```python
def update_do_0d(x_prev, x_in, q_l_h, volume_l, s, k_rear, do_sat, biomass_kg, respiration_rate, dt_h):
    dxdt = (q_l_h * (x_in - x_prev) / volume_l) + s + k_rear * (do_sat - x_prev) - (biomass_kg * respiration_rate / volume_l)
    return x_prev + dt_h * dxdt
```

---

### 2.2 Tasa metabólica sinusoidal con efecto de temperatura

Para simular oscilación diaria de respiración:

$$
R=(R_m+A\cos(2\pi f(t+\phi)))e^{p_k(T_w-15)}
$$

Parámetros de referencia extraídos del documento:

| Parámetro | Valor / uso |
|---|---|
| `R_m` | tasa media diaria de respiración; calibrar |
| `A` | amplitud diaria; calibrar |
| `f` | frecuencia sinusoidal = `1/24` h⁻¹ |
| `phi` | fase; calibrar |
| `p_k` | `0.07` |
| `T_w` | temperatura del agua, °C |

Firma sugerida:

```python
def respiration_sinusoidal(t_h, temp_c, r_m, amplitude, phase, p_k=0.07, freq=1/24):
    return (r_m + amplitude * math.cos(2 * math.pi * freq * (t_h + phase))) * math.exp(p_k * (temp_c - 15))
```

---

### 2.3 Concentración de saturación de oxígeno disuelto

Fórmula polinómica:

$$
DO_{sat}(T_w)=14.589-0.4T_w+0.008T_w^2-0.0000661T_w^3
$$

Firma sugerida:

```python
def do_saturation(temp_c):
    return 14.589 - 0.4 * temp_c + 0.008 * temp_c**2 - 0.0000661 * temp_c**3
```

---

### 2.4 Tasa de suministro de oxígeno puro

$$
S=\frac{0.9\,LO2\,P\,M_m}{N_a\,k\,[T_w(t)+273.15]V}
$$

Parámetros de referencia:

| Parámetro | Valor / unidad |
|---|---|
| `LO2` | 2400 L h⁻¹ |
| `P` | 101325 Pa |
| `M_m` | 31.998 g mol⁻¹ |
| `N_a` | 6.022 × 10²³ mol⁻¹ |
| `k` | 1.38 × 10⁻²³ J K⁻¹ |
| `V` | 1280 m³ en el caso de referencia |
| `0.9` | eficiencia OTE = 90 % |

Firma sugerida:

```python
def oxygen_supply_rate(lo2_l_h, pressure_pa, molar_mass_g_mol, temp_c, volume_m3, efficiency=0.9):
    NA = 6.022e23
    k = 1.38e-23
    return (efficiency * lo2_l_h * pressure_pa * molar_mass_g_mol) / (NA * k * (temp_c + 273.15) * volume_m3)
```

---

### 2.5 Modelo de transporte 1D de oxígeno disuelto

Usar cuando se desea representar variación longitudinal en el canal.

$$
\frac{\partial C_{(x,t)}}{\partial t}=-\frac{Q}{A}\frac{\partial C_{(x,t)}}{\partial x}+K_{rear}(Csat_{(x,t)}-C_{(x,t)})-\frac{R_{(t)}}{A}\frac{\partial M_{(x,t)}}{\partial x}
$$

Donde:

- `x`: coordenada de corriente, m.
- `t`: tiempo, h.
- `C`: concentración de OD, mg L⁻¹.
- `Csat`: concentración de saturación, mg L⁻¹.
- `K_rear`: tasa de reaireación, h⁻¹.
- `Q`: caudal de agua.
- `A`: área transversal del canal.
- `R`: tasa de consumo de oxígeno.
- `M`: biomasa acumulada a lo largo de `x`.

Discretización recomendada con diferencia upwind para advección:

$$
C_i^{t+1}=C_i^t+\Delta t\left[-\frac{Q}{A}\frac{C_i^t-C_{i-1}^t}{\Delta x}+K_{rear}(Csat_i^t-C_i^t)-\frac{R_t}{A}\frac{M_i^t-M_{i-1}^t}{\Delta x}\right]
$$

Regla de estabilidad inicial:

$$
\Delta t \leq \frac{\Delta x}{Q/A}
$$

---

### 2.6 Función objetivo para calibrar modelos de OD

RMSE:

$$
RMSE=\sqrt{\frac{\sum_{i=1}^{n}(\hat{y_i}-y_i)^2}{n}}
$$

Donde:

- `y_i`: OD observado en el efluente en `t_i`.
- `ŷ_i`: OD estimado por el modelo en `t_i`.
- `n`: número de observaciones.

---

## 3. Balance de oxígeno en sistema de recirculación acuícola RAS

### 3.1 Balance general de demanda/suplementación

$$
DO_{FR}+DO_B+DO_N=DO_{sup}+DO_{PF}
$$

Despeje operativo:

$$
DO_{sup}=DO_{FR}+DO_B+DO_N-DO_{PF}
$$

Para implementación real:

```python
oxygen_required = max(0, DO_FR + DO_B + DO_N - DO_PF)
```

No confundir demanda de oxígeno con concentración disponible. Para simular concentración real:

$$
\frac{dDO}{dt}=DO_{sup}+DO_{PF}-DO_{FR}-DO_B-DO_N
$$

Actualización temporal:

$$
DO_t=DO_{t-1}+\left(\frac{dDO}{dt}\Delta t\right)
$$

---

### 3.2 Respiración de peces

Tasa de consumo respiratorio por temperatura y peso:

$$
FR=2014.45+2.75W-165.2T+0.007W^2+3.93T^2-0.21WT
$$

$$
DO_{FR}=\frac{FR\cdot SD}{1000}
$$

Donde:

- `FR`: mg O₂ kg⁻¹ pez h⁻¹.
- `W`: masa promedio individual, g.
- `T`: temperatura del agua, °C.
- `SD`: densidad de siembra, kg m⁻³.
- La ecuación fue reportada para peces de 20 a 200 g y 24 a 32 °C.

---

### 3.3 Nitrificación como consumo de oxígeno

$$
DO_N=4.57\times K_{NR}\times\frac{N_r}{V}
$$

$$
K_{NR}=0.1(1.08)^{(T-20)}
$$

$$
N_r=\frac{0.03\times F_r\times W\times N_f}{24\times1000}
$$

Donde:

- `K_NR`: coeficiente de nitrificación.
- `N_r`: tasa de nitrificación, g TAN h⁻¹.
- `F_r`: tasa de alimentación, % peso corporal día⁻¹.
- `W`: peso promedio individual, g.
- `N_f`: número de peces.
- `V`: volumen de agua, m³.

Tasa de alimentación auxiliar:

$$
F_r=17.02\times e^{\left[\frac{(\ln(W+1.14))^2}{-19.52}\right]}
$$

---

### 3.4 Consumo de oxígeno por biofiltro

$$
DO_B=\frac{2.3\times BOD_5\times W_n}{V\times24\times1000}
$$

Donde:

- `BOD_5`: tasa promedio de excreción de DBO₅ sin filtrar. Valor referencial: 2160 mg O₂ kg⁻¹ pez día⁻¹.
- `W_n`: biomasa, kg.
- `V`: volumen de agua, m³.

---

### 3.5 Oxígeno añadido por flujo de tubería / bombeo

$$
DO_{PF}=\frac{PC\times f\times E\times OTR}{V}
$$

Donde:

- `PC`: duración del ciclo de bombeo, h.
- `f`: frecuencia de bombeo, h⁻¹.
- `E`: eficiencia, proporción o porcentaje según dataset; normalizar a 0–1.
- `OTR`: tasa de transferencia de oxígeno, g O₂ h⁻¹.
- `V`: volumen de agua, m³.

---

## 4. Modelo de crecimiento ambiental de Yi / tasa FGR

### 4.1 Tasa de crecimiento del pez

$$
FGR=(0.2919\tau\kappa\delta\varphi h f W^m)-K W^n
$$

Donde:

- `FGR`: tasa de crecimiento, g día⁻¹.
- `tau`: factor de temperatura, 0 a 1.
- `kappa`: factor de fotoperiodo, 0 a 1.
- `delta`: factor de oxígeno disuelto, 0 a 1.
- `phi`: factor de amoníaco no ionizado, 0 a 1.
- `h`: coeficiente de consumo de alimento.
- `f`: nivel de alimentación relativo, 0 a 1.
- `W`: peso del pez.
- `K`: coeficiente de catabolismo.
- `m`, `n`: constantes alométricas.

Como el modelo completo de amoníaco no ionizado está condicionado, usar por defecto:

```python
phi = 1.0  # hasta que exista modelo validado de NH3 no ionizado
```

---

### 4.2 Factor de temperatura

Para `T < T_opti`:

$$
\tau=EXP\left\{-4.6\left[\frac{T_{opti}-T}{T_{opti}-T_{max}}\right]^4\right\}
$$

Para `T >= T_opti`:

$$
\tau=EXP\left\{-4.6\left[\frac{T-T_{opti}}{T_{max}-T_{opti}}\right]^4\right\}
$$

Variables:

- `T_min`: temperatura por debajo de la cual se detiene la alimentación.
- `T_max`: temperatura por encima de la cual se detiene la alimentación.
- `T_opti`: temperatura óptima.

---

### 4.3 Catabolismo dependiente de temperatura

$$
K=K_{min}\exp[s(T-T_{min})]
$$

Donde:

- `K_min`: coeficiente de catabolismo en ayunas a `T_min`.
- `s`: constante empírica.

---

### 4.4 Factor de oxígeno disuelto

El texto original presenta tres reglas: sin efecto por encima de `DO_crit`, afectación lineal entre `DO_min` y `DO_crit`, y parada bajo el mínimo. Para programación usar:

$$
\delta=1.0\quad\text{si }DO>DO_{crit}
$$

$$
\delta=\frac{DO-DO_{min}}{DO_{crit}-DO_{min}}\quad\text{si }DO_{min}\leq DO\leq DO_{crit}
$$

$$
\delta=0.0\quad\text{si }DO<DO_{min}
$$

Nota técnica: en una línea del documento aparece `DO < DOcrit` para la condición cero, pero por la propia definición previa debe ser `DO < DOmin`; si se usa `DOcrit`, se contradice la regla intermedia.

---

## 5. Modelos lineales de crecimiento Soderberg / Taylor

### 5.1 Modelo general

$$
\Delta L=\alpha+bT
$$

Donde:

- `ΔL`: incremento diario de longitud, mm/día.
- `T`: temperatura, °C.
- `α`: intersección.
- `b`: pendiente.

Regla de selección: usar la ecuación cuyo rango de temperatura contenga el valor observado y cuyo `R²` sea mayor.

---

### 5.2 Tilapia del Nilo, cultivo intensivo en agua corriente

Ecuación combinada para 21–30 °C:

$$
\Delta L=-1.6707+0.09682T
$$

`R² = 0.95`

Relación peso-longitud para tilapia del Nilo macho:

$$
W(g)=1.861\times10^{-8}L^3
$$

Donde `L` está en mm y `W` en g.

Ecuación 2002:

$$
\Delta L=-1.6623+0.097021T
$$

Ecuación 2005:

$$
\Delta L=-1.7147+0.097794T
$$

---

### 5.3 Tilapia azul

$$
\Delta L=-0.853+0.048T
$$

Rango: 20–30 °C.  
`R² > 0.99`

---

### 5.4 Modelos lineales por especie para criaderos

| Especie | Modelo | Rango °C | R² |
|---|---:|---:|---:|
| Brook trout | `ΔL = -0.348 + 0.0944T` | 5.5–12.2 | >0.99 |
| Brook trout | `ΔL = 0.155 + 0.0355T` | 4–19 | 0.637 |
| Brook trout | `ΔL = 0.006 + 0.0455T` | 7–19 | 0.792 |
| Brook trout | `ΔL = -0.068 + 0.0578T` | 7–16 | 0.882 |
| Rainbow trout | `ΔL = -0.040 + 0.0505T` | 4–19 | 0.886 |
| Rainbow trout | `ΔL = 0.043 + 0.0450T` | 7–19 | 0.801 |
| Rainbow trout | `ΔL = -0.167 + 0.066T` | 7–16 | 0.971 |
| Lake trout | `ΔL = 0.176 + 0.0426T` | 4–16 | 0.858 |
| Lake trout | `ΔL = -0.0622 + 0.0588T` | 4–13 | 0.979 |
| Steelhead | `ΔL = 0.0329 + 0.0294T` | 4–19 | 0.856 |
| Steelhead | `ΔL = -0.0407 + 0.0386T` | 7–16 | 0.963 |
| Atlantic salmon | `ΔL = 0.0043 + 0.0306T` | 4–19 | 0.926 |
| Atlantic salmon | `ΔL = -0.0429 + 0.0371T` | 7–16 | 0.999 |
| Channel catfish | `ΔL = -0.612 + 0.0298T` | 24–30 | 0.825 |
| Channel catfish | `ΔL = 0.195 + 0.0463T` | 24–28 | 0.991 |
| Tiger muskellunge 3–4 cm | `ΔL = -0.0548 + 0.0912T` | 14–24 | 0.985 |
| Tiger muskellunge 12–13 cm | `ΔL = 0.394 + 0.0471T` | 18–24 | 0.864 |
| Blue tilapia | `ΔL = -0.853 + 0.048T` | 20–30 | >0.99 |

---

### 5.5 Conversión peso-longitud para bagre de canal

$$
L^3=\frac{W}{0.0002877}
$$

Donde:

- `L`: longitud en pulgadas.
- `W`: peso en libras.

---

### 5.6 Tasa diaria de alimentación Haskell

$$
F=\frac{3C\Delta L}{L}\times100
$$

Donde:

- `F`: porcentaje del peso corporal suministrado como alimento por día.
- `C`: conversión de alimento.
- `ΔL`: crecimiento diario en longitud.
- `L`: longitud del pez en las mismas unidades que `ΔL`.

Actualización diaria de longitud:

$$
L_t=L_{t-1}+\Delta L_t
$$

---

## 6. Modelo bioenergético Brigolin para crecimiento individual

### 6.1 Balance de masa/energía corporal

$$
\frac{dw}{dt}=\frac{A-C}{\varepsilon_T}
$$

Donde:

- `W` o `w`: peso húmedo del pez.
- `A`: anabolismo neto, J/día.
- `C`: catabolismo en ayunas, J/día.
- `ε_T`: contenido energético del tejido somático, kJ/g.

---

### 6.2 Ingestión máxima y efecto térmico

$$
I=I_{max}H(T_w)W^m
$$

$$
H(T_w)=\left(\frac{T_m-T_w}{T_m-T_0}\right)^{b(T_m-T_0)}e^{b(T_w-T_0)}
$$

Regla de limitación por ración y temperatura:

$$
I=I_{racion}\quad\text{cuando }I\geq I_{racion}
$$

$$
I=0\quad\text{cuando }T<12^\circ C
$$

Implementación robusta:

```python
I_unlimited = Imax * H_Tw * W**m
I = min(I_unlimited, I_racion) if T_w >= 12 else 0
```

---

### 6.3 Anabolismo neto

$$
A=(1-\alpha)I\left[C_p\varepsilon_p\beta_p+C_c\varepsilon_c\beta_c+C_l\varepsilon_l\beta_l\right]
$$

Donde:

- `α`: coeficiente de catabolismo alimentario.
- `C_p`, `C_c`, `C_l`: fracciones de proteína, carbohidrato y lípido en la dieta.
- `β_p`, `β_c`, `β_l`: coeficientes de asimilación.
- `ε_p`, `ε_c`, `ε_l`: contenido energético de proteína, carbohidrato y lípido.

---

### 6.4 Producción fecal individual

$$
F=I\left[C_p(1-\beta_p)+C_c(1-\beta_c)+C_l(1-\beta_l)\right]
$$

---

### 6.5 Catabolismo en ayunas

$$
C=\varepsilon_{o2}k_0K(T_w)W^n
$$

$$
K(T_w)=e^{p_kT_w}
$$

Consumo de oxígeno para calibración:

$$
\frac{d_{o2}}{dt}=k_0e^{p_kT_w}W^n
$$

Función objetivo de calibración:

$$
\Gamma=\sum_{i=1}^{n}(W_i-\hat{W_i})^2
$$

---

### 6.6 Parámetros Brigolin para S. aurata

| Parámetro | Valor | Unidad |
|---|---:|---|
| `I_max` | 0.09 | día⁻¹ |
| `α` | 0.3 | adimensional |
| `β_p` | 0.85 | adimensional |
| `β_c` | 0.5 | adimensional |
| `β_l` | 0.95 | adimensional |
| `ε_p` | 23.6 | kJ g⁻¹ |
| `ε_c` | 17.2 | kJ g⁻¹ |
| `ε_l` | 36.2 | kJ g⁻¹ |
| `ε_o2` | 13.6 | kJ g⁻¹ |
| `ε_T` | `4.66 W^0.14` | kJ g⁻¹ |
| `p_k` | 0.06 | °C⁻¹ |
| `k_0` | 0.00072 | día⁻¹ |
| `m` | 0.6 | adimensional |
| `n` | 1.0 | adimensional |
| `b` | 0.2 | adimensional |
| `T_0` | 25 | °C |
| `T_m` | 32.9 | °C |

---

## 7. Indicadores zootécnicos por fases de alimentación

### 7.1 Factor de condición

$$
Factor\ de\ condición=100\frac{P}{Lt^3}
$$

Donde:

- `P`: peso corporal del pez muestreado al final de la fase.
- `Lt`: longitud total al final de la fase.

---

### 7.2 Biomasa final

$$
Biomasa\ final\left(\frac{kg}{m^3}\right)=(P_fN_f)\times1.666
$$

Donde:

- `P_f`: peso corporal final promedio en el tanque.
- `N_f`: número de peces vivos al final de la fase.
- `1.666`: factor para convertir de tanque a m³ en el caso de referencia.

---

### 7.3 Ganancia diaria

$$
Ganancia\ diaria\left(\frac{g}{pez}\right)=\frac{P_f-P_i}{t}
$$

---

### 7.4 Tasa específica de crecimiento

$$
TEG\left(\frac{\%}{día}\right)=100\frac{\ln(P_f)-\ln(P_i)}{t}
$$

---

### 7.5 Conversión alimenticia ajustada

$$
CAA=\frac{CAL}{GBT}
$$

Donde:

- `CAL`: consumo de alimento por tanque.
- `GBT`: ganancia de biomasa total = biomasa final + biomasa retirada por mortalidad + biomasa extraída para estudio.

---

### 7.6 Tasa de alimentación respecto a biomasa

$$
Tasa\ de\ alimentación\left(\%\ de\ biomasa\right)=100\frac{CAMP}{PCPP}
$$

Donde:

- `CAMP`: consumo de alimento promedio por pez durante la fase.
- `PCPP`: peso corporal promedio de los peces a lo largo de la fase.

---

### 7.7 Mortalidad

$$
Mortalidad(\%)=100\frac{N_m}{36}
$$

Donde:

- `N_m`: número de peces muertos por tanque.
- `36`: número inicial de peces por tanque en el caso de referencia.

Para sistema configurable, reemplazar 36 por `N_inicial`:

$$
Mortalidad(\%)=100\frac{N_m}{N_{inicial}}
$$

---

## 8. Modelos de IA tabular y series temporales

### 8.1 Normalización min-max

Primera forma:

$$
X_{norm}=\frac{X_t-X_{min}}{X_{max}-X_{min}}
$$

Segunda forma equivalente:

$$
x'=\frac{x-\min(x)}{\max(x)-\min(x)}
$$

Implementar protección contra división por cero:

```python
if xmax == xmin:
    x_norm = 0.0
else:
    x_norm = (x - xmin) / (xmax - xmin)
```

---

### 8.2 Media y desviación estándar para regla 3σ

$$
\mu=\frac{1}{N}\sum_{i=1}^{N}X_i
$$

$$
\sigma=\sqrt{\frac{\sum_{i=1}^{N}(X_i-\mu)^2}{N}}
$$

Regla de atípicos:

$$
|X_i-\mu|>3\sigma
$$

---

### 8.3 Interpolación lineal de faltantes

Para un valor faltante entre `(t0, x0)` y `(t1, x1)`:

$$
x(t)=x_0+\frac{(x_1-x_0)(t-t_0)}{t_1-t_0}
$$

---

### 8.4 Selección de características por Pearson

$$
r_{xy}=\frac{\sum_{i=1}^{n}(x_i-\bar{x})(y_i-\bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i-\bar{x})^2}\sqrt{\sum_{i=1}^{n}(y_i-\bar{y})^2}}
$$

Regla:

```python
features_selected = [feature for feature in features if abs(r(feature, DO_target)) >= threshold]
```

Umbral inicial sugerido: `0.3` o `0.5`, ajustable por validación.

---

### 8.5 BPNN / red neuronal de retropropagación para consumo de alimento

Entradas del modelo 4-10-1:

1. Temperatura del agua.
2. Oxígeno disuelto.
3. Peso promedio de peces.
4. Número de peces.

Salida:

- Consumo de alimento / feed intake.

Normalización:

$$
X_{norm}=\frac{X_t-X_{min}}{X_{max}-X_{min}}
$$

Número de nodos ocultos:

$$
m=\sqrt{n+l}+\alpha
$$

Donde:

- `n`: nodos de entrada.
- `l`: nodos de salida.
- `α`: constante entre 1 y 10.
- En el documento el resultado final fue `4-10-1`.

Salida de capa oculta:

$$
H_j=f\left(\sum_{i=1}^{n}W_{ij}X_i-a_j\right),\quad j=1,\dots,l
$$

Salida de capa final:

$$
Y_k=\sum_{j=1}^{l}H_jW_{jk}-b_k,\quad k=1,2,\dots,m
$$

Nota de implementación: en la notación original hay cruce entre `l` y `m`. Para programar sin ambigüedad usar:

```python
n_inputs = 4
n_hidden = 10
n_outputs = 1
```

Pérdida:

$$
MSE=\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat{y_i})^2
$$

---

### 8.6 LSTM tradicional

Usar para predecir OD u otro indicador futuro desde ventanas temporales.

Ventana de entrada:

$$
X_t=[x_{t-L+1},x_{t-L+2},\dots,x_t]
$$

Ecuaciones LSTM estándar:

$$
f_t=\sigma(W_f[h_{t-1},x_t]+b_f)
$$

$$
i_t=\sigma(W_i[h_{t-1},x_t]+b_i)
$$

$$
\tilde{C}_t=\tanh(W_C[h_{t-1},x_t]+b_C)
$$

$$
C_t=f_tC_{t-1}+i_t\tilde{C}_t
$$

$$
o_t=\sigma(W_o[h_{t-1},x_t]+b_o)
$$

$$
h_t=o_t\tanh(C_t)
$$

Salida:

$$
\hat{y}_{t+1}=W_yh_t+b_y
$$

---

### 8.7 Pearson-LSTM

Pipeline:

1. Calcular `r_xy` de cada variable contra `OD` objetivo.
2. Retener variables con correlación absoluta superior al umbral.
3. Construir ventanas temporales.
4. Entrenar LSTM con las variables seleccionadas.

Variables recomendadas:

```text
T_w, OD, pH, TAN, ORP, conductividad, salinidad, caudal, biomasa, alimentación
```

---

### 8.8 Pearson-LSTM-AM con mecanismo de atención

Capa de atención:

$$
e_t=sigmoid(Wh_t+b)
$$

$$
\alpha_t=\frac{\exp(e_t)}{\sum_{i=1}^{t}\exp(e_i)}
$$

$$
Y=\sum_{i=1}^{t}\alpha_i h_i
$$

Pipeline:

1. Preprocesamiento: imputación, 3σ, normalización.
2. Pearson: selección de variables relevantes para OD.
3. LSTM: aprendizaje temporal.
4. Attention: ponderación de pasos temporales relevantes.
5. Dense: predicción final.

---

### 8.9 Métricas de evaluación

RMSE:

$$
RMSE=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat{y_i})^2}
$$

MAE:

$$
MAE=\frac{1}{n}\sum_{i=1}^{n}|y_i-\hat{y_i}|
$$

MAPE:

$$
MAPE=\frac{100}{n}\sum_{i=1}^{n}\left|\frac{y_i-\hat{y_i}}{y_i}\right|
$$

R²:

$$
R^2=1-\frac{\sum_{i=1}^{n}(y_i-\hat{y_i})^2}{\sum_{i=1}^{n}(y_i-\bar{y})^2}
$$

---

## 9. Algoritmos ML tabulares viables

Estos módulos se implementan como comparadores/baselines y servicios auxiliares. No todos provienen como ecuación cerrada en los informes, pero son fórmulas estándar necesarias para programar los componentes tabulares viables.

### 9.1 Regresión lineal

$$
\hat{y}=\beta_0+\sum_{j=1}^{p}\beta_jx_j
$$

Objetivo:

$$
\min_{\beta}\sum_{i=1}^{n}(y_i-\hat{y_i})^2
$$

### 9.2 Regresión logística

$$
p(y=1|x)=\frac{1}{1+e^{-(\beta_0+\beta^Tx)}}
$$

### 9.3 SVM / SVR

Clasificación:

$$
\min_{w,b}\frac{1}{2}\|w\|^2+C\sum_i\xi_i
$$

sujeto a:

$$
y_i(w^Tx_i+b)\geq1-\xi_i
$$

Regresión ε-SVR:

$$
\min\frac{1}{2}\|w\|^2+C\sum_i(\xi_i+\xi_i^*)
$$

### 9.4 Random Forest

Predicción por ensamble:

$$
\hat{y}=\frac{1}{B}\sum_{b=1}^{B}T_b(x)
$$

Clasificación:

$$
\hat{c}=mode\{T_b(x)\}_{b=1}^{B}
$$

### 9.5 K-Means

Objetivo:

$$
\min_{C}\sum_{k=1}^{K}\sum_{x_i\in C_k}\|x_i-\mu_k\|^2
$$

Centroide:

$$
\mu_k=\frac{1}{|C_k|}\sum_{x_i\in C_k}x_i
$$

### 9.6 PCA

Centrado:

$$
X_c=X-\bar{X}
$$

Covarianza:

$$
\Sigma=\frac{1}{n-1}X_c^TX_c
$$

Descomposición:

$$
\Sigma v_j=\lambda_j v_j
$$

Proyección:

$$
Z=X_cV_k
$$

### 9.7 KNN

Distancia euclidiana:

$$
d(x_i,x_j)=\sqrt{\sum_{k=1}^{p}(x_{ik}-x_{jk})^2}
$$

Regresión:

$$
\hat{y}=\frac{1}{K}\sum_{i\in N_K(x)}y_i
$$

Clasificación:

$$
\hat{c}=mode\{y_i:i\in N_K(x)\}
$$

### 9.8 SOM / mapa autoorganizado

Actualización de pesos:

$$
w_j(t+1)=w_j(t)+\eta(t)h_{cj}(t)[x(t)-w_j(t)]
$$

Vecindad gaussiana:

$$
h_{cj}(t)=\exp\left(-\frac{\|r_c-r_j\|^2}{2\sigma(t)^2}\right)
$$

### 9.9 Q-Learning para decisión prescriptiva

Actualización:

$$
Q(s,a)\leftarrow Q(s,a)+\alpha\left[r+\gamma\max_{a'}Q(s',a')-Q(s,a)\right]
$$

Estados recomendados:

```text
bucket_DO, bucket_T, bucket_pH, bucket_TAN, bucket_biomasa, fase_crecimiento
```

Acciones recomendadas:

```text
aumentar_aireacion, reducir_aireacion, alimentar_normal, reducir_alimento, pausar_alimento, alertar_operador
```

Recompensa inicial:

$$
r= -w_1|DO-DO_{target}| -w_2|T-T_{target}| -w_3FCR -w_4Mortality + w_5Growth
$$

---

## 10. Arquitectura del Gemelo Digital

### 10.1 Capas del sistema

1. **Observación:** ingesta de datos de sensores y registros productivos.
2. **Interpretación:** limpieza, normalización, simulación MBC y predicción MBD.
3. **Decisión:** reglas, umbrales, predicción, recomendación y evaluación de escenarios.
4. **Actuación:** alertas, comandos a aireación/alimentación y bitácora de intervención.

---

### 10.2 Tipologías implementables

| Tipo | Implementación mínima |
|---|---|
| MBC | Módulos matemáticos: OD 0D, OD 1D, RAS, crecimiento, bioenergética |
| MBD | Modelos ML: regresión, RF, SVM, KMeans, PCA, KNN, SOM, LSTM |
| Híbrido MBC-MBD | MBC genera variables derivadas; MBD predice residuales o futuro |
| Independiente | Simulación con parámetros cargados manualmente |
| Descriptivo | Estado actual del sistema con sensores y dashboard |
| Diagnóstico | detección de atípicos, reglas 3σ, umbrales DO/pH/TAN |
| Predictivo | forecasting de OD, crecimiento, alimento y riesgo |
| Prescriptivo | recomendaciones por reglas, optimización o Q-Learning |
| Autónomo | emisión de comandos a actuadores con límites y aprobación configurable |

---

### 10.3 Esquema de datos mínimo

```json
{
  "timestamp": "2026-01-01T00:00:00-05:00",
  "pond_id": "P01",
  "tank_id": "T01",
  "temperature_c": 24.8,
  "do_mg_l": 6.2,
  "ph": 7.4,
  "tan_mg_l": 0.3,
  "orp_mv": 250,
  "conductivity_us_cm": 800,
  "flow_l_h": 1500,
  "volume_m3": 30,
  "area_m2": 4,
  "fish_count": 1200,
  "avg_weight_g": 80,
  "biomass_kg": 96,
  "feed_kg_day": 2.5,
  "mortality_count": 0
}
```

---

## 11. Estructura de carpetas sugerida

```text
aquaculture-digital-twin/
  data/
    raw/
    processed/
  src/
    core/
      units.py
      preprocessing.py
      metrics.py
    models_deterministic/
      dissolved_oxygen_0d.py
      dissolved_oxygen_1d.py
      ras_oxygen_balance.py
      yi_growth.py
      soderberg_growth.py
      brigolin_bioenergetic.py
      zootechnic_indexes.py
    models_ml/
      baselines.py
      bpnn_feed_intake.py
      lstm_forecaster.py
      pearson_lstm.py
      pearson_lstm_attention.py
      q_learning_controller.py
    twin/
      observation.py
      interpretation.py
      diagnosis.py
      prediction.py
      prescription.py
      actuation.py
    api/
      main.py
      schemas.py
      routes.py
  tests/
    test_units.py
    test_dissolved_oxygen.py
    test_growth.py
    test_bioenergetic.py
    test_ml_pipeline.py
  README.md
```

---

## 12. Orden de implementación para el GPT programador

### Paso 1: núcleo matemático

Implementar funciones puras, sin base de datos:

- `do_saturation(temp_c)`
- `respiration_sinusoidal(...)`
- `oxygen_supply_rate(...)`
- `update_do_0d(...)`
- `update_do_1d(...)`
- `ras_oxygen_balance(...)`
- `yi_growth_rate(...)`
- `soderberg_delta_l(...)`
- `haskell_feed_rate(...)`
- `brigolin_step(...)`
- `zootechnic_indexes(...)`

### Paso 2: preprocesamiento

- imputación lineal,
- regla 3σ,
- normalización min-max,
- generación de ventanas temporales,
- partición train/validation/test respetando orden temporal.

### Paso 3: modelos ML

- baselines: regresión lineal, Random Forest, SVR,
- no supervisados: KMeans, PCA, SOM,
- BPNN para feed intake,
- LSTM,
- Pearson-LSTM,
- Pearson-LSTM-AM.

### Paso 4: Gemelo Digital

- observación: cargar sensores,
- interpretación: calcular variables derivadas,
- diagnóstico: umbrales y anomalías,
- predicción: modelos deterministas + IA,
- prescripción: recomendación,
- actuación: alertas o comandos con control de seguridad.

### Paso 5: API

Endpoints sugeridos:

```text
POST /api/v1/telemetry/ingest
GET  /api/v1/twin/state/{pond_id}
POST /api/v1/models/do/simulate-0d
POST /api/v1/models/do/simulate-1d
POST /api/v1/models/growth/soderberg
POST /api/v1/models/growth/brigolin
POST /api/v1/models/feed/bpnn/predict
POST /api/v1/models/water-quality/lstm/predict
POST /api/v1/twin/prescription/recommend
```

---

## 13. Pruebas mínimas obligatorias

1. Ningún modelo debe devolver `NaN` si las entradas están completas.
2. Normalización min-max debe manejar `xmax == xmin`.
3. OD simulado no debe ser negativo; aplicar `max(DO, 0)` después del cálculo si el modelo numérico lo exige.
4. `delta` debe quedar en `[0,1]`.
5. `tau` debe quedar en `[0,1]`.
6. Biomasa, peso, longitud y alimento no deben ser negativos.
7. Modelos LSTM deben separar entrenamiento y prueba por fecha, no aleatoriamente.
8. El módulo de amoníaco completo debe permanecer desactivado hasta contar con ecuaciones cinéticas y coeficientes del biofiltro.
9. Los módulos de visión artificial deben quedar como interfaces sin entrenamiento hasta tener imágenes/video anotado.

---

## 14. Prompt corto para entregar al GPT programador

Usa este repositorio como proyecto Python de Gemelo Digital acuícola. Implementa primero las funciones deterministas de OD, RAS, crecimiento Soderberg, modelo Yi, Brigolin e indicadores zootécnicos usando exactamente las fórmulas de este documento. Luego implementa el pipeline tabular de IA: imputación lineal, regla 3σ, normalización, Pearson, BPNN 4-10-1, LSTM, Pearson-LSTM y Pearson-LSTM-AM. Crea pruebas unitarias para cada fórmula. No implementes como modelo final los módulos de visión, saciedad por video, CFD ni amoníaco completo; solo deja interfaces/stubs. La API debe exponer simulación, predicción, diagnóstico y recomendación del Gemelo Digital.

