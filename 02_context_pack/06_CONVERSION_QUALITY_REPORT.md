# 06_CONVERSION_QUALITY_REPORT.md

## Estado de conversión DOCX → Markdown

Los archivos se convirtieron con Pandoc a Markdown GFM. Las imágenes, diagramas y algunas ecuaciones/tablas se extrajeron en carpetas `*_media/`.

## Archivos convertidos

### `Informe015_Gemelo_Digital.md`

- Longitud aproximada: 959 líneas.
- Imágenes/medios extraídos: 25.
- Fragmentos LaTeX detectados: 1.
- Marcadores de ecuación con puntos/suspensión: 1.
- Primeros marcadores que requieren revisión manual:
  - Línea 173: `$\frac{{\partial C}_{(x,t)}}{\partial t} = - \frac{(Q)}{(A)}\frac{{\partial C}_{(x,t)}}{\partial x} + K_{rear}\left( {Csat}_{(x,t)} - C_{(x,t)} \right) - \frac{`

### `Informe016_Oxigeno_Disuelto.md`

- Longitud aproximada: 717 líneas.
- Imágenes/medios extraídos: 13.
- Fragmentos LaTeX detectados: 14.
- Marcadores de ecuación con puntos/suspensión: 18.
- Primeros marcadores que requieren revisión manual:
  - Línea 150: `style="width:1.39815in;height:0.61419in" />……………..(1)`
  - Línea 395: `+DO<sub>PF</sub>………..(1)`
  - Línea 414: `$\frac{dDO}{dt} = {DO}_{FR} + {DO}_{B} + {DO}_{N} - {DO}_{PF}$ ………………(2)`
  - Línea 424: `${DO}_{t} = {DO}_{t - 1} + \left( \frac{dDO}{dt}.\ dt \right)$……………….(3)`
  - Línea 434: `0.21WT……..(4)`
  - Línea 436: `${DO}_{FR} = \frac{FR\ x\ SD}{1000}$………….(5)`
  - Línea 461: `DO<sub>N</sub> = 4.57× K<sub>NR</sub> × Nr/V…………(6)`
  - Línea 463: `K<sub>NR</sub> = 0.1(1.08)<sup>(T−20)</sup>……………….(7)`
  - Línea 465: `$N_{r} = \frac{0.03\ x\ F_{r}xWxN_{f}}{24\ x\ 1000}$……………..(8)`
  - Línea 482: `$F_{r} = 17.02\ x\ e^{\left\lbrack \frac{\left( \ln{W + 1.14} \right)^{2}}{- 19.52} \right\rbrack}$…………..(9)`
  - Línea 490: `${DO}_{B} = \frac{(2.3)\left( {BOD}_{5} \right)\left( W_{n} \right)}{(V)(24)(1000)}$………………(10)`
  - Línea 509: `${DO}_{PF} = \frac{PC\ x\ fx\ \ Ex\ OTR}{V}$……………..(11)`
  - Línea 538: `$FGR = \left( 0.2919\tau\kappa\delta\varphi hfW^{m} \right) - k.W^{n}$………….(12)`
  - Línea 565: `$\tau = EXP\left\{ - 4.6\left\lbrack \frac{T_{opti} - T}{T_{opti} - T_{\max}} \right\rbrack^{4} \right\}\ if\ \ T < T_{opti}$…………..(13)`
  - Línea 567: `$\tau = EXP\left\{ - 4.6\left\lbrack \frac{T - T_{opti}}{T_{\max} - T_{opti}} \right\rbrack^{4} \right\}\ if\ \ T \geq T_{opti}$…………..(14)`
  - Línea 577: `K = K<sub>min</sub> exp\[s(T − T<sub>min</sub>)\]……………(15)`
  - Línea 596: `> $\delta = 1.0\ \ \ if\ DO\  > {DO}_{crit}$…………(16)`
  - Línea 598: `$\delta = \frac{DO - {DO}_{\min}}{{DO}_{crit} - {DO}_{\min}}\ \ \ \ if\ \ \ {DO}_{\min} \leq DO \leq {DO}_{crit}$…………….(17)`

### `Informe017_Crecimiento_Alimentacion_ML.md`

- Longitud aproximada: 912 líneas.
- Imágenes/medios extraídos: 13.
- Fragmentos LaTeX detectados: 12.
- Marcadores de ecuación con puntos/suspensión: 19.
- Primeros marcadores que requieren revisión manual:
  - Línea 131: `$X_{norm} = \frac{X_{t} - X_{\min}}{X_{\max} - X_{\min}}$…………………(1)`
  - Línea 417: `$e_{t} = sigmoid\left( {Wh}_{t} + b \right)$………..(1)`
  - Línea 421: `$Y = \sum_{i = 1}^{t}\alpha_{i}h_{i}$……………….(3)`
  - Línea 480: `$\mu = \frac{1}{N}\sum_{i = 1}^{N}X_{i}$………………(4)`
  - Línea 482: `$\sigma = \sqrt{\frac{\sum_{i = 1}^{N}\left( X_{i} - \mu \right)^{2}}{N}}$……………………(5)`
  - Línea 496: `$x^{'} = \frac{x - \min_{x}}{\max(x) - min(x)}$……………………(6)`
  - Línea 523: `ΔL = -1,6707 +0,09682T ……..(1)`
  - Línea 532: `W (g) =1,861×10<sup>-8</sup> L³…………....(2)`
  - Línea 537: `ΔL = -0,853 + 0,048T………….(3)`
  - Línea 563: `W = 2,330 × 10 <sup>-8</sup> L<sup>3</sup>……(4)`
  - Línea 609: `ΔL = -1,6623 + 0,097021T ………(5)`
  - Línea 637: `ΔL = -1,7147 + 0,097794T……………(6)`
  - Línea 676: `ΔL = -1,6707 + 0,09682T……….(1)`
  - Línea 707: `F = \[(3 x C x ΔL)/L\] x100…………..(7)`
  - Línea 730: `W = 1,861 × 10 <sup>-8</sup>L³……….(2)`
  - Línea 787: `ΔL = *α* + *bT*…………..(8)`
  - Línea 807: `$L^{3} = \frac{W}{0.0002877}$……………….(9)`
  - Línea 842: `$F = \frac{(3xCx\mathrm{\Delta}L)}{L}$ x 100……….(10)`
  - Línea 892: `ΔL = -1,6707 +0,09682T ……..(1)`

### `Informe018_Modelos_Bioenergeticos.md`

- Longitud aproximada: 418 líneas.
- Imágenes/medios extraídos: 7.
- Fragmentos LaTeX detectados: 29.
- Marcadores de ecuación con puntos/suspensión: 15.
- Primeros marcadores que requieren revisión manual:
  - Línea 55: `$\frac{dw}{dt} = \frac{(A - C)}{\varepsilon_{T}}$…………..(1)`
  - Línea 81: `$I = I_{\max}H\left( T_{w} \right).W^{m}$…….(2)`
  - Línea 83: `$H\left( T_{w} \right) = \left( \frac{T_{m} - T_{w}}{T_{m} - T_{0}} \right)^{b\left( T_{m} - T_{0} \right)}e^{b\left( T_{w} - T_{0} \right)}$……(3)`
  - Línea 115: `> \end{array} \right.\ \ \ $……………(4)`
  - Línea 126: `$A = (1 - \alpha).I.\left\lbrack C_{p}\varepsilon_{p}\beta_{p} + C_{c}\varepsilon_{c}\beta_{c} + C_{l}\varepsilon_{l}\beta_{l} \right\rbrack$…………..(5)`
  - Línea 149: `$F = I.\left\lbrack C_{p}\left( 1 - \beta_{p} \right) + C_{c}\left( 1 - \beta_{c} \right) + C_{l}\left( 1 - \beta_{l} \right) \right\rbrack$……..(6)`
  - Línea 157: `$C = \varepsilon_{o2}k_{0}K\left( T_{w} \right)W^{n}$……..(7)`
  - Línea 159: `$K\left( T_{w} \right) = e^{p_{k}T_{w}}$………(8)`
  - Línea 201: `$\frac{d_{o2}}{dt} = k_{0}e^{\left( p_{k}T_{w} \right)}W^{n}$…………..(9)`
  - Línea 213: `$\Gamma = \sum_{i = 1}^{n}\left( W_{i} - W_{i}^{\land} \right)^{2}$………..(10)`
  - Línea 282: `$Factor\ de\ condición = 100*\frac{P}{{Lt}^{3}}\ $……………..(1)`
  - Línea 303: `$Ganancia\ diaria\ (\frac{g}{pez}) = \frac{(Pf - Pi)}{t}$……………(3)`
  - Línea 313: `$Tasa\ específica\ de\ crecimiento\ \left( \frac{\%}{día} \right) = 100*\frac{\left( \ln{Pf} - \ln{Pi} \right)}{t}$………….(4)`
  - Línea 315: `$Conversión\ alimenticia\ ajustada = \frac{CAL}{GBT}$…………….(5)`
  - Línea 325: `$Tasa\ de\ alimentación\ (\%\ de\ la\ biomasa) = 100*\frac{CAMP}{PCPP}$……….(6)`

## Recomendación

Para implementación productiva, usar los Markdown como contexto textual y las carpetas media como fuente de verdad visual. Si una fórmula no está en texto o LaTeX completo, marcarla como `FORMULA_PENDING_EXTRACTION` hasta validarla manualmente.