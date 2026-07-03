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


# --- §10 item 7 — new qualifier coverage on claims --------------------------

def _verified_toid_claim() -> dict:
    """A minimal verified_building_toid claim with all three required
    qualifiers (verification_method, verified_at, cache_snapshot_id)."""
    return {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "verified_building_toid",
        "value_text": "osgb1000005195614324",
        "source_id": "TDS-DOL-SRC-LLEOLYDD-2026-05",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {
            "verification_method": "on-site",
            "verified_at": "2026-05-16",
            "cache_snapshot_id": "lleolydd-cache-2026-05",
        },
    }


def test_verified_toid_claim_validates_clean():
    errors = validate_claim(_verified_toid_claim(),
                            subject_entity_type="building")
    assert errors == []


def test_verified_toid_claim_missing_required_qualifier_rejected():
    """verified_building_toid requires verification_method + verified_at
    + cache_snapshot_id. Drop one and the predicate's required_qualifiers
    check should fire."""
    claim = _verified_toid_claim()
    del claim["qualifiers"]["verification_method"]
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("verification_method" in e for e in errors)


def test_verification_method_closed_domain_check():
    claim = _verified_toid_claim()
    claim["qualifiers"]["verification_method"] = "ouija-board"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("verification_method" in e for e in errors)


def test_cosign_qualifiers_on_a_claim_require_field_session_id():
    """The cross-qualifier rule applies to claims, not just to proposals."""
    claim = _verified_toid_claim()
    claim["qualifiers"]["co_signed_by"] = "richard@arloesidolgellau.com"
    # field_session_id deliberately not added
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("co_signed_by" in e and "field_session_id" in e
               for e in errors)


def test_cosign_with_field_session_id_on_a_claim_accepted():
    claim = _verified_toid_claim()
    claim["qualifiers"]["co_signed_by"] = "richard@arloesidolgellau.com"
    claim["qualifiers"]["field_session_id"] = "FS-20260516-bridge-street-walk"
    errors = validate_claim(claim, subject_entity_type="building")
    assert errors == []


def test_geometry_basis_closed_domain():
    """geometry_basis is closed-enum per §10 item 7.2. A value outside
    the four-element set is a validation error."""
    claim = {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value_geom": "POINT(-3.886 52.741)",
        "source_id": "TDS-DOL-SRC-LLEOLYDD",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {"geometry_basis": "made-up-basis"},
    }
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("geometry_basis" in e for e in errors)


def test_geometry_basis_curator_placed_accepted():
    claim = {
        "subject_id": "TDS-DOL-B-00001",
        "predicate": "geometry",
        "value_geom": "POINT(-3.886 52.741)",
        "source_id": "TDS-DOL-SRC-LLEOLYDD",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": {"geometry_basis": "curator-placed"},
    }
    errors = validate_claim(claim, subject_entity_type="building")
    assert errors == []


def test_verified_at_must_be_iso():
    claim = _verified_toid_claim()
    claim["qualifiers"]["verified_at"] = "yesterday morning"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("verified_at" in e for e in errors)


# --- §10 item 8: the `binding` qualifier + federated cross-rule --------------

@pytest.mark.parametrize("binding", ["asserted", "measured", "curated", "derived"])
def test_non_federated_bindings_accepted(binding: str):
    """The four non-federated bindings need no source-of-record and validate
    clean as a plain closed-domain qualifier."""
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = binding
    errors = validate_claim(claim, subject_entity_type="building")
    assert errors == []


def test_binding_closed_domain_rejects_unknown():
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = "teleported"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("binding" in e for e in errors)


def test_binding_federated_requires_source_of_record():
    """binding=federated is invalid without BOTH federated_from and
    source_ran_at — reference, don't copy (mirrors co_signed_by rule)."""
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = "federated"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("federated_from" in e for e in errors)
    assert any("source_ran_at" in e for e in errors)


def test_binding_federated_missing_only_run_utc_rejected():
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = "federated"
    claim["qualifiers"]["federated_from"] = "dolgellau-town-dataset"
    # source_ran_at deliberately omitted
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("source_ran_at" in e for e in errors)
    assert not any("federated_from" in e for e in errors)


def test_binding_federated_with_source_of_record_accepted():
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = "federated"
    claim["qualifiers"]["federated_from"] = "dolgellau-town-dataset"
    claim["qualifiers"]["source_ran_at"] = "2026-06-30T09:15:00+00:00"
    errors = validate_claim(claim, subject_entity_type="building")
    assert errors == []


def test_source_ran_at_must_be_iso():
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = "federated"
    claim["qualifiers"]["federated_from"] = "dolgellau-town-dataset"
    claim["qualifiers"]["source_ran_at"] = "last Tuesday"
    errors = validate_claim(claim, subject_entity_type="building")
    assert any("source_ran_at" in e for e in errors)


def test_federated_from_must_be_nonempty_string():
    claim = _base_address_claim()
    claim["qualifiers"]["binding"] = "federated"
    claim["qualifiers"]["federated_from"] = ""
    claim["qualifiers"]["source_ran_at"] = "2026-06-30T09:15:00+00:00"
    errors = validate_claim(claim, subject_entity_type="building")
    # empty string fails both the non-empty-string check AND the cross-rule
    assert any("federated_from" in e for e in errors)
