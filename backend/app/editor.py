"""Owner-authorized editor previews and immutable saves. Clients never supply totals."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app import audit
from app.auth import current_user
from app.materials import load_catalog
from app.revisions import rpc, require_revision_storage
from app.takeoff.contracts import (ContractModel, EstimateCorrections, EstimateInputSnapshot,
    PriceSnapshot, RevisionSavePrecondition, SourceQuantityOverrides, snapshot_catalog)
from app.takeoff.corrections import IncompatibleSnapshot, recalculate
from app.takeoff.frame import derive_frame
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import Opening, PlanSchema, Wall
from app.takeoff.constants import DEFAULT_DOOR_M, DEFAULT_WINDOW_M

router = APIRouter(dependencies=[Depends(current_user), Depends(require_revision_storage)])


class EditorRequest(ContractModel):
    project_id: UUID
    scan_revision_id: UUID
    corrections: EstimateCorrections


class EditorSaveRequest(EditorRequest):
    precondition: RevisionSavePrecondition


def compute(original, corrections):
    try:
        return recalculate(original, corrections)
    except IncompatibleSnapshot as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc


def owned_result(request, owner):
    scan = rpc('owned_estimate_scan', {'p_owner':owner,'p_project_id':str(request.project_id),
                                     'p_scan_id':str(request.scan_revision_id)})
    return compute(EstimateInputSnapshot.model_validate(scan['original_input']), request.corrections)


@router.post('/api/estimate/editor/preview')
def preview(request: EditorRequest, owner: str = Depends(current_user)):
    return owned_result(request, owner)


@router.post('/api/estimate/editor/revisions')
def save(request: EditorSaveRequest, owner: str = Depends(current_user)):
    result = owned_result(request, owner)
    revision = rpc('save_corrected_estimate', {
        'p_owner':owner, 'p_project_id':str(request.project_id), 'p_scan_id':str(request.scan_revision_id),
        'p_expected_active_revision_id':str(request.precondition.expected_active_revision_id) if request.precondition.expected_active_revision_id else None,
        'p_idempotency_key':str(request.precondition.idempotency_key),
        'p_corrections':result.corrections.model_dump(mode='json'),
        'p_effective_input':result.effective_input.model_dump(mode='json'), 'p_estimate':result.estimate.model_dump(mode='json'),
    })
    audit.record_estimate(result.estimate.plan_type,result.estimate,plan=result.effective_input.plan,
                          corrections=result.corrections.model_dump(mode='json'))
    return {'revision_id':revision}


Positive = Annotated[float, Field(gt=0, le=10000, strict=True, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, le=10000, strict=True, allow_inf_nan=False)]


class ManualInputs(ContractModel):
    quantities: SourceQuantityOverrides
    width_m: Positive | None = None
    length_m: Positive | None = None
    exterior_wall_m: Nonnegative | None = None
    interior_wall_m: Nonnegative | None = None
    doors: Annotated[int, Field(ge=0, strict=True)] | None = None
    windows: Annotated[int, Field(ge=0, strict=True)] | None = None
    confirmed: bool = Field(False, strict=True)


class ManualRequest(ContractModel):
    project_id: UUID
    asset_id: UUID
    inputs: ManualInputs
    # Returned by preview, retained for retry so a changing catalog cannot alter a save.
    prices: PriceSnapshot | None = None


class ManualSaveRequest(ManualRequest):
    precondition: RevisionSavePrecondition


def manual_result(request, owner):
    context = rpc('manual_estimate_context', {'p_owner':owner,'p_project_id':str(request.project_id),'p_asset_id':str(request.asset_id)})
    if not context['asset'].get('storage_path'):
        raise HTTPException(422, 'Upload the original plan before entering a manual estimate.')
    i, trade = request.inputs, context['plan_type']
    if not i.confirmed:
        raise HTTPException(422,'Confirm that you checked the entered quantities against the original plan.')
    params = EstimatingParams()
    plan = PlanSchema(plan_type=trade,source='manual')
    if trade == 'Floor Plan':
        if any(v is None for v in (i.width_m,i.length_m,i.exterior_wall_m,i.interior_wall_m,i.doors,i.windows,
                                   i.quantities.wall_height_m,i.quantities.slab_area_m2,i.quantities.column_count)):
            raise HTTPException(422,'Enter every floor-plan measurement and count; enter zero only for confirmed exclusions.')
        if i.exterior_wall_m + i.interior_wall_m <= 0:
            raise HTTPException(422,'Enter at least one wall length.')
        for name, length, thickness in [('exterior',i.exterior_wall_m,'6in'),('interior',i.interior_wall_m,'4in')]:
            if length:
                plan.walls.append(Wall(id=name,length_m=length,thickness=thickness))
        # Apply standard opening dimensions to one aggregate wall, explicitly entered counts.
        wall = plan.walls[0]
        if i.doors: wall.openings.append(Opening(kind='door',width_m=DEFAULT_DOOR_M[0],height_m=DEFAULT_DOOR_M[1],count=i.doors))
        if i.windows: wall.openings.append(Opening(kind='window',width_m=DEFAULT_WINDOW_M[0],height_m=DEFAULT_WINDOW_M[1],count=i.windows))
        if wall.opening_area_m2 > wall.length_m * i.quantities.wall_height_m:
            raise HTTPException(422,'Opening deductions exceed the entered exterior wall area. Review lengths and opening counts.')
        plan.concrete = derive_frame(i.width_m,i.length_m,params).elements
        plan.concrete_basis = [e.model_copy(deep=True) for e in plan.concrete]
    else:
        if any(v is not None for v in (i.width_m,i.length_m,i.exterior_wall_m,i.interior_wall_m,i.doors,i.windows)):
            raise HTTPException(422,'Floor geometry does not apply to this trade.')
        counts = i.quantities.electrical_counts if trade == 'Electrical Plan' else i.quantities.plumbing_counts
        if not counts:
            raise HTTPException(422,'Enter at least one confirmed fixture count, including zero where intentional.')
    prices = request.prices or snapshot_catalog(load_catalog(), datetime.now(timezone.utc).isoformat())
    original = EstimateInputSnapshot(plan=plan,params=params,prices=prices)
    result = compute(original,EstimateCorrections(quantities=i.quantities))
    # Manual inputs constitute a new source revision, not a correction of a failed read.
    original = result.effective_input
    result = compute(original,EstimateCorrections())
    result.estimate.priced_at = prices.captured_at.isoformat()
    return context, result


@router.post('/api/estimate/manual/preview')
def preview_manual(request: ManualRequest, owner: str = Depends(current_user)):
    _, result = manual_result(request, owner)
    return result


@router.post('/api/estimate/manual/revisions')
def save_manual(request: ManualSaveRequest, owner: str = Depends(current_user)):
    if request.prices is None:
        raise HTTPException(422,'Recalculate and review before saving manual inputs.')
    context, result = manual_result(request,owner)
    asset = context['asset']
    payload = {'original_input':result.effective_input.model_dump(mode='json'),
        'estimate':result.estimate.model_dump(mode='json'),'extraction':None,'unmatched_detections':[],
        'scan':{'source_sha256':asset['source_sha256'],'pipeline_version':'image-v1','method':'manual'}}
    metadata = {k:asset[k] for k in ('source_sha256','original_filename','media_type','byte_size')}
    metadata['asset_id'] = str(request.asset_id)
    revision = rpc('save_scan_estimate', {'p_owner':owner,'p_project_id':str(request.project_id),
        'p_expected_active_revision_id':str(request.precondition.expected_active_revision_id) if request.precondition.expected_active_revision_id else None,
        'p_idempotency_key':str(request.precondition.idempotency_key),'p_result':payload,'p_asset':metadata})
    audit.record_estimate(result.estimate.plan_type,result.estimate,plan=result.effective_input.plan)
    return {'revision_id':revision}
