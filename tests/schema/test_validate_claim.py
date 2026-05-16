"""
Smoke tests for src/craidd/schema/validation.py::validate_claim.

Pins the behaviour already exercised by hand during the foundation build
(2026-05-15). The validator is a pure function — no DB, no I/O — so a
small set of happy-path + obvious-error tests covers most of the
contract surface. v0.1-schema.md §3.2 + §3.5 are the source of truth.
"""
from __future__ import annotations

import pytest

from craidd.schema.validation import (
    VALID_CONFIDENCES,
    validate_claim,
)


def _base_address_claim() -> dict:
    """A minimally-valid `address` claim (bilingual, single) on a building."""
    return {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "address",
        "value_cy": "Adeilad Glyndwr, Stryd y Bont, Dolgellau",
        "value_en": "Glyndwr Buildings, Bridge Street, Dolgellau",
        "source_id": "TDS-DOL-SRC-CADW-4938",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {},
    }


def test_minimal_bilingual_claim_validates_clean():
    errors = validate_claim(_base_address_claim(), subject_entity_type="building")
    assert errors == []


def test_unknown_predicate_is_rejected():
    claim = _base_address_claim()
    claim["predicate"] = "not_a_real_predicate"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("unknown predicate" in e for e in errors)


def test_predicate_wrong_subject_type_is_rejected():
    """`address` applies to building; using it on a tenancy is invalid."""
    claim = _base_address_claim()
    errors = validate_claim(claim, subject_entity_type="tenancy")
    assert any("does not apply to entity type" in e for e in errors)


def test_bilingual_empty_value_is_rejected():
    claim = _base_address_claim()
    claim["value_cy"] = ""
    claim["value_en"] = None
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("bilingual" in e for e in errors)


def test_missing_confidence_is_rejected():
    claim = _base_address_claim()
    claim["confidence"] = None
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("confidence" in e for e in errors)


@pytest.mark.parametrize("confidence", sorted(VALID_CONFIDENCES))
def test_each_valid_confidence_accepted(confidence: str):
    claim = _base_address_claim()
    claim["confidence"] = confidence
    errors = validate_claim(claim, subject_entity_type="building")
    assert errors == []


def test_invalid_confidence_rejected():
    claim = _base_address_claim()
    claim["confidence"] = "very-high"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("confidence" in e for e in errors)


def test_deprecated_predicate_is_rejected():
    claim = _base_address_claim()
    errors = validate_claim(
        claim,
        subject_entity_type="building",
        deprecated_predicates=("address",),
    )
    assert any("deprecated" in e for e in errors)


def test_single_cardinality_conflict_is_rejected():
    """`address` is single-cardinality — adding a second active claim is
    rejected; the caller is expected to supersede the existing one instead."""
    claim = _base_address_claim()
    errors = validate_claim(
        claim,
        subject_entity_type="building",
        existing_active_predicates=("address",),
    )
    assert any("single-cardinality" in e for e in errors)


def test_name_claim_requires_name_type_qualifier():
    """`name_cy`/`name_en` claims carry a required `name_type` qualifier
    (v0.1-schema.md §3.2, item 3 of §1 what's-new). name_cy is text/multi,
    so the value lives in value_text."""
    claim = {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "name_cy",
        "value_text": "Tŷ Newyddion",
        "source_id": "TDS-DOL-SRC-LOCAL",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {},
    }
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("name_type" in e for e in errors)


def test_name_claim_with_invalid_name_type_rejected():
    claim = {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "name_cy",
        "value_text": "Tŷ Newyddion",
        "source_id": "TDS-DOL-SRC-LOCAL",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {"name_type": "made-up-value"},
    }
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("name_type" in e for e in errors)


def test_name_claim_with_valid_name_type_accepted():
    claim = {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "name_cy",
        "value_text": "Tŷ Newyddion",
        "source_id": "TDS-DOL-SRC-LOCAL",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {"name_type": "current_local"},
    }
    errors = validate_claim(claim, subject_entity_type="building")
    assert errors == []


def test_int_predicate_rejects_text_value():
    """`uprn` is int-typed; populating value_text instead is a mismatch."""
    claim = {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "uprn",
        "value_text": "not-a-uprn",
        "source_id": "TDS-DOL-SRC-LOCAL",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {},
    }
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("value_int" in e or "int value" in e for e in errors)
