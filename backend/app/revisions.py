"""Validated revision persistence. No recognition or new correction semantics here."""
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from postgrest.exceptions import APIError

from app.auth import current_user
from app.extract.report import ImageEstimateResponse
from app.materials import _client
from app.takeoff.constants import RULES_VERSION
from app.takeoff.contracts import ContractModel, RevisionSavePrecondition
from app.takeoff.estimator import estimate_plan
from app.takeoff.units import UNIT_SPECS

router = APIRouter(dependencies=[Depends(current_user)])


class AssetMetadata(ContractModel):
    asset_id: UUID | None = None
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    byte_size: Annotated[int, Field(strict=True, gt=0)]


class SaveScanRequest(ContractModel):
    project_id: UUID
    precondition: RevisionSavePrecondition
    result: ImageEstimateResponse
    asset: AssetMetadata

    @model_validator(mode="after")
    def consistent(self):
        if self.asset.source_sha256 != self.result.scan.source_sha256:
            raise ValueError("asset checksum differs from scan")
        if self.result.estimate.plan_type != self.result.original_input.plan.plan_type:
            raise ValueError("estimate and input plan types differ")
        if self.result.estimate.rules_version != self.result.original_input.rules_version:
            raise ValueError("estimate and input rules versions differ")
        review = self.result.original_input.plan.electrical_review
        if review is not None:
            if review.source_sha256 != self.result.scan.source_sha256:
                raise ValueError('electrical review and source checksums differ')
            from collections import Counter
            counts = Counter()
            for fixture in self.result.original_input.plan.fixtures:
                counts[fixture.item_id] += fixture.count
            if +counts != Counter(review.priced_counts()):
                raise ValueError('original electrical counts differ from reviewed assemblies')
        return self


# Set ESTIMATE_INPUT_SECRET for multiple workers; an in-process key works for one
# worker, at the cost that a restart between scan and save asks for a rescan.
_LOCAL_INPUT_SECRET = secrets.token_bytes(32)


def sign_original_input(snapshot, source_sha256: str, owner: str) -> str:
    """Bind a scan's original input to the user and image it was read for."""
    key = os.environ["ESTIMATE_INPUT_SECRET"].encode() if os.getenv("ESTIMATE_INPUT_SECRET") else _LOCAL_INPUT_SECRET
    body = json.dumps({"owner": owner, "source_sha256": source_sha256,
                       "original_input": snapshot.model_dump(mode="json")},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hmac.new(key, b"trace-original-input-v1" + body.encode(), hashlib.sha256).hexdigest()


class ScanFailureRequest(ContractModel):
    project_id: UUID
    message: str = Field(min_length=1, max_length=2000)


def require_revision_storage():
    if os.getenv("ESTIMATE_REVISIONS_ENABLED", "").lower() != "true":
        raise HTTPException(503, "Estimate saving is not configured yet. Your computed result is retained in this tab; retry after storage is enabled.")


def rpc(name: str, args: dict):
    try:
        return _client().rpc(name, args).execute().data
    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(404, "Project not found.") from exc
        if exc.code in ("PT409", "40001", "23505"):
            raise HTTPException(409, "This save conflicts with another revision. Open the saved project before starting a new scan.") from exc
        if exc.code == "22023":
            raise HTTPException(422, "The saved plan or estimate inputs are inconsistent. Re-upload the plan before saving.") from exc
        # Never expose SQL, keys or PostgREST internals in a browser error.
        raise HTTPException(503, "Could not save the estimate. Retry saving; the previous result is unchanged.") from exc
    except Exception as exc:
        raise HTTPException(503, "Could not reach estimate storage. Retry saving.") from exc


@router.post("/api/estimate/revisions", dependencies=[Depends(require_revision_storage)])
def save_scan(request: SaveScanRequest, owner: str = Depends(current_user)):
    snapshot = request.result.original_input
    if snapshot.plan.electrical_review is not None and snapshot.plan.electrical_review.owner_id != owner:
        raise HTTPException(422, 'Electrical review belongs to another owner.')
    if snapshot.rules_version != RULES_VERSION:
        raise HTTPException(409, "The estimating rules changed. Rescan with the current backend before saving.")
    # Machine purchase units affect rounding. A historical incompatible unit
    # snapshot must not silently replay with the current implementation.
    if any(row.purchase_unit != UNIT_SPECS.get(row.item_id) for row in snapshot.prices.items):
        raise HTTPException(409, "Purchase units changed. Rescan before saving.")
    expected = sign_original_input(snapshot, request.result.scan.source_sha256, owner)
    if not hmac.compare_digest(request.result.input_signature or "", expected):
        raise HTTPException(422, "This scan result could not be verified as unchanged. Rescan before saving.")
    computed = estimate_plan(snapshot.plan, snapshot.prices.to_catalog(), snapshot.params)
    submitted = request.result.estimate
    if computed.model_dump(exclude={"priced_at"}) != submitted.model_dump(exclude={"priced_at"}):
        raise HTTPException(422, "The estimate does not match its captured inputs. Rescan before saving.")
    try:
        same_pricing_time = snapshot.prices.captured_at == datetime.fromisoformat(submitted.priced_at.replace("Z", "+00:00"))
    except ValueError:
        same_pricing_time = False
    if not same_pricing_time:
        raise HTTPException(422, "The estimate and price snapshot timestamps differ.")
    revision_id = rpc("save_scan_estimate", {
        "p_owner": owner, "p_project_id": str(request.project_id),
        "p_expected_active_revision_id": (
            str(request.precondition.expected_active_revision_id)
            if request.precondition.expected_active_revision_id else None
        ),
        "p_idempotency_key": str(request.precondition.idempotency_key),
        "p_result": request.result.model_dump(mode="json"),
        "p_asset": request.asset.model_dump(mode="json", exclude_none=True),
    })
    return {"revision_id": revision_id}


@router.post("/api/estimate/scan-failure", dependencies=[Depends(require_revision_storage)])
def record_failure(request: ScanFailureRequest, owner: str = Depends(current_user)):
    rpc("record_scan_failure", {
        "p_owner": owner, "p_project_id": str(request.project_id), "p_message": request.message,
    })
    return {"recorded": True}
