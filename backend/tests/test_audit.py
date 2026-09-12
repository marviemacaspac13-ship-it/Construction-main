"""The assumption ledger.

Assumptions are deliberately not shown in the UI, so this file is the only
place they survive. That makes two things matter: the record has to be
complete enough to reconstruct an estimate, and writing it must never be
able to break one.
"""

import json

import pytest

from app import audit
from app.takeoff.estimator import estimate_plan
from app.extract.to_plan import extract_plan, to_plan_schema
from tests.fixtures.sample_plans import KERALA


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Point the ledger at a temp file for the duration of a test."""
    path = tmp_path / "estimates.jsonl"
    monkeypatch.setattr(audit, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(audit, "LEDGER", path)
    return path


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def estimate(catalog):
    schema = to_plan_schema(
        extract_plan(
            KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks,
            KERALA.chains, KERALA.opening_tags,
        )
    )
    return estimate_plan(schema, catalog)


def test_an_estimate_is_recorded(ledger, estimate):
    audit.record_estimate("Floor Plan", estimate)
    rows = read(ledger)
    assert len(rows) == 1
    assert rows[0]["plan_type"] == "Floor Plan"
    assert rows[0]["grand_total"] == estimate.grand_total


def test_the_assumptions_are_what_the_ledger_is_for(ledger, estimate):
    """Nothing renders these, so if they are not here they are nowhere."""
    audit.record_estimate("Floor Plan", estimate)
    recorded = read(ledger)[0]["assumptions"]
    assert recorded == estimate.assumptions
    assert any("project guide" in a for a in recorded)


def test_the_record_can_reconstruct_the_bill(ledger, estimate):
    """rules_version alone says which rules ran, not what they produced."""
    row = (audit.record_estimate("Floor Plan", estimate), read(ledger)[0])[1]
    assert row["rules_version"] == estimate.rules_version
    assert {li["item_id"] for li in row["lines"]} == {
        li.item_id for li in estimate.line_items
    }
    assert all("rule" in li for li in row["lines"])


def test_estimates_append_rather_than_overwrite(ledger, estimate):
    audit.record_estimate("Floor Plan", estimate)
    audit.record_estimate("Electrical Plan", estimate)
    assert [r["plan_type"] for r in read(ledger)] == ["Floor Plan", "Electrical Plan"]


def test_a_broken_ledger_never_breaks_an_estimate(monkeypatch, estimate):
    """The caller is waiting on a price; the audit trail is a convenience."""
    def explode(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(audit.Path, "mkdir", explode)
    audit.record_estimate("Floor Plan", estimate)  # must not raise


def test_a_large_ledger_rotates_rather_than_growing_without_bound(ledger, estimate, monkeypatch):
    monkeypatch.setattr(audit, "MAX_BYTES", 10)
    audit.record_estimate("Floor Plan", estimate)
    audit.record_estimate("Floor Plan", estimate)
    assert ledger.with_suffix(".jsonl.1").exists()
    assert len(read(ledger)) == 1


def test_the_extraction_report_is_recorded_when_there_is_one(ledger, estimate, catalog):
    from app.extract.report import report_from_extraction

    ex = extract_plan(
        KERALA.envelope_w, KERALA.envelope_l, KERALA.room_blocks,
        KERALA.chains, KERALA.opening_tags,
    )
    audit.record_estimate("Floor Plan", estimate, report_from_extraction(ex))
    row = read(ledger)[0]
    assert row["extraction"]["unit"] == "cm"
    assert row["extraction"]["warnings"]


def test_detection_estimates_record_no_extraction(ledger, estimate):
    """Nothing was read on that path, so there is nothing to report."""
    audit.record_estimate("Electrical Plan", estimate, None)
    assert "extraction" not in read(ledger)[0]
