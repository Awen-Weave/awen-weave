"""
Smoke tests for value_from_claim_columns — the BRA→proposal-queue adapter
helper that collapses the claim-table's type-tagged value_* columns into
the single untyped `value` the proposal format carries.

Source: src/craidd/schema/validation.py (value_from_claim_columns) and
design/bra-proposal-handoff.md.
"""
from __future__ import annotations

from craidd.schema.predicates import PREDICATE_REGISTRY
from craidd.schema.validation import value_from_claim_columns


def test_text_value_extracted_from_value_text():
    pred = PREDICATE_REGISTRY["building_type"]  # text/single
    claim = {"value_text": "terrace"}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == "terrace"


def test_int_value_extracted_from_value_int():
    pred = PREDICATE_REGISTRY["uprn"]  # int/single
    claim = {"value_int": 200003184697}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == 200003184697


def test_real_value_extracted_from_value_real():
    pred = PREDICATE_REGISTRY["floor_area_m2"]  # real/single
    claim = {"value_real": 142.6}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == 142.6


def test_bilingual_value_extracted_as_mapping():
    pred = PREDICATE_REGISTRY["address"]  # bilingual/single
    claim = {
        "value_cy": "Adeilad Glyndwr, Stryd y Bont",
        "value_en": "Glyndwr Buildings, Bridge Street",
    }
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == {
        "cy": "Adeilad Glyndwr, Stryd y Bont",
        "en": "Glyndwr Buildings, Bridge Street",
    }


def test_bilingual_value_cy_only_returns_partial_mapping():
    pred = PREDICATE_REGISTRY["address"]
    claim = {"value_cy": "Stryd y Bont"}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == {"cy": "Stryd y Bont"}


def test_bilingual_value_empty_returns_error():
    pred = PREDICATE_REGISTRY["address"]
    claim = {}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors
    assert any("bilingual" in e for e in errors)


def test_int_predicate_with_text_column_flags_stray():
    """A `uprn` claim with value_text populated (and no value_int) is a
    column-mismatch the helper catches."""
    pred = PREDICATE_REGISTRY["uprn"]  # int
    claim = {"value_text": "not-a-uprn"}
    _, errors = value_from_claim_columns(claim, pred)
    assert errors
    assert any("value_text" in e for e in errors)


def test_date_value_prefers_value_date_over_text():
    """v0.1's hybrid date: prefer the precise value_date when present."""
    pred = PREDICATE_REGISTRY["period_start"]  # date/single (tenancy)
    claim = {"value_date": "1885-06-15", "value_date_text": "c.1885"}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == "1885-06-15"


def test_date_value_falls_back_to_value_date_text():
    """When value_date is empty, use the free-text alternative."""
    pred = PREDICATE_REGISTRY["period_start"]
    claim = {"value_date": None, "value_date_text": "c.1885"}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors == []
    assert value == "c.1885"


def test_date_value_empty_returns_error():
    pred = PREDICATE_REGISTRY["period_start"]
    claim = {}
    value, errors = value_from_claim_columns(claim, pred)
    assert errors
    assert any("date" in e for e in errors)
