# Panel Laravel y registro prospectivo — 21/10/2026

La aplicación existente incorpora un botón **Crecimiento ML · experimental**
en `/modelos-ml`. Abre `/modelos-ml/crecimiento-ml` y consulta el proxy de Laravel
`/modelos-ml/crecimiento-ml/datos?piscina_id=1`. Ambas rutas conservan `web`,
`auth:sanctum`, sesión Jetstream, correo verificado y `modulo:modelosml`.

El controlador consulta el servicio privado 8013 para 7, 14 y 28 días, con clave
bearer desde `storage/app/private/tilapia-growth-api.key`. El navegador nunca recibe
esa clave. Las URLs de la vista son relativas para preservar origen y protocolo.
No se modificó el controlador previo ni el router del backend público en ejecución.

La vista presenta las últimas tres biometrias usadas, fechas de muestreo y tamaños
de muestra; gráfico observado/proyectado; antigüedad de la última muestra; peso
proyectado y tiempo desde el ancla; luz registrada; variables efectivamente usadas
y huella del artefacto. Oculta los resultados anteriores si falla una consulta.
No presenta sensores como entradas activas ni fabrica intervalos calibrados.

## Instalación realizada

En vmi2770917, la fuente de esta integración quedó en:
`/root/flask_sismapiscis/aquaculture_backend/backend/research_runs/20261021_growth_adaptive/panel_integration_20261021`.

1. Respaldar `pilot_service.py` e `install_pilot.py`; instalar sus nuevas versiones
   en `.../serving/`. Reiniciar únicamente `tilapia-growth-adaptive-pilot.service`.
   El instalador genera/preserva `serving/api.key`, copia la clave al contenedor y
   mantiene la primera disponibilidad del mismo artefacto. No publicar 8013.
2. Ejecutar `integration/deploy_laravel.py` en el host. Guarda fuentes existentes,
   manifiesto y activos previos en `panel_backup_<UTC>`, agrega controlador/vista,
   rutas y botón; instala la clave con permisos 0640 para www-data. El script
   rechaza sobrescribir otra implementación del controlador o vista.
3. Desde `/root/sismapiscis`, compilar a un directorio de preparación distinto:
   `/root/.nvm/versions/node/v22.23.2/bin/node node_modules/vite/bin/vite.js build --outDir public/build-panel-20261021`.
   Verificar manifiesto y archivos, copiar activos nuevos a `public/build`,
   preservando los nombres antiguos, y reemplazar `manifest.json` de forma
   atómica. El botón conserva la piscina seleccionada; «T» corresponde a piscina 1.
4. Copiar `capture_prospective.py` a `.../serving/` y los dos archivos systemd a
   `/etc/systemd/system/`; `systemctl daemon-reload`, habilitar/iniciar
   `tilapia-growth-prospective.timer` y ejecutar una captura inicial.

El archivo privado de clave queda fuera de Git; nunca incluirlo en informes,
capturas, logs ni paquetes de evidencia. Las copias en host, contenedor y Laravel
deben coincidir. Los archivos de biometrias y artefactos entrenados son privados.

## Registro horario

El timer guarda cada ejecución con un nombre UTC exclusivo en `serving/prospective/`,
JSON 0600 y SHA256 separado, sin reemplazar emisiones anteriores. Conserva tres
proyecciones de crecimiento con huella, fuente y versión; respuesta del SVM OD
existente; última medición y última recepción de agua/luz; estado de calidad.
Consultar el SVM puede agregar un registro de pronóstico cuando exista un activo;
no entrena ni activa modelos. La captura no corrige relojes ni reescribe etiquetas.

Primera captura del 21/10/2026 22:25:22 UTC: los tres pronósticos ML respondieron
200. El SVM respondió 200 con `status=not_ready`, `reason=no_active_asset`:
**no había pronóstico de OD disponible**, aunque el transporte HTTP funcionó.
La fusión permanece bloqueada porque la alineación de relojes no está verificada,
el horizonte SVM es 1 h, faltan pronósticos diarios verificados y el modelo de peso
no tiene variables de sensores aprendidas. Un bloqueo registrado no es un dato
biométrico ni un pronóstico válido para entrenar. La última luz registrada sigue
siendo del 06/10; no se extrapola como si hubiera mediciones de luz hoy.

## Comprobaciones y límites

- 124 pruebas Python aprobadas, incluidas ausencia de clave, clave incorrecta y
  fallo cerrado cuando falta configuración. No equivalen a validación biológica.
- Compilación Vite completada; existen activos y manifiesto. Se conservaron activos
  antiguos para sesiones abiertas. Advertencia de tamaño de chunks del proyecto.
- Controlador y vista Blade ejecutados contra el modelo real: tres proyecciones,
  mismo SHA256 del artefacto y pesos observados de la base configurada.
- Dos rutas con sesión/permiso respondieron 200 mediante el kernel Laravel en una
  prueba interna con un usuario existente, sin cambiar cuentas ni credenciales.
  Sin sesión: página 302 al login y datos 401. Servicio 8013 sin clave: 401.
- Timer habilitado, primera captura terminada correctamente. El contenedor público
  Python mantiene su inicio del 18/10/2026; no se reinició para esta integración.
- Navegador externo: detenido por `ERR_CERT_COMMON_NAME_INVALID` al abrir la IP.
  No se eludió el certificado. No se afirma que exista una inspección visual
  completa autenticada. Una comprobación local con Playwright tampoco pudo arrancar
  porque su binario Chromium no está instalado.

## Reversión

Deshabilitar/detener `tilapia-growth-prospective.timer`; dejar intacto el archivo
prospectivo. Usar `panel_backup_20261021T222502Z/manifest.json` para identificar las
fuentes previas y las que antes no existían. Restaurar `routes/system/monitoreo.php`,
`ModelosMl.vue` y el manifiesto Vite original desde ese respaldo. Retirar solo los
dos archivos nuevos (controlador/vista) tras verificar que siguen siendo nuestros.
Limpiar caché de rutas/vistas. Los activos adicionales pueden conservarse.
Detener/deshabilitar el piloto adaptativo después de retirar su enlace. El piloto
v0.2, modelos previos y datos de la campaña no necesitan cambios.
