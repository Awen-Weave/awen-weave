"""The build gate must enforce the GRAMMAR, not only the JSON shape.

Until 2026-07-27 `validation_gate` validated a claim against the Tier-1 JSON
Schema and stopped there. The schema describes shape; it cannot express that
`predicate` names a registered predicate, that the predicate applies to the
subject's entity type, that its required qualifiers are present, or that the
value sits in the column its value_type demands. So every snapshot ever built
could carry an invented predicate and pass clean — demonstrated with a claim
naming `this_predicate_does_not_exist_at_all`, which the gate called valid.

These tests are the teeth. Each one FAILS against the pre-fix gate, which is the
only evidence that a guard is real (the standing lesson: prove it fails before
trusting it — two earlier checker designs passed happily on a broken ledger).

The gap was recorded in awen_signals.jsonl on 2026-07-05 and went unactioned for
three weeks, which is the other reason it is pinned by a test now.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import PREDICATE_REGISTRY
from craidd.validation_gate import SchemaValidator

# A claim that is SHAPE-clean: every field the Tier-1 claim schema requires is
# present and well typed. Only the grammar can fault it.
BASE = {
    "claim_id": "test-claim",
    "subject_id": "subject-1",
    "source_id": "source-1",
    "recorded_by": "test@awenweave.com",
    "confidence": "high",
    "qualifiers": {},
}


def _gate(subject_entity_type=None):
    return SchemaValidator(subject_entity_type)


def test_shape_clean_claim_with_invented_predicate_is_refused():
    """The headline regression: an unregistered predicate must not pass."""
    result = _gate().validate(
        "claim", dict(BASE, predicate="this_predicate_does_not_exist_at_all",
                      value_text="whatever"))
    assert not result.valid
    assert any("unknown predicate" in v for v in result.violations), result.violations


def test_missing_required_qualifier_is_refused():
    """`build_period` requires date_precision; the schema cannot know that."""
    result = _gate().validate(
        "claim", dict(BASE, predicate="build_period", value_text="c.1885"))
    assert not result.valid
    assert any("date_precision" in v for v in result.violations), result.violations


def test_value_in_the_wrong_column_is_refused():
    """A predicate declared `int` with its value only in value_text is invalid.

    This is exactly how the returns channel's `uprn` claim was found: `uprn` was
    declared `int` in the seed while every other part of the estate — the
    place-anchor schema, the ^\\d{12}$ external-ref pattern, gazetteer.py,
    returns.py — treats a UPRN as a string. The declaration was the bug and is
    now `text`; the check that caught it is pinned here on a genuinely numeric
    predicate."""
    assert PREDICATE_REGISTRY["uprn"].value_type == "text", (
        "a UPRN is an identifier, not a quantity — see the note in predicates.py")
    result = _gate().validate(
        "claim", dict(BASE, predicate="build_year", value_text="1885"))
    assert not result.valid
    assert any("value_int" in v for v in result.violations), result.violations


def test_unknown_qualifier_key_is_refused():
    result = _gate().validate(
        "claim", dict(BASE, predicate="building_type", value_text="barn",
                      qualifiers={"not_a_real_qualifier": "x"}))
    assert not result.valid
    assert any("unknown qualifier" in v for v in result.violations), result.violations


def test_applies_to_is_enforced_when_the_subject_type_is_declared():
    result = _gate(subject_entity_type="organisation").validate(
        "claim", dict(BASE, predicate="building_type", value_text="barn"))
    assert not result.valid
    assert any("does not apply to entity type" in v for v in result.violations)
    assert result.unchecked == ()


def test_applies_to_is_reported_unchecked_when_the_subject_type_is_unknown():
    """A snapshot builder usually cannot resolve the subject's entity type — the
    subject of a search-layer claim is a UPRN in the frozen spine, not a record
    in the record set being built. applies_to is then the ONE rule skipped, and
    the result must SAY so rather than read as full enforcement."""
    result = _gate().validate(
        "claim", dict(BASE, predicate="building_type", value_text="barn"))
    assert result.valid
    assert result.unchecked == ("applies_to",)


def test_a_wholly_valid_claim_still_passes():
    """The gate must not have become a blanket refusal."""
    result = _gate(subject_entity_type="building").validate(
        "claim", dict(BASE, predicate="build_period", value_text="c.1885",
                      qualifiers={"date_precision": "decade"}))
    assert result.valid, result.violations
    assert result.unchecked == ()


@pytest.mark.parametrize(
    "name,value_type,cardinality",
    [("flood_coverage", "real", "multi"),
     ("population_estimate", "int", "multi"),
     ("alc_grade", "text", "single"),
     ("uprn_count", "int", "single")],
)
def test_backfilled_area_predicates_are_registered(name, value_type, cardinality):
    """Four PUBLISHED layers emitted these with no registry entry — 1,608
    committed claims. Turning the grammar on without registering them would have
    made those four layers unbuildable, so the backfill and the teeth land
    together. Shapes are read off the published data, not chosen."""
    pred = PREDICATE_REGISTRY[name]
    assert pred.value_type == value_type
    assert pred.cardinality == cardinality
    assert pred.applies_to_types == ("area",)
