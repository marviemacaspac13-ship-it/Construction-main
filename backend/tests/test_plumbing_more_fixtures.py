"""Kitchen sinks, showers, bathtubs, washing machines, hose bibs and drinking fountains.

Added on 30 Oct 2026 at the owner's request. Labels find all six (KS, SH, BT, WM, HB,
DF). Gemini also proposes the drawn shapes it can box - urinals, kitchen sinks,
showers, bathtubs, washing machines - under prompt version plumbing-bodies-v2.
Their materials are the owner-approved estimating choice: a 2-inch drain and wye
plus a 1/2-inch supply and tee, and a hose bib takes supply only.
"""
import json

import pytest

from app import plumbing_vision as vision
from app.extract.ocr import TextBox
from app.extract.tags import count_tags, tally
from app.plumbing_models import FixtureProposal, FixtureReview
from app.takeoff.constants import FIXTURE_PLUMBING, FIXTURE_TAG_PATTERNS
from app.takeoff.contracts import SourceQuantityOverrides
from app.takeoff.estimator import estimate_plan
from app.takeoff.params import EstimatingParams
from app.takeoff.rules.plumbing import compute as plumbing_compute
from app.takeoff.schema import PlanSchema

NEW = {"kitchen_sink": "KS", "shower": "SH", "bathtub": "BT", "washing_machine": "WM",
       "hose_bib": "HB", "drinking_fountain": "DF"}


def plan(**tags):
    return PlanSchema(plan_type="Plumbing Plan", source="tags", fixture_tags=tags)


def items(lines):
    return {li.item_id for li in lines}


LABELLED = {tag: label for tag, label in NEW.items() if tag != "washing_machine"}


def test_each_new_label_is_counted():
    boxes = [TextBox(label, 50 + 60 * i, 50, .9, False) for i, label in enumerate(LABELLED.values())]
    assert tally(count_tags(boxes, FIXTURE_TAG_PATTERNS)) == {tag: 1 for tag in LABELLED}


def test_wm_is_not_read_as_a_washing_machine():
    # On Philippine water-line layouts WM marks a water meter. Washing machines
    # come from Gemini's shape proposals or are added by hand in review.
    assert tally(count_tags([TextBox("WM", 50, 50, .9, False)], FIXTURE_TAG_PATTERNS)) == {}


@pytest.mark.parametrize("tag", ["kitchen_sink", "shower", "bathtub", "washing_machine", "drinking_fountain"])
def test_a_drained_fixture_takes_a_two_inch_drain_and_half_inch_supply(tag):
    assert FIXTURE_PLUMBING[tag] == {"drain": "PDP01", "drain_fitting": "PVYO01",
                                     "supply": "PCSP01", "supply_fitting": "PVTB01"}
    assert {"PDP01", "PVYO01", "PCSP01", "PVTB01"} <= items(plumbing_compute(plan(**{tag: 1}), EstimatingParams()))


def test_a_hose_bib_takes_supply_only_and_no_drain_main():
    lines = plumbing_compute(plan(hose_bib=2), EstimatingParams())
    assert items(lines) == {"PCSP01", "PVTB01"}


def test_a_hose_bib_does_not_lengthen_the_drain_main():
    with_bib = plumbing_compute(plan(water_closet=2, hose_bib=3), EstimatingParams())
    drain_main = [li for li in with_bib if li.rule == "plumbing.main_run" and li.item_id == "PDP03"]
    assert drain_main[0].inputs["route_length_m"] == pytest.approx(2 * 1.5)


def test_the_new_materials_are_logged_as_assumptions(catalog):
    estimate = estimate_plan(plan(kitchen_sink=1, water_closet=2, lavatory=1), catalog)
    assert any("kitchen sinks" in a.lower() and "estimating assumption" in a for a in estimate.assumptions)


def test_corrections_accept_the_new_fixtures():
    overrides = SourceQuantityOverrides(plumbing_counts={tag: 1 for tag in NEW})
    assert set(overrides.plumbing_counts) == set(NEW)


def model_body(*classes):
    return json.dumps({"fixtures": [{"id": f"f{i}", "fixture_class": c, "box_2d": [100, 100 + 60 * i, 150, 140 + 60 * i],
                                     "uncertainty": None} for i, c in enumerate(classes)], "limitations": []})


def test_gemini_may_propose_the_drawn_fixtures():
    fixtures, _ = vision.parse_proposals(model_body("WC", "LAV", "U", "KS", "SH", "BT", "WM"))
    assert [f.fixture_class for f in fixtures] == ["WC", "LAV", "U", "KS", "SH", "BT", "WM"]
    assert vision.PROMPT_VERSION == "plumbing-bodies-v2"
    assert set(vision.SCHEMA["properties"]["fixtures"]["items"]["properties"]["fixture_class"]["enum"]) == \
        {"WC", "LAV", "U", "KS", "SH", "BT", "WM"}


@pytest.mark.parametrize("label_only", ["FD", "CO", "HB", "DF"])
def test_gemini_may_not_propose_label_only_fixtures(label_only):
    with pytest.raises(ValueError):
        vision.parse_proposals(model_body(label_only))


def review(prompt_version, *accepted, provider="gemini"):
    boxes = [FixtureProposal(id=f"a{i}", fixture_class=c, box_2d=(100, 100 + 60 * i, 150, 140 + 60 * i))
             for i, c in enumerate(accepted)]
    return FixtureReview(source_sha256="0" * 64, image_width=100, image_height=100, provider=provider,
                         model="gemini-3.8-flash", prompt_version=prompt_version, proposed=boxes,
                         accepted=boxes, confirmed_at="2026-10-30T00:00:00Z")


def test_a_v2_gemini_review_replaces_label_urinals_and_keeps_label_drains():
    counts, _ = vision.apply_review({"urinal": 4, "floor_drain": 3, "water_closet": 9},
                                    [], review("plumbing-bodies-v2", "WC", "U", "KS"))
    assert counts["urinal"] == 1 and counts["kitchen_sink"] == 1 and counts["water_closet"] == 1
    assert counts["floor_drain"] == 3


def test_a_v1_gemini_review_still_covers_only_toilets_and_lavatories():
    # Signed before the prompt grew: it never proposed urinals, so it must not zero them.
    counts, _ = vision.apply_review({"urinal": 4, "water_closet": 9}, [], review("plumbing-bodies-v1", "WC"))
    assert counts["urinal"] == 4 and counts["water_closet"] == 1
    assert vision.reviewed_classes("gemini", "plumbing-bodies-v1") == ("WC", "LAV")


def test_a_label_review_covers_every_tag():
    assert set(vision.reviewed_classes("tags", "plumbing-tags-v1")) == \
        {"WC", "LAV", "U", "FD", "CO", "KS", "SH", "BT", "WM", "HB", "DF"}


def test_a_type_confirmed_as_none_is_kept_as_zero():
    # The correction editor shows a missing count as "Original: Not read", so a
    # reviewed type with nothing accepted must stay as an explicit 0.
    counts, _ = vision.apply_review({"urinal": 2, "floor_drain": 3}, [], review("plumbing-bodies-v2", "WC"))
    assert counts["urinal"] == 0 and counts["kitchen_sink"] == 0
    assert counts["floor_drain"] == 3


def test_the_label_review_ledger_names_the_labels_actually_read(catalog):
    plan = PlanSchema(plan_type="Plumbing Plan", source="tags", fixture_tags={"water_closet": 3},
                      fixture_review=review("plumbing-tags-v1", "WC", "WC", "WC", provider="tags"))
    line = next(a for a in estimate_plan(plan, catalog).assumptions if "printed fixture tags" in a)
    assert "(WC, LAV, U, FD, CO, KS, SH, BT, HB, DF)" in line


def test_every_fixture_list_names_the_same_types():
    """These lists must change together; a label with no class crashes tag_proposals."""
    from typing import get_args
    from app.plumbing_models import MODEL_CLASSES, TAG_CLASSES, FixtureClass
    from app.takeoff.contracts import PlumbingFixtureTag
    assert set(TAG_CLASSES) == set(FIXTURE_PLUMBING) == set(get_args(PlumbingFixtureTag))
    assert set(TAG_CLASSES.values()) == set(get_args(FixtureClass))
    assert set(FIXTURE_TAG_PATTERNS) <= set(TAG_CLASSES)
    assert set(MODEL_CLASSES) <= set(get_args(FixtureClass))
