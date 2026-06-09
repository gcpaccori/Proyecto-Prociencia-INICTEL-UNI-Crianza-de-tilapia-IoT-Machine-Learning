# Resumen maestro de actualización full stack

Fuente revisada: `directiva de actualizacioopn.md`.

## Objetivo central

AquaTwin Studio debe dejar de mostrar módulos estáticos o aislados y convertirse en una plataforma operable por productores técnicos: datos reales, copias de trabajo, limpieza explicada, preparación de features, entrenamiento comprobable, catálogo dinámico de modelos y un gemelo digital que permita comparar escenarios sobre gráficos horarios.

## Requisitos consolidados

### Resumen

- No debe preseleccionar ni imponer un modelo central.
- Debe mostrar el estado operativo del ciclo completo.
- Sus botones deben navegar a acciones reales.
- No debe repetir pipeline ni trazabilidad como decoración.

Aplicación: el Resumen operativo muestra datos, limpiezas, feature sets, entrenamientos, artefactos activos y acceso directo al Gemelo Digital.

### Datos

- Debe trabajar con una copia actualizada de la base operativa.
- No debe modificar los datos originales.
- Debe explicar variables, cobertura y utilidad.
- La comprobación de requisitos debe usar el catálogo dinámico de modelos.

Aplicación: la UI denomina el proceso “Actualizar copia desde base operativa”, muestra registros copiados, variables utilizables y requisitos por modelo.

### Limpieza

- Debe explicar qué hace cada técnica.
- Cada limpieza debe quedar versionada y trazable.
- Debe mostrar entrada, salida, outliers, interpolados y normalizados.

Aplicación: se mantienen interpolación lineal, regla 3 sigma, MinMax y persistencia por `cleaning_run_id`.

### Features

- Debe explicar target, variables predictoras, ventana, horizonte y particiones.
- Debe relacionarse con una limpieza concreta.

Aplicación: el builder y detalle de feature sets permanecen operativos y versionados.

### Entrenamiento

- Debe explicar opciones e hiperparámetros.
- Debe mostrar etapas y detalle del job seleccionado.
- Debe separar entrenamiento, validación y publicación del artefacto.

Aplicación: launcher, autorrelleno, estados de job, eventos, métricas y artefactos continúan separados.

### Modelos ML

- El catálogo debe salir del backend y de entrenamientos/artefactos reales.
- Debe mostrar versión, propósito, tipo, trazabilidad, datos requeridos y origen de datos.
- Debe distinguir datos reales de datos generados para prueba.
- Los gráficos deben usar tiempo cuando exista información temporal.

Aplicación: catálogo dinámico, lifecycle backend, artefactos, readiness, inferencia guiada e historial de predicciones.

### Gemelo digital

- Debe funcionar como clon virtual del estanque.
- Debe combinar varios modelos activables o desactivables.
- Debe permitir modificar condiciones y comparar el comportamiento.
- Los gráficos deben trabajar en horas.
- Debe indicar qué modelos afectan cada variable y mostrar trazabilidad.

Aplicación:

- Nueva ruta `POST /digital-twin/{pond_id}/projection`.
- Nueva pantalla `Gemelo digital`.
- Horizonte configurable de 12, 24, 48 o 72 horas.
- Modelos activables/desactivables.
- Ajustes explícitos por variable y hora.
- Curvas temporales para oxígeno disuelto, temperatura, pH y nitrato.
- Tabla de injerencia, disponibilidad, artefacto activo y advertencias.

## Regla científica aplicada

La proyección temporal nueva parte de `clean_measurements`, calcula tendencia observada y aplica solamente ajustes explícitos del operador. No inventa ecuaciones de modelos no documentadas.

La respuesta identifica:

- origen real de datos;
- tendencia observada;
- ajuste de escenario;
- modelos seleccionados;
- disponibilidad del runner o artefacto;
- advertencia de que el escenario operacional no sustituye inferencia científica productiva.

## Estado resultante

- Resumen operativo: implementado.
- Datos y copia de trabajo: implementado.
- Limpieza explicada y versionada: implementado.
- Features versionadas: implementado.
- Entrenamiento y artefactos: implementado.
- Modelos ML comprobables: implementado.
- Gemelo Digital horario interactivo: implementado.
- Despliegue y verificación pública: pendiente de publicación de esta actualización.
