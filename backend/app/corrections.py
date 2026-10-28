"""Authenticated quantity/price preview; saving belongs to task 7."""
from fastapi import APIRouter, Depends, HTTPException

from app import audit
from app.auth import current_user
from app.takeoff.corrections import (
    IncompatibleSnapshot, RecalculationRequest, RecalculationResponse, recalculate,
)

router = APIRouter(dependencies=[Depends(current_user)])


@router.post("/api/estimate/recalculate", response_model=RecalculationResponse)
def recalculate_estimate(request: RecalculationRequest):
    try:
        result = recalculate(request.original_input, request.corrections)
    except IncompatibleSnapshot as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, "Cannot recalculate these source inputs. " + str(exc)) from exc
    audit.record_estimate(result.estimate.plan_type, result.estimate, plan=result.effective_input.plan,
                          corrections=result.corrections.model_dump(mode="json"))
    return result
