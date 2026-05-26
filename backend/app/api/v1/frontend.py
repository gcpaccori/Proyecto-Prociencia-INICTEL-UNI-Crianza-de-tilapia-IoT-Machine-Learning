from fastapi import APIRouter, Depends, Query, Request

from backend.app.api.v1.dependencies import get_model_catalog_service, get_store
from backend.app.application import InMemoryBackendStore, ModelCatalogService

router = APIRouter()


@router.get("/frontend/dashboard")
def get_frontend_dashboard(
    request: Request,
    farm_id: str | None = Query(default=None),
    pond_id: str | None = Query(default=None),
    range_label: str = Query(default="Ultimas 24 horas"),
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
    store: InMemoryBackendStore = Depends(get_store),
) -> dict[str, object]:
    farms = store.list_farms()
    ponds = store.list_ponds(farm_id=farm_id)
    selected_pond_id = pond_id or (ponds[0].id if ponds else None)
    latest = store.latest_clean_by_variable(selected_pond_id) if selected_pond_id else {}
    clean_rows = (
        store.list_clean_measurements(pond_id=selected_pond_id, limit=5000)
        if selected_pond_id
        else []
    )
    sensors = store.list_sensors(pond_id=selected_pond_id) if selected_pond_id else []
    actuators = store.list_actuators(pond_id=selected_pond_id) if selected_pond_id else []
    models = catalog.list_models()
    audits = {
        model.model_code: catalog.audit_inputs(
            model.model_code,
            store,
            pond_id=selected_pond_id,
        )
        for model in models
    }
    outputs = store.list_model_outputs(limit=20)
    latest_snapshot = store.latest_snapshot(selected_pond_id) if selected_pond_id else None
    alerts = store.list_alerts(pond_id=selected_pond_id) if selected_pond_id else []
    recommendations = (
        store.list_recommendations(pond_id=selected_pond_id) if selected_pond_id else []
    )
    variables = sorted({row.variable_code for row in clean_rows})
    ready_models = [model for model in models if model.readiness_status == "ready"]
    artifact_models = [
        model for model in models if model.readiness_status == "requires_external_artifact"
    ]
    generated_ready = sum(
        1
        for audit in audits.values()
        if audit is not None and audit.frontend_status in {"needs_form_inputs", "ready"}
    )

    settings = request.app.state.settings
    return {
        "backend": {
            "status": "online",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
        "selection": {
            "farm_id": farm_id,
            "pond_id": selected_pond_id,
            "range_label": range_label,
        },
        "farms": [farm.model_dump(mode="json") for farm in farms],
        "ponds": [pond.model_dump(mode="json") for pond in ponds],
        "system_metrics": {
            "farms": len(farms),
            "ponds": len(ponds),
            "sensors": len(sensors),
            "actuators": len(actuators),
            "clean_measurements_loaded": len(clean_rows),
            "variables": len(variables),
        },
        "project_map": _project_map(models),
        "model_summary": {
            "total": len(models),
            "ready": len(ready_models),
            "requires_external_artifact": len(artifact_models),
            "test_payload_enabled": len(models),
            "test_run_ready_or_generated": generated_ready,
        },
        "models": [
            {
                **model.model_dump(mode="json"),
                "audit": audits[model.model_code].model_dump(mode="json")
                if audits[model.model_code]
                else None,
                "routes": {
                    "details": f"/models/{model.model_code}",
                    "input_audit": f"/models/{model.model_code}/input-audit",
                    "test_payload": f"/models/{model.model_code}/test-payload",
                    "test_run": f"/models/{model.model_code}/test-run",
                    "run": f"/models/{model.model_code}/run",
                },
            }
            for model in models
        ],
        "water_quality_current": {
            variable_code: row.model_dump(mode="json")
            for variable_code, row in latest.items()
        },
        "timeseries": {
            "default_route": "/telemetry/timeseries",
            "variables": variables,
            "recommended_limit": 288,
        },
        "digital_twin": {
            "latest_snapshot_id": latest_snapshot.snapshot_id if latest_snapshot else None,
            "risk_count": len(latest_snapshot.risk_assessments) if latest_snapshot else 0,
            "recommendation_count": len(recommendations),
            "alert_count": len(alerts),
            "routes": {
                "state": f"/ponds/{selected_pond_id}/state" if selected_pond_id else None,
                "snapshot": f"/digital-twin/{selected_pond_id}/snapshot"
                if selected_pond_id
                else None,
                "risks": f"/digital-twin/{selected_pond_id}/risks"
                if selected_pond_id
                else None,
                "recommendations": f"/digital-twin/{selected_pond_id}/recommendations"
                if selected_pond_id
                else None,
            },
        },
        "evidence": {
            "scenarios": len(outputs),
            "reports": 1 if latest_snapshot else 0,
            "models": len(models),
            "datasets": len(variables),
            "charts": len(clean_rows),
        },
        "traceability": [
            {
                "run_id": output.run_id,
                "model_code": output.model_code,
                "model_version": output.model_version,
                "source_report": output.source_report,
                "status": "completed" if not output.warnings else "completed_with_warnings",
                "warnings": output.warnings,
                "outputs": list(output.outputs),
                "traceability": output.traceability,
            }
            for output in outputs
        ],
        "frontend_contract_routes": {
            "health": "/health",
            "dashboard": "/frontend/dashboard",
            "models": "/models",
            "test_run_all": "/models/test-run-all",
            "telemetry": "/telemetry/timeseries",
            "actuators": "/actuators",
        },
    }


def _project_map(models: list[object]) -> list[dict[str, object]]:
    ready_codes = {model.model_code for model in models if model.readiness_status == "ready"}
    artifact_codes = {
        model.model_code
        for model in models
        if model.readiness_status == "requires_external_artifact"
    }
    return [
        {
            "order": 1,
            "title": "Contenedor informatico / Arquitectura web",
            "status": "IMPLEMENTADO",
            "backend_status": "ready",
        },
        {
            "order": 2,
            "title": "Modelos de regresion ML en Python",
            "status": "EN PRUEBA" if artifact_codes else "VALIDADO",
            "backend_status": "requires_artifacts" if artifact_codes else "ready",
        },
        {
            "order": 3,
            "title": "Modelos de arboles de decision",
            "status": "EN PRUEBA",
            "backend_status": "contract_ready",
        },
        {
            "order": 4,
            "title": "Analisis e interpretacion estadistica",
            "status": "VALIDADO",
            "backend_status": "ready",
        },
        {
            "order": 5,
            "title": "Modelo matematico de oxigeno disuelto",
            "status": "LISTO"
            if "DO_DYNAMIC_0D_ROYER_2021" in ready_codes
            else "EN PRUEBA",
            "backend_status": "ready",
        },
        {
            "order": 6,
            "title": "Modelo de crecimiento de peces",
            "status": "LISTO"
            if "YI_ENVIRONMENTAL_GROWTH" in ready_codes
            else "EN PRUEBA",
            "backend_status": "ready",
        },
        {
            "order": 7,
            "title": "Gemelo digital aplicado al crecimiento de peces",
            "status": "IMPLEMENTADO",
            "backend_status": "ready_with_generated_tests",
        },
    ]
