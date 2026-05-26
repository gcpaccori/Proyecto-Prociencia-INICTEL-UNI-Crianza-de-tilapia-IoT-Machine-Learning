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
    components = _component_catalog(models)
    integrable_components = [
        component
        for component in components
        if component["viability_status"] == "integrable"
    ]
    conditioned_components = [
        component
        for component in components
        if component["viability_status"] == "conditioned"
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
        "component_summary": {
            "total_components": len(components),
            "integrable_components": len(integrable_components),
            "implemented_components": len(integrable_components),
            "conditioned_components": len(conditioned_components),
            "executable_model_runners": len(models),
            "tested_model_runners_route": "/models/test-run-all",
            "components_route": "/frontend/components",
            "note": (
                "13 corresponde a runners ejecutables; 40 corresponde a "
                "componentes integrables de arquitectura, datos, formulas y ML."
            ),
        },
        "components": components,
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
            "components": "/frontend/components",
            "telemetry": "/telemetry/timeseries",
            "actuators": "/actuators",
        },
    }


@router.get("/frontend/components")
def list_frontend_components(
    catalog: ModelCatalogService = Depends(get_model_catalog_service),
) -> dict[str, object]:
    models = catalog.list_models()
    components = _component_catalog(models)
    integrable = [
        component
        for component in components
        if component["viability_status"] == "integrable"
    ]
    conditioned = [
        component
        for component in components
        if component["viability_status"] == "conditioned"
    ]
    return {
        "total_components": len(components),
        "integrable_components": len(integrable),
        "implemented_components": len(integrable),
        "conditioned_components": len(conditioned),
        "executable_model_runners": len(models),
        "components": components,
    }


def _component_catalog(models: list[object]) -> list[dict[str, object]]:
    model_by_code = {model.model_code: model for model in models}
    rows = [
        ("C01", "oxygen_water_quality", "Modelo dinamico 0D de oxigeno disuelto", "model_runner", "DO_DYNAMIC_0D_ROYER_2021"),
        ("C02", "oxygen_water_quality", "Modelo 1D de transporte de oxigeno disuelto", "model_runner", "DO_TRANSPORT_1D"),
        ("C03", "oxygen_water_quality", "Calculo de saturacion de oxigeno", "formula_core", None),
        ("C04", "oxygen_water_quality", "Balance de oxigeno RAS", "model_runner", "RAS_OXYGEN_BALANCE"),
        ("C05", "oxygen_water_quality", "Pipeline estadistico de calidad de agua", "algorithm", None),
        ("C06", "oxygen_water_quality", "Pearson-LSTM-AM para calidad de agua", "model_runner", "PEARSON_LSTM_ATTENTION_WQ"),
        ("C07", "oxygen_water_quality", "LSTM tradicional para calidad de agua", "trainable_component", None),
        ("C08", "oxygen_water_quality", "Pearson-LSTM para seleccion y forecast", "trainable_component", None),
        ("C09", "growth_bioenergetic", "Crecimiento lineal Soderberg", "model_runner", "SODERBERG_LINEAR_GROWTH"),
        ("C10", "growth_bioenergetic", "Regresiones Taylor por especie", "formula_core", None),
        ("C11", "growth_bioenergetic", "Relacion longitud-peso Tilapia del Nilo", "formula_core", None),
        ("C12", "growth_bioenergetic", "Modelo ambiental de crecimiento Yi", "model_runner", "YI_ENVIRONMENTAL_GROWTH"),
        ("C13", "growth_bioenergetic", "Modelo bioenergetico Brigolin", "model_runner", "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010"),
        ("C14", "growth_bioenergetic", "Modelo de racion diaria", "model_runner", "DAILY_RATION_MODEL"),
        ("C15", "growth_bioenergetic", "Tasa de alimentacion Haskell", "formula_core", None),
        ("C16", "growth_bioenergetic", "Indicadores zootecnicos", "model_runner", "ZOOTECHNIC_INDEXES"),
        ("C17", "growth_bioenergetic", "Reglas de saciedad alimentaria", "model_runner", "FEEDING_SATIETY_RULES"),
        ("C18", "growth_bioenergetic", "Analitica de alimentacion por fases", "algorithm", None),
        ("C19", "ml_tabular_statistics", "Regresion lineal de telemetria", "trainable_component", None),
        ("C20", "ml_tabular_statistics", "Regresion multiple de calidad de agua", "trainable_component", None),
        ("C21", "ml_tabular_statistics", "SVM para regresion/clasificacion", "trainable_component", None),
        ("C22", "ml_tabular_statistics", "Random Forest tabular", "trainable_component", None),
        ("C23", "ml_tabular_statistics", "Arboles de decision", "trainable_component", None),
        ("C24", "ml_tabular_statistics", "K-Means para agrupamiento", "trainable_component", None),
        ("C25", "ml_tabular_statistics", "PCA para reduccion dimensional", "trainable_component", None),
        ("C26", "ml_tabular_statistics", "KNN tabular", "trainable_component", None),
        ("C27", "ml_tabular_statistics", "SOM para mapas autoorganizados", "trainable_component", None),
        ("C28", "ml_tabular_statistics", "BPNN-MEA consumo de alimento", "model_runner", "BPNN_MEA_FEED_INTAKE"),
        ("C29", "ml_tabular_statistics", "Q-Learning para politica operativa simulada", "trainable_component", None),
        ("C30", "architecture_twin", "Contenedor FastAPI backend", "backend_module", None),
        ("C31", "architecture_twin", "Base MySQL aquaculture_digital_twin", "data_module", None),
        ("C32", "architecture_twin", "Sincronizacion legacy solo lectura", "data_module", None),
        ("C33", "architecture_twin", "Catalogo de modelos", "backend_module", None),
        ("C34", "architecture_twin", "Auditoria de inputs para formularios", "backend_module", None),
        ("C35", "architecture_twin", "Generador de payloads de prueba", "backend_module", None),
        ("C36", "architecture_twin", "Ejecucion global test-run-all", "backend_module", None),
        ("C37", "architecture_twin", "Estado del gemelo digital", "backend_module", None),
        ("C38", "architecture_twin", "Snapshots, riesgos y recomendaciones", "backend_module", None),
        ("C39", "architecture_twin", "Politica de actuacion", "backend_module", None),
        ("C40", "architecture_twin", "Dashboard agregado para frontend", "backend_module", None),
    ]
    conditioned = [
        ("C41", "conditioned_external", "CNN de segmentacion para roturas de malla", "external_dataset_required", None),
        ("C42", "conditioned_external", "CNN/I3D de saciedad por video subacuatico", "external_dataset_required", None),
        ("C43", "conditioned_external", "Comportamiento matematico de peces por tracking", "external_dataset_required", None),
        ("C44", "conditioned_external", "Distribucion de alimento por CFD y corrientes", "external_dataset_required", None),
        ("C45", "conditioned_external", "Modelo mecanistico predictivo de amoniaco", "formula_research_required", None),
    ]
    return [
        _component_item(code, family, title, kind, linked_model_code, model_by_code, "integrable")
        for code, family, title, kind, linked_model_code in rows
    ] + [
        _component_item(code, family, title, kind, linked_model_code, model_by_code, "conditioned")
        for code, family, title, kind, linked_model_code in conditioned
    ]


def _component_item(
    code: str,
    family: str,
    title: str,
    kind: str,
    linked_model_code: str | None,
    model_by_code: dict[str, object],
    viability_status: str,
) -> dict[str, object]:
    model = model_by_code.get(linked_model_code) if linked_model_code else None
    status = "conditioned_external_data" if viability_status == "conditioned" else "integrable"
    if model is not None:
        status = model.readiness_status
    implementation_status = (
        "conditioned_pending"
        if viability_status == "conditioned"
        else "implemented_backend"
    )
    implementation_ref = _implementation_ref(kind, linked_model_code)
    routes = {}
    if linked_model_code:
        routes = {
            "details": f"/models/{linked_model_code}",
            "input_audit": f"/models/{linked_model_code}/input-audit",
            "test_payload": f"/models/{linked_model_code}/test-payload",
            "test_run": f"/models/{linked_model_code}/test-run",
            "run": f"/models/{linked_model_code}/run",
        }
    return {
        "component_code": code,
        "family": family,
        "title": title,
        "kind": kind,
        "viability_status": viability_status,
        "implementation_status": implementation_status,
        "implementation_ref": implementation_ref,
        "backend_status": status,
        "linked_model_code": linked_model_code,
        "is_executable_model_runner": model is not None,
        "routes": routes,
    }


def _implementation_ref(kind: str, linked_model_code: str | None) -> str | None:
    if linked_model_code:
        return f"models_engine.runner.{linked_model_code}"
    refs = {
        "formula_core": "backend.app.models_engine.deterministic / bioenergetic",
        "algorithm": "backend.app.models_engine.ml.preprocessing",
        "trainable_component": "backend.app.models_engine.ml.tabular_algorithms / sequence_algorithms",
        "backend_module": "backend.app.api.v1 / application services",
        "data_module": "backend.app.application.mysql_store",
    }
    return refs.get(kind)


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
