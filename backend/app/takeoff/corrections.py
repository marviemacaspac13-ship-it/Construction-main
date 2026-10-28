"""Rebuild from original inputs plus a complete set of absolute overrides.

Pure computation: no recognition, shared catalog access, or persistence. Removing
an override resets that field because every call starts from the original scan.
"""
import json

from app.takeoff.constants import RULES_VERSION
from app.takeoff.contracts import ContractModel, EstimateCorrections, EstimateInputSnapshot
from app.takeoff.estimator import EstimateResponse, estimate_plan
from app.takeoff.schema import FixtureCount, PlanSchema
from app.takeoff.units import UNIT_SPECS


class IncompatibleSnapshot(ValueError):
    pass


class RecalculationRequest(ContractModel):
    original_input: EstimateInputSnapshot
    corrections: EstimateCorrections


class RecalculationResponse(ContractModel):
    effective_input: EstimateInputSnapshot
    corrections: EstimateCorrections
    estimate: EstimateResponse


def _single_member(plan: PlanSchema, kind: str, expected_id: str):
    members = [e for e in plan.concrete if e.kind == kind]
    if not members and plan.source == "manual":
        basis = [e for e in plan.concrete_basis if e.kind == kind]
        if len(basis) == 1:
            members = [basis[0].model_copy(deep=True)]
            plan.concrete.extend(members)
    if len(members) != 1 or members[0].id != expected_id or not members[0].is_reinforceable:
        raise ValueError(f"Cannot correct {kind}: original needs one complete {expected_id} member group.")
    return members[0]


def recalculate(original: EstimateInputSnapshot, corrections: EstimateCorrections) -> RecalculationResponse:
    # Revalidate even Python callers: model_copy(update=...) bypasses validation.
    original = EstimateInputSnapshot.model_validate(original.model_dump())
    corrections = EstimateCorrections.model_validate(corrections.model_dump())
    json.dumps(original.model_dump(mode="json"), allow_nan=False)
    if original.rules_version != RULES_VERSION:
        raise IncompatibleSnapshot("The saved rules version is incompatible; rescan before correcting.")
    if any(row.purchase_unit != UNIT_SPECS.get(row.item_id) for row in original.prices.items):
        raise IncompatibleSnapshot("The saved purchase units are incompatible; rescan before correcting.")
    q = corrections.quantities
    effective = original.model_copy(deep=True)
    plan, params = effective.plan, effective.params
    floor_edit = any(v is not None for v in (q.wall_height_m, q.slab_area_m2, q.column_count))
    if floor_edit and plan.plan_type != "Floor Plan":
        raise ValueError("Wall, slab and column corrections require a Floor Plan.")
    if q.electrical_counts and plan.plan_type != "Electrical Plan":
        raise ValueError("Electrical counts require an Electrical Plan.")
    if q.plumbing_counts and plan.plan_type != "Plumbing Plan":
        raise ValueError("Plumbing counts require a Plumbing Plan.")

    if q.wall_height_m is not None:
        if not plan.walls:
            raise ValueError("Cannot correct wall height without original wall lengths.")
        params.default_wall_height_m = q.wall_height_m
        # The override is explicitly project-wide, including previously explicit heights.
        for wall in plan.walls:
            wall.height_m = q.wall_height_m

    if q.slab_area_m2 is not None:
        slab = _single_member(plan, "slab", "slab_on_grade")
        if q.slab_area_m2 == 0:
            plan.concrete.remove(slab)
        else:
            slab.slab_area_m2 = q.slab_area_m2
            slab.volume_m3 = q.slab_area_m2 * slab.height_m

    if q.column_count is not None:
        columns = _single_member(plan, "column", "columns")
        footings = _single_member(plan, "footing", "footings")
        if columns.count != footings.count:
            raise ValueError("Original columns and linked footings have different counts.")
        for member in (columns, footings):
            if q.column_count == 0:
                plan.concrete.remove(member)
            else:
                member.count = q.column_count
                member.volume_m3 = member.count * member.width_m * member.length_m * member.height_m
                member.counted = False
        plan.manual_column_count = q.column_count

    if q.electrical_counts:
        # Replace the aggregate for each edited SKU, even if the original has
        # several detection groups. Preserve unrelated and unresolved entries.
        plan.fixtures = [f for f in plan.fixtures if f.item_id not in q.electrical_counts]
        plan.fixtures.extend(FixtureCount(item_id=k, count=v) for k, v in sorted(q.electrical_counts.items()))
    plan.fixture_tags.update(q.plumbing_counts)

    # Price-only edits rerun the same quantity engine with unchanged plan/params.
    # Copy the captured catalog; never consult or modify the shared live catalog.
    effective.prices = original.prices.with_overrides(corrections.unit_prices)
    # Validate rebuilt geometry and the hash of the effective price snapshot.
    effective = EstimateInputSnapshot.model_validate(effective.model_dump())
    estimate = estimate_plan(effective.plan, effective.prices.to_catalog(), effective.params)
    json.dumps(estimate.model_dump(mode="json"), allow_nan=False)
    return RecalculationResponse(effective_input=effective, corrections=corrections, estimate=estimate)
