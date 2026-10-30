"""Versioned inputs and correction records for reproducible estimates.

The image endpoint returns an original input snapshot. takeoff.corrections
rebuilds source quantities; revisions persists original scan results. Saving
corrected previews and editing them in the UI remain task 7.
"""

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.takeoff.constants import RULES_VERSION
from app.takeoff.estimator import EstimateResponse
from app.takeoff.params import EstimatingParams
from app.takeoff.schema import PlanSchema
from app.takeoff.units import UNIT_SPECS, UnitSpec

INPUT_SCHEMA_VERSION = 1
IMAGE_PIPELINE_VERSION = "image-v1"

NonNegativeNumber = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, strict=True)]
UnitPriceOverride = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
ElectricalDeviceId = Literal[
    "GS01", "GS02", "GS03", "SW01", "SW02", "SW03",
    "OT01", "OT02", "OT03", "ACO01", "CLR01", "CLR02", "CLR03",
]
PlumbingFixtureTag = Literal[
    "water_closet", "lavatory", "urinal", "floor_drain", "cleanout",
    "kitchen_sink", "shower", "bathtub", "washing_machine", "hose_bib", "drinking_fountain",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CatalogPrice(ContractModel):
    """Keep display units and machine-readable purchase units separately."""

    item_id: str
    item_name: str
    unit: str | None
    price: NonNegativeNumber
    category: str
    purchase_unit: UnitSpec | None


class PriceSnapshot(ContractModel):
    # Content hash excludes captured_at: identical catalogs share an ID.
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: AwareDatetime
    currency: Literal["PHP"] = "PHP"
    items: list[CatalogPrice]

    @model_validator(mode="after")
    def unique_items(self) -> "PriceSnapshot":
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("price snapshot contains duplicate item IDs")
        if self.snapshot_id != _catalog_hash(self.items):
            raise ValueError("price snapshot content does not match its ID")
        return self

    def to_catalog(self) -> dict[str, dict]:
        """Replay pricing without consulting the current shared catalog."""
        return {
            item.item_id: item.model_dump(exclude={"purchase_unit"})
            for item in self.items
        }

    def with_overrides(self, unit_prices: dict[str, float]) -> "PriceSnapshot":
        """Project-local prices with unchanged catalog metadata and purchase units.

        captured_at remains the base catalog's capture time; the correction
        record and estimate timestamp describe the edit. Missing rows cannot be
        invented from a price alone (their names/units would be unknown).
        """
        validated = EstimateCorrections(unit_prices=unit_prices).unit_prices
        missing = set(validated) - {item.item_id for item in self.items}
        if missing:
            raise ValueError("Price override items are missing from the captured catalog: "
                             + ", ".join(sorted(missing)))
        # Revalidation also detects a mutated or inconsistent source snapshot.
        result = PriceSnapshot.model_validate(self.model_dump()).model_copy(deep=True)
        for item in result.items:
            if item.item_id in validated:  # zero is an intentional price
                item.price = validated[item.item_id]
        result.snapshot_id = _catalog_hash(result.items)
        return PriceSnapshot.model_validate(result.model_dump())


def _catalog_hash(items: list[CatalogPrice]) -> str:
    content = json.dumps(
        [item.model_dump(mode="json") for item in sorted(items, key=lambda item: item.item_id)],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def snapshot_catalog(catalog: dict[str, dict], captured_at: str) -> PriceSnapshot:
    """Capture all rows so later edits can introduce a previously unused SKU."""
    items = [
        CatalogPrice(
            item_id=item_id, item_name=row["item_name"], unit=row.get("unit"),
            price=row["price"], category=row["category"],
            purchase_unit=UNIT_SPECS.get(item_id),
        )
        for item_id, row in sorted(catalog.items())
    ]
    return PriceSnapshot(
        snapshot_id=_catalog_hash(items), captured_at=captured_at, items=items,
    )


class EstimateInputSnapshot(ContractModel):
    """Exact rule-engine inputs, not a rounded extraction report."""

    schema_version: Literal[1] = INPUT_SCHEMA_VERSION
    rules_version: str = RULES_VERSION
    plan: PlanSchema
    params: EstimatingParams
    prices: PriceSnapshot


class ScanMetadata(ContractModel):
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pipeline_version: Literal["image-v1"] = IMAGE_PIPELINE_VERSION
    method: Literal["ocr", "tags", "detection", "manual"]


class SourceQuantityOverrides(ContractModel):
    """Absolute replacement values. None/absent means no override.

    Zero intentionally excludes the corresponding component. Counts describe
    existing SKU/tag semantics, not newly verified PEC classifications.
    """

    wall_height_m: Annotated[float, Field(gt=0, le=10, allow_inf_nan=False, strict=True)] | None = None
    slab_area_m2: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)] | None = None
    column_count: Count | None = None
    electrical_counts: dict[ElectricalDeviceId, Count] = Field(default_factory=dict)
    plumbing_counts: dict[PlumbingFixtureTag, Count] = Field(default_factory=dict)


class EstimateCorrections(ContractModel):
    quantities: SourceQuantityOverrides = Field(default_factory=SourceQuantityOverrides)
    unit_prices: dict[str, UnitPriceOverride] = Field(default_factory=dict)
    reason: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def known_price_items(self) -> "EstimateCorrections":
        unknown = set(self.unit_prices) - UNIT_SPECS.keys()
        if unknown:
            raise ValueError(f"unsupported price item IDs: {', '.join(sorted(unknown))}")
        return self


class EstimateRevision(ContractModel):
    """Proposed saved output; append-only enforcement belongs in Postgres."""

    id: UUID
    scan_revision_id: UUID
    parent_revision_id: UUID | None = None
    created_by: UUID
    created_at: AwareDatetime
    corrections: EstimateCorrections = Field(default_factory=EstimateCorrections)
    effective_input: EstimateInputSnapshot
    estimate: EstimateResponse

    @model_validator(mode="after")
    def consistent_output(self) -> "EstimateRevision":
        if self.estimate.plan_type != self.effective_input.plan.plan_type:
            raise ValueError("estimate and effective input have different plan types")
        if self.estimate.rules_version != self.effective_input.rules_version:
            raise ValueError("estimate and effective input have different rules versions")
        return self


class RevisionSavePrecondition(ContractModel):
    """Future atomic-save guard; no save endpoint is enabled by this model."""

    expected_active_revision_id: UUID | None
    idempotency_key: UUID
