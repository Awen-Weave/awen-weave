"""
Smoke tests for src/craidd/schema/validation.py::validate_proposal.

Pins the partial-by-design contract: validate_proposal checks everything
decidable without the live store (predicate, value type, qualifiers,
confidence, source, subject identification). It does NOT resolve
subject_hint, check applies_to against the resolved entity, or check
single-cardinality — those are craidd-review's job.
"""
from __future__ import annotations

import pytest

from craidd.schema.validation import validate_proposal


def _base_proposal() -> dict:
    """A minimally-valid floor_area_m2 proposal."""
    return {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "floor_area_m2",
        "value": 142.6,
        "source": {"id": "TDS-DOL-SRC-DOL-ENERGY-2026"},
        "confidence": "medium",
        "qualifiers": {},
    }


def test_minimal_proposal_validates_clean():
    assert validate_proposal(_base_proposal()) == []


def test_subject_hint_is_accepted_in_place_of_subject():
    """v0.1-schema.md proposals identify subject by either entity_id or
    a non-empty subject_hint mapping. BRA uses the hint path."""
    p = _base_proposal()
    del p["subject"]
    p["subject_hint"] = {"name": "Tŷ Newyddion", "uprn": "200003184697"}
    assert validate_proposal(p) == []


def test_missing_submitter_rejected():
    p = _base_proposal()
    p["submitter"] = ""
    errors = validate_proposal(p)
    assert any("submitter" in e for e in errors)


def test_missing_subject_and_hint_rejected():
    p = _base_proposal()
    del p["subject"]
    errors = validate_proposal(p)
    assert any("subject" in e for e in errors)


def test_empty_subject_hint_rejected():
    """Brief says: subject_hint must be a non-empty mapping. Empty fails."""
    p = _base_proposal()
    del p["subject"]
    p["subject_hint"] = {}
    errors = validate_proposal(p)
    assert any("subject" in e for e in errors)


def test_subject_hint_must_be_mapping():
    p = _base_proposal()
    del p["subject"]
    p["subject_hint"] = "Tŷ Newyddion"  # string, not mapping
    errors = validate_proposal(p)
    assert any("subject_hint" in e for e in errors)


def test_unknown_predicate_rejected():
    p = _base_proposal()
    p["predicate"] = "not_a_real_predicate"
    errors = validate_proposal(p)
    assert any("unknown predicate" in e for e in errors)


def test_deprecated_predicate_rejected():
    p = _base_proposal()
    errors = validate_proposal(p, deprecated_predicates=("floor_area_m2",))
    assert any("deprecated" in e for e in errors)


def test_missing_source_rejected():
    p = _base_proposal()
    del p["source"]
    errors = validate_proposal(p)
    assert any("source" in e for e in errors)


def test_source_without_id_rejected():
    p = _base_proposal()
    p["source"] = {"title": "Some source"}
    errors = validate_proposal(p)
    assert any("source" in e for e in errors)


def test_invalid_confidence_rejected():
    p = _base_proposal()
    p["confidence"] = "very-high"
    errors = validate_proposal(p)
    assert any("confidence" in e for e in errors)


def test_int_predicate_accepts_int_value():
    """`build_year` is int-typed."""
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "build_year",
        "value": 1890,
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "medium",
    }
    assert validate_proposal(p) == []


def test_int_predicate_rejects_float_value():
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "build_year",
        "value": 1890.5,
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "medium",
    }
    errors = validate_proposal(p)
    assert any("int" in e for e in errors)


def test_int_predicate_rejects_boolean_value():
    """Python bools are ints, but predicates expecting int reject them
    explicitly (avoids accidental True→1 / False→0 coercion)."""
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "build_year",
        "value": True,
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "medium",
    }
    errors = validate_proposal(p)
    assert any("int" in e for e in errors)


def test_bilingual_predicate_accepts_mapping_with_cy_only():
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "address",
        "value": {"cy": "Stryd y Bont"},
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "medium",
    }
    assert validate_proposal(p) == []


def test_bilingual_predicate_rejects_empty_mapping():
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "address",
        "value": {},
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "medium",
    }
    errors = validate_proposal(p)
    assert any("bilingual" in e for e in errors)


def test_bilingual_predicate_rejects_string_value():
    """Bilingual values must be a {cy,en} mapping, never a plain string."""
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "address",
        "value": "Stryd y Bont",
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "medium",
    }
    errors = validate_proposal(p)
    assert any("bilingual" in e for e in errors)


# --- §10 item 7 — new qualifier coverage on proposals -----------------------

def test_proposal_with_verification_qualifiers_accepts_clean():
    """A geometry proposal carrying the new verification qualifiers
    should pass — they're all known qualifier keys post-§10 item 7."""
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value": "POINT(-3.886 52.741)",
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD"},
        "confidence": "high",
        "qualifiers": {
            "geometry_basis": "curator-placed",
            "verification_method": "on-site",
            "verified_at": "2026-05-16",
            "cache_snapshot_id": "lleolydd-cache-2026-05",
        },
    }
    assert validate_proposal(p) == []


def test_proposal_geometry_basis_outside_enum_rejected():
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value": "POINT(-3.886 52.741)",
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD"},
        "confidence": "high",
        "qualifiers": {"geometry_basis": "guessed"},
    }
    errors = validate_proposal(p)
    assert any("geometry_basis" in e for e in errors)


def test_proposal_cosign_without_field_session_id_rejected():
    """Cross-qualifier rule applies to claim proposals too."""
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value": "POINT(-3.886 52.741)",
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD"},
        "confidence": "high",
        "qualifiers": {"co_signed_by": "richard@arloesidolgellau.com"},
    }
    errors = validate_proposal(p)
    assert any("co_signed_by" in e and "field_session_id" in e
               for e in errors)


def test_proposal_temporal_status_closed_domain():
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value": "POINT(-3.886 52.741)",
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD"},
        "confidence": "high",
        "qualifiers": {"temporal_status": "made-up"},
    }
    errors = validate_proposal(p)
    assert any("temporal_status" in e for e in errors)


def test_proposal_temporal_status_existing_accepted():
    p = {
        "submitter": "huw@arloesidolgellau.com",
        "subject": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value": "POINT(-3.886 52.741)",
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD"},
        "confidence": "high",
        "qualifiers": {"temporal_status": "existing"},
    }
    assert validate_proposal(p) == []
