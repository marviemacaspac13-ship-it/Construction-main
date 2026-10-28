"""Electrical review evidence, separate from both catalog counts and plumbing."""
from collections import Counter
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, revalidate_instances='always')


Coordinate = Annotated[float, Field(strict=True, ge=0, le=1000)]
Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')]
ElectricalSku = Literal['OT01', 'OT02', 'OT03', 'CLR01', 'CLR02', 'CLR03',
    'GS01', 'GS02', 'GS03', 'SW01', 'SW02', 'SW03', 'ACO01']
PRICED_REVIEW_SKUS = frozenset({'OT01', 'OT02', 'OT03', 'CLR01', 'CLR02', 'CLR03'})
PARTIAL_REVIEW_SKUS = PRICED_REVIEW_SKUS | {'SW01', 'SW02', 'SW03', 'ACO01'}
ReviewedScope = Literal['standard', 'devices_and_boxes', 'reviewed_device_allowances']
REVIEWED_ESTIMATE_SCOPES = frozenset({'devices_and_boxes', 'reviewed_device_allowances'})


class ElectricalObservation(ReviewModel):
    id: Identifier
    # One observation per physical assembly, not one per switching mechanism.
    assembly_id: Identifier
    box_2d: tuple[Coordinate, Coordinate, Coordinate, Coordinate]
    device_class: Literal['light_point', 'convenience_outlet', 'switch', 'ac_outlet', 'unknown']
    raw_mark: str | None = Field(None, max_length=120)
    adjacent_text: str | None = Field(None, max_length=200)
    socket_configuration: Literal['single', 'duplex', 'triplex'] | None = None
    gang_count: Annotated[int, Field(strict=True, ge=1, le=12)] | None = None
    switching_function: Literal['one_way', 'three_way', 'four_way'] | None = None
    uncertainty: str | None = Field(None, max_length=1000)

    @model_validator(mode='after')
    def positive_box(self):
        y1, x1, y2, x2 = self.box_2d
        if y2 <= y1 or x2 <= x1:
            raise ValueError('Electrical boxes must have positive area.')
        return self


class ElectricalChoice(ReviewModel):
    observation: ElectricalObservation
    disposition: Literal['include', 'exclude'] = 'include'
    # A user's choice, never a model-provided authoritative mapping.
    selected_sku: ElectricalSku | None = None
    exclusion_reason: str | None = Field(None, max_length=1000)
    box_item_id: Literal['UTB01', 'JCB01'] | None = None
    box_compatibility_confirmed: bool = Field(False, strict=True)
    box_exclusion_reason: str | None = Field(None, max_length=1000)

    @model_validator(mode='after')
    def explicit_exclusion(self):
        if self.disposition == 'exclude':
            if not self.exclusion_reason or not self.exclusion_reason.strip():
                raise ValueError('Excluded devices need a reason.')
            if self.selected_sku is not None:
                raise ValueError('An excluded device cannot also select a product.')
        elif self.exclusion_reason is not None:
            raise ValueError('Included devices cannot carry an exclusion reason.')
        return self


class ElectricalAssessment(ReviewModel):
    observation_id: str
    state: Literal['priced', 'unresolved', 'excluded']
    item_id: ElectricalSku | None = None
    basis: str


def assess(choice: ElectricalChoice, partial: bool = False) -> ElectricalAssessment:
    o, sku = choice.observation, choice.selected_sku
    def result(state, basis, item=None):
        return ElectricalAssessment(observation_id=o.id, state=state, item_id=item, basis=basis)
    if choice.disposition == 'exclude':
        return result('excluded', 'explicit_user_exclusion')
    if partial:
        if sku is None:
            return result('unresolved', 'partial_scope_requires_explicit_product_selection')
        if choice.box_item_id:
            if not choice.box_compatibility_confirmed or choice.box_exclusion_reason is not None:
                return result('unresolved', 'confirm_box_compatibility_without_exclusion')
        elif not choice.box_exclusion_reason or not choice.box_exclusion_reason.strip() or choice.box_compatibility_confirmed:
            return result('unresolved', 'select_compatible_box_or_explain_box_exclusion')
        if o.device_class == 'switch':
            if (sku in ('SW01', 'SW02', 'SW03') and o.switching_function == 'one_way'
                    and o.gang_count == int(sku[-1]) and o.socket_configuration is None):
                return result('priced', 'explicit_one_way_product_device_only', sku)
            return result('unresolved', 'confirm_one_way_gang_and_matching_SW_product')
        if o.device_class == 'ac_outlet':
            if sku == 'ACO01' and o.gang_count in (None, 1) and o.switching_function is None:
                return result('priced', 'explicit_generic_AC_product_device_only_no_circuit', sku)
            return result('unresolved', 'select_generic_AC_product_without_circuit_inference')
    if o.device_class in ('switch', 'ac_outlet'):
        return result('unresolved', 'device_product_and_service_rules_not_approved')
    if o.device_class == 'unknown':
        return result('unresolved', 'device_class_unknown')
    if o.switching_function is not None:
        return result('unresolved', 'switch_function_conflicts_with_device_class')
    if o.device_class == 'light_point':
        if o.gang_count is not None or o.socket_configuration is not None:
            return result('unresolved', 'receptacle_attributes_do_not_specify_ceiling_size')
        if sku is None:
            return result('priced', 'existing_ceiling_library_default_not_read_size', 'CLR01')
        if sku in ('CLR01', 'CLR02', 'CLR03'):
            return result('priced', 'explicit_user_product_selection', sku)
        return result('unresolved', 'product_does_not_match_device_class')
    if sku is not None:
        if sku not in ('OT01', 'OT02', 'OT03'):
            return result('unresolved', 'product_does_not_match_device_class')
        if o.gang_count is not None and o.gang_count != int(sku[-1]):
            return result('unresolved', 'confirmed_gang_count_conflicts_with_product')
        return result('priced', 'explicit_user_product_selection', sku)
    if o.socket_configuration == 'duplex' and o.gang_count in (None, 1):
        return result('priced', 'owner_selected_duplex_default_not_read_gang', 'OT01')
    return result('unresolved', 'outlet_product_requires_explicit_selection')


def box_overlap(a, b):
    y1, x1, y2, x2 = a.box_2d
    y3, x3, y4, x4 = b.box_2d
    intersection = max(0, min(y2, y4)-max(y1, y3)) * max(0, min(x2, x4)-max(x1, x3))
    return intersection / ((y2-y1)*(x2-x1)+(y4-y3)*(x4-x3)-intersection)


def validate_choices(choices):
    ids = [c.observation.id for c in choices]
    if len(ids) != len(set(ids)):
        raise ValueError('Electrical observation IDs must be unique, including exclusions.')
    included = [c.observation for c in choices if c.disposition == 'include']
    assemblies = [o.assembly_id for o in included]
    if len(assemblies) != len(set(assemblies)):
        raise ValueError('Merge included observations of the same physical assembly.')
    if any(box_overlap(a, b) > .5 for i, a in enumerate(included) for b in included[i+1:]):
        raise ValueError('Resolve overlapping electrical observations before confirmation.')


class ElectricalReviewSubmission(ReviewModel):
    receipt: str = Field(min_length=1, max_length=1_000_000)
    confirmed: bool = Field(strict=True)
    choices: list[ElectricalChoice] = Field(max_length=500)
    estimate_scope: ReviewedScope = 'standard'

    @model_validator(mode='after')
    def confirm(self):
        if not self.confirmed:
            raise ValueError('Explicit electrical review confirmation is required.')
        validate_choices(self.choices)
        return self


class ElectricalProposalAttempt(ReviewModel):
    provider: Literal['gemini'] = 'gemini'
    model: str = Field(min_length=1, max_length=120)
    outcome: str = Field(min_length=1, max_length=80)
    elapsed_ms: int = Field(ge=0)
    returned_model: str | None = Field(None, max_length=120)


class ElectricalReview(ReviewModel):
    version: Literal['electrical-review-v1'] = 'electrical-review-v1'
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    image_width: Annotated[int, Field(strict=True, gt=0)]
    image_height: Annotated[int, Field(strict=True, gt=0)]
    owner_id: str = Field(min_length=1, max_length=128)
    provider: Literal['template', 'gemini', 'openrouter', 'manual']
    model: str = Field(min_length=1, max_length=120)
    proposed: list[ElectricalObservation] = Field(max_length=500)
    choices: list[ElectricalChoice] = Field(max_length=500)
    confirmed_at: AwareDatetime
    estimate_scope: ReviewedScope = 'standard'
    prompt_version: Literal['electrical-devices-v1'] | None = Field(None, exclude_if=lambda v: v is None)
    attempts: list[ElectricalProposalAttempt] = Field(default_factory=list, max_length=2, exclude_if=lambda v: not v)
    limitations: list[Annotated[str, Field(max_length=1000)]] = Field(default_factory=list, max_length=30, exclude_if=lambda v: not v)

    @model_validator(mode='after')
    def consistent(self):
        validate_choices(self.choices)
        ids = [p.id for p in self.proposed]
        if len(ids) != len(set(ids)):
            raise ValueError('Original electrical proposal IDs must be unique.')
        # Removals remain explicit excluded records rather than disappearing.
        if not set(ids) <= {c.observation.id for c in self.choices}:
            raise ValueError('Every original proposal needs an included or excluded decision.')
        return self

    def assessments(self):
        return [assess(c, self.estimate_scope in REVIEWED_ESTIMATE_SCOPES) for c in self.choices]

    def box_counts(self):
        return dict(Counter(c.box_item_id for c in self.choices
            if c.disposition == 'include' and c.box_item_id))

    def priced_counts(self):
        return dict(Counter(a.item_id for a in self.assessments() if a.state == 'priced'))

    def unresolved(self):
        return [a for a in self.assessments() if a.state == 'unresolved']

    def require_priceable(self):
        if self.unresolved():
            raise ValueError('Resolve or explicitly exclude unsupported electrical devices before estimating.')
        if not self.priced_counts():
            raise ValueError('Electrical review has no supported material-bearing devices to estimate.')
