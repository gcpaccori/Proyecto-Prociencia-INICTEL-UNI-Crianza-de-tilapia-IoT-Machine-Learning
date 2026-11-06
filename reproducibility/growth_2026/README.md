# SISMAPISCIS · Reproducción integral del gráfico de crecimiento (2026)

**Incluye las ecuaciones y la ejecución del núcleo ML, no solamente las curvas dibujadas.** Este paquete permite repetir, auditar y revisar la figura de comparación de cuatro modelos de crecimiento de tilapia, con siete biometrías (seis intervalos) y evaluación cronológica en cuatro fechas.

**Repositorio de origen:** `gcpaccori/Proyecto-Prociencia-INICTEL-UNI-Crianza-de-tilapia-IoT-Machine-Learning`. La ejecución no necesita acceso a MySQL, contraseñas, API, contenedores de producción ni servidores externos: `cohort.json` contiene un conjunto de datos **agregados y minimizados**, derivado de una extracción verificada en la VMI.

## Ejecución

Desde la raíz de **este directorio**, en Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py --out evidence_new
python -m unittest discover -s tests -v
```

En la VMI, **sin instalar nada en servicios productivos**, existe una ejecución probada dentro del contenedor auxiliar `flask_sismapiscis`:

```bash
docker cp ./growth_2026 flask_sismapiscis:/tmp/growth_2026
docker exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 flask_sismapiscis \
  python /tmp/growth_2026/run.py --out /tmp/growth_2026/evidence_new
docker exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 flask_sismapiscis \
  python -m unittest discover -s /tmp/growth_2026/tests -v
docker cp flask_sismapiscis:/tmp/growth_2026/evidence_new ./evidence_new
```

Para generar también una captura PNG, instalar opcionalmente `matplotlib` en un **entorno aislado** y repetir `run.py`. Sin `matplotlib` se produce siempre la captura vectorial `chart.svg`.

## Componentes y trazabilidad

| Archivo | Función |
|---|---|
| `cohort.json` | Siete biometrías reales y seis resúmenes ambientales elegibles, sin credenciales ni lecturas individuales |
| `original_ml_core.py` | Copia del núcleo real `interval_ml.py` archivado el 25/10/2026: Ridge de covarianza correlacionada y proceso gaussiano lineal+Matérn 3/2 |
| `run.py` | Invoca **`original_ml_core.evaluate(...)`** para ambos ML, ejecuta TGC y VBGF mediante fórmulas y coeficientes ajustados solo con datos anteriores, verifica predicciones, genera figura, métricas y manifiesto |
| `reference_replay.json` | Predicciones archivadas; se usan **solo para contrastar** las predicciones recién calculadas (tolerancia de 0,001 g) |
| `tests/test_runner.py` | Pruebas de ejecución, ausencia de fuga de etiquetas futuras, protocolos, coberturas y resultados |
| `evidence/` | Evidencia de una corrida real: `chart.svg`, `predictions.csv`, `audit.json`, `manifest.json`, `run.log`, `tests.log` |

Se recomienda revisar primero **`evidence/chart.svg`**, luego **`evidence/audit.json`**, y ejecutar el comando para recomputar los resultados.

## Métrica y resultado de la misma evaluación (cuatro fechas)

- Modelo SISMAPISCIS de incremento de peso (Ridge, peso inicial/duración/temperatura media/OD medio): **MAE 8,51 g**.
- Modelo probabilístico SISMAPISCIS (GP, peso inicial/duración/temperatura media/OD P10): **MAE 12,20 g**.
- Von Bertalanffy recalibrado cronológicamente: **MAE 17,49 g**.
- TGC generalizado recalibrado cronológicamente: **MAE 42,25 g**.

Las cuatro fechas finales evaluadas son 07/08, 13/09, 26/09 y 16/10/2026. En cada fecha se entrenaron usando **2, 3, 4 y 5 intervalos anteriores**, respectivamente. Para los modelos matemáticos, también se usa el peso observado del intervalo inicial. Su valor en B3 (11/07) en el gráfico es un **ancla observada**, NO una estimación.

## Fundamento de la corrección TGC/VBGF

El script experimental archivado el 30/09 calibraba la tasa TGC con el aumento inicial de **1 g → 8,19 g** y reutilizaba su parámetro en proyección acumulativa abierta, produciendo extrapolaciones de más de 2 kg en octubre. Esto **no es comparable directamente** con los ML, cuya evaluación utiliza los pesos iniciales biométricos reales de cada intervalo y reajusta la predicción con el historial disponible.

Para resolver la diferencia de protocolo, el presente ensayo **conserva la forma matemática TGC y VBGF** y el modificador ambiental original, pero **recalibra el coeficiente TGC C y la tasa VBGF K usando únicamente los incrementos anteriores a cada fecha objetivo**. El valor teórico asintótico VBGF se mantiene congelado en 392,32 g; se preservan el umbral térmico de 15,5 °C y la interpolación de oxígeno de Tran-Duy (Table 2). La exposición de cada intervalo se calcula con su temperatura y oxígeno **agregados**, no con series diarias completas. Para más detalles, consultar [PROTOCOL.md](PROTOCOL.md).

## Interpretación y alcance

La secuencia demuestra un **avance técnico verificable**: los modelos ML implementados aprenden los incrementos con covarianza biométrica y resumen de sensores, y en las cuatro fechas retrospectivas Ridge presenta el menor MAE. El gaussiano incorpora estructura probabilística del incremento; su dispersión condicional todavía no es cobertura predictiva calibrada. La referencia VBGF es competitiva en el último tramo (155,05 g frente a 150,53 g observados); ello no revierte el orden de MAE en las cuatro fechas. El trabajo aporta un mecanismo reproducible para traducir biometrías y condiciones ambientales a **peso medio estimado**, listo para pruebas de integración del gemelo digital.

**Alcance científico:** evaluación retrospectiva sobre una sola campaña, **no** predicción ex ante ni validación independiente en campañas externas. Algunas variantes ambientales se eligieron durante el desarrollo; ni métricas ni ecuaciones prueban efectos causales. El eje horario de sensores usa `created_at`, no `fecha_medicion`, porque el dispositivo presentaba desplazamientos de reloj. Son registros disponibles al cierre de cada intervalo; la hora física de exposición no está certificada. Los datos sensibles e identificadores personales no se distribuyen.

El repositorio contiene la **reproducción experimental** de la figura que acompaña el informe, y no reemplaza automáticamente los resultados históricos TGC/VBGF bajo el protocolo inicial de tres biometrías.
