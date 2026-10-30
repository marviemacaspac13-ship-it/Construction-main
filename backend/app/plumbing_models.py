"""Bounded image-space plumbing proposals; never catalog SKUs or probabilities."""
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProposalModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


Coordinate = Annotated[float, Field(ge=0, le=1000, strict=True)]
# Model proposals carry WC/LAV; printed-tag proposals carry every tag the reader prices.
FixtureClass = Literal['WC', 'LAV', 'U', 'FD', 'CO', 'KS', 'SH', 'BT', 'WM', 'HB', 'DF']
Provider = Literal['gemini', 'openrouter', 'tags']
# Fixture tag (as priced in FIXTURE_PLUMBING) -> review class. The one map shared by
# the label reader, the review and the ledger; tests/test_plumbing_more_fixtures.py
# checks that every other fixture list names the same types.
TAG_CLASSES = {'water_closet': 'WC', 'lavatory': 'LAV', 'urinal': 'U', 'floor_drain': 'FD', 'cleanout': 'CO',
               'kitchen_sink': 'KS', 'shower': 'SH', 'bathtub': 'BT', 'washing_machine': 'WM',
               'hose_bib': 'HB', 'drinking_fountain': 'DF'}
# Drawn shapes a model can box. Floor drains, cleanouts, hose bibs and drinking
# fountains are small marks found by their printed labels only.
MODEL_CLASSES = ('WC', 'LAV', 'U', 'KS', 'SH', 'BT', 'WM')
# Receipts signed under prompt v1 asked for toilets and lavatories only.
V1_MODEL_CLASSES = ('WC', 'LAV')


def reviewed_classes(provider, prompt_version=None):
    """The counts a confirmed review replaces; every other count keeps its label read."""
    if provider == 'tags':
        return get_args(FixtureClass)
    return V1_MODEL_CLASSES if prompt_version == 'plumbing-bodies-v1' else MODEL_CLASSES


class FixtureProposal(ProposalModel):
    id: str = Field(min_length=1, max_length=80)
    fixture_class: FixtureClass
    # Original image, normalized [ymin, xmin, ymax, xmax].
    box_2d: tuple[Coordinate, Coordinate, Coordinate, Coordinate]
    uncertainty: str | None = Field(None, max_length=1000)

    @model_validator(mode='after')
    def ordered(self):
        y1, x1, y2, x2 = self.box_2d
        if y2 <= y1 or x2 <= x1:
            raise ValueError('Fixture boxes must have positive area.')
        return self


class ProposalAttempt(ProposalModel):
    provider: Literal['gemini', 'openrouter']
    model: str = Field(max_length=120)
    outcome: str = Field(max_length=80)


class FixtureReview(ProposalModel):
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    provider: Provider
    model: str = Field(max_length=120)
    prompt_version: Literal['plumbing-bodies-v1', 'plumbing-bodies-v2', 'plumbing-tags-v1'] = 'plumbing-bodies-v1'
    attempts: list[ProposalAttempt] = Field(default_factory=list, max_length=8)
    proposed: list[FixtureProposal] = Field(max_length=500)
    accepted: list[FixtureProposal] = Field(max_length=500)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    confirmed_at: str


class ReviewSubmission(ProposalModel):
    receipt: str = Field(min_length=1, max_length=500_000)
    confirmed: bool = Field(strict=True)
    fixtures: list[FixtureProposal] = Field(max_length=500)

    @model_validator(mode='after')
    def unique(self):
        if not self.confirmed:
            raise ValueError('Explicit confirmation is required.')
        ids = [f.id for f in self.fixtures]
        if len(ids) != len(set(ids)):
            raise ValueError('Fixture IDs must be unique.')
        return self
