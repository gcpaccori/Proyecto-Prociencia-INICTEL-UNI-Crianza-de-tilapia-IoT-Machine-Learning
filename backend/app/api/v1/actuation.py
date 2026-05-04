from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.v1.dependencies import get_store
from backend.app.application import InMemoryBackendStore
from backend.app.domains.actuation import (
    ActuationCommandDraft,
    ActuationCommandRequest,
    ActuationDecision,
    ActuationPolicyEngine,
    ActuatorCreate,
    ActuatorRead,
    ActuatorStatus,
)
from backend.app.models_engine.orchestrators.schemas import Recommendation

router = APIRouter()


@router.post("/actuators", response_model=ActuatorRead, status_code=status.HTTP_201_CREATED)
def create_actuator(
    payload: ActuatorCreate,
    store: InMemoryBackendStore = Depends(get_store),
) -> ActuatorRead:
    if store.get_farm(payload.farm_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="farm_id does not exist")
    if payload.pond_id is not None and store.get_pond(payload.pond_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pond_id does not exist")
    actuator = ActuatorRead(
        id=f"ACTUATOR-{uuid4()}",
        **payload.model_dump(),
    )
    try:
        return store.create_actuator(actuator)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/actuators", response_model=list[ActuatorRead])
def list_actuators(
    pond_id: str | None = Query(default=None),
    store: InMemoryBackendStore = Depends(get_store),
) -> list[ActuatorRead]:
    return store.list_actuators(pond_id=pond_id)


@router.get("/actuators/{actuator_id}", response_model=ActuatorRead)
def get_actuator(
    actuator_id: str,
    store: InMemoryBackendStore = Depends(get_store),
) -> ActuatorRead:
    actuator = store.get_actuator(actuator_id)
    if actuator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="actuator not found",
        )
    return actuator


@router.post("/actuation-commands/from-recommendation", response_model=ActuationDecision)
def create_command_from_recommendation(
    payload: ActuationCommandRequest,
    store: InMemoryBackendStore = Depends(get_store),
) -> ActuationDecision:
    recommendation = store.get_recommendation(payload.recommendation_code)
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="recommendation not found",
        )

    actuator_statuses = [
        ActuatorStatus(
            actuator_id=actuator.id,
            actuator_type=actuator.actuator_type,
            status=actuator.status,
            pond_id=actuator.pond_id,
            metadata=actuator.extra_metadata,
        )
        for actuator in store.list_actuators(pond_id=recommendation.pond_id)
    ]
    decision = ActuationPolicyEngine().evaluate(
        recommendation=Recommendation(
            recommendation_code=recommendation.recommendation_code,
            priority=recommendation.priority,
            recommended_action=recommendation.recommended_action,
            explanation=recommendation.explanation,
            approval_required=recommendation.approval_required,
            source_risk_code=recommendation.source_risk_code,
            evidence=recommendation.evidence,
        ),
        actuator_statuses=actuator_statuses,
        safety_policy=payload.safety_policy,
        user_approval=payload.user_approval,
    )
    if decision.command is None:
        return decision
    stored_command = store.save_command(decision.command)
    return decision.model_copy(update={"command": stored_command})


@router.get("/actuation-commands", response_model=list[ActuationCommandDraft])
def list_commands(
    store: InMemoryBackendStore = Depends(get_store),
) -> list[ActuationCommandDraft]:
    return store.list_commands()
