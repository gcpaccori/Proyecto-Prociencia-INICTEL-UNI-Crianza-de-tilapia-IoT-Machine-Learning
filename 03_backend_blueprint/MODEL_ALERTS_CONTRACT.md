# Contrato local de alertas de modelos

`GET /api/v1/ponds/{pond_id}/model-alerts/dashboard?window_hours=24` es el contrato que consume Laravel para el modulo de alarmas de modelos.

La solicitud retorna inmediatamente. Cuando el resultado no esta en cache, FastAPI inicia el calculo pesado de limpieza, series temporales y modelos en un worker local. La primera respuesta contiene `meta.warming=true`; Laravel la vuelve a consultar a los tres segundos. Asi la vista no espera el entrenamiento, la sincronizacion MySQL ni el dashboard completo y evita los tiempos de espera HTTP.

El resultado incluye exactamente cuatro tarjetas: ICA, crecimiento por temperatura, SVR de OD a una hora y luz/respuesta alimentaria. Conserva las formulas, graficos y trazabilidad producidos por `RealModelsService`; no fabrica series ni predicciones.

## Politicas y eventos

FastAPI solo consulta `sismapiscis.model_alert_policies` en modo de lectura. La tabla y sus aprobaciones pertenecen a Laravel.

Un evento tiene `productive=true` solo cuando:

1. El modelo esta realmente habilitado para uso productivo. Para SVM, el activo debe superar los criterios ya guardados frente a persistencia.
2. Existe una politica con `status=approved` para el modelo y la piscina o una politica global.
3. La proyeccion cumple su operador (`lt`, `lte`, `gt`, `gte`) y umbral.

Las observaciones tecnicas, los candidatos SVM, las proyecciones de crecimiento en modo sombra y los escenarios manuales de luz siempre se devuelven sin evento productivo. Laravel deduplica los eventos mediante `source_event_id` antes de crear una fila en `alarmas`.

La luz solo puede pasar a produccion despues de disponer de sensor real, etiquetas de racion/respuesta, entrenamiento validado y politica aprobada. Mientras tanto, la tarjeta muestra su estado de datos y el gemelo puede usar un escenario manual que no genera alertas.
