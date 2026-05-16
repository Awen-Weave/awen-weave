"""
Smoke tests for src/craidd/schema/validation.py::validate_entity_proposal.

Pins the partial-by-design contract: validate_entity_proposal checks
everything decidable without the live store — proposal_type literal,
ID format, ISO timestamp, submitter, entity{type, names, address,
external_refs}, source, confidence, qualifiers, bilingual note. It does
NOT check external_ref collision, bundle-member consistency with the EP,
or whether the field_session_id references a real open session — those
are craidd-review's job against the DB.

Source: design/entity-proposal-shape.md §3 (file shape) + §5 (validator
contract). Mirrors the happy-path + error-path pattern used in
test_validate_proposal.py.
"""
from __future__ import annotations

import pytest

from craidd.schema import VALID_ENTITY_TYPES
from craidd.schema.validation import validate_entity_proposal


# --- fixtures ---------------------------------------------------------------

def _minimal_ep() -> dict:
    """The smallest entity_proposal that should validate cleanly."""
    return {
        "proposal_type": "entity",
        "proposal_id": "EP-20260516-1015-9c4d2b78",
        "submitted_at": "2026-05-16T10:15:23+01:00",
        "submitter": "huw@arloesidolgellau.com",
        "entity": {
            "entity_type": "building",
            "names": [
                {
                    "value": "Tŷ Newyddion",
                    "language": "cy",
                    "name_type": "current_local",
                },
            ],
        },
        "source": {"id": "TDS-DOL-SRC-TEST"},
        "confidence": "high",
    }


def _full_ep() -> dict:
    """A maximally-populated entity_proposal with all optional fields."""
    return {
        "proposal_type": "entity",
        "proposal_id": "EP-20260516-1015-9c4d2b78",
        "submitted_at": "2026-05-16T10:15:23+01:00",
        "submitter": "huw@arloesidolgellau.com",
        "field_session_id": "FS-20260516-bridge-street-walk",
        "bundle_id": "B-20260516-1015-9c4d2b78",
        "entity": {
            "entity_type": "building",
            "names": [
                {"value": "Tŷ Newyddion", "language": "cy",
                 "name_type": "current_local"},
                {"value": "Ty Newyddion", "language": "en",
                 "name_type": "current_local"},
            ],
            "address_text": "Glyndwr Buildings, Bridge Street, Dolgellau",
            "external_refs": [
                {"scheme": "cadw", "value": "4938"},
                {"scheme": "uprn", "value": "200003184697"},
            ],
        },
        "source": {
            "source_id": "SRC-LLEOLYDD-20260516-1015",
            "source_type": "curator-on-site",
            "evidence_uri": "lleolydd://session/x/placement/y",
        },
        "note": {
            "cy": "Adeilad newydd ei adnabod.",
            "en": "Building newly identified.",
        },
        "confidence": "high",
        "qualifiers": {
            "cache_snapshot_id": "lleolydd-cache-2026-05",
            "verification_method": "on-site",
        },
    }


# --- happy path -------------------------------------------------------------

def test_minimal_ep_validates_clean():
    assert validate_entity_proposal(_minimal_ep()) == []


def test_full_ep_validates_clean():
    assert validate_entity_proposal(_full_ep()) == []


def test_ep_with_cosign_qualifiers_validates_clean():
    """co_signed_by + field_session_id present together is the valid form."""
    ep = _full_ep()
    ep["qualifiers"]["field_session_id"] = "FS-20260516-bridge-street-walk"
    ep["qualifiers"]["co_signed_by"] = "richard@arloesidolgellau.com"
    assert validate_entity_proposal(ep) == []


# Parameterise across every v0.1 entity type. Each should validate when
# given a minimal otherwise-valid shape.
@pytest.mark.parametrize("entity_type", sorted(VALID_ENTITY_TYPES))
def test_each_v01_entity_type_accepted(entity_type: str):
    ep = _minimal_ep()
    ep["entity"]["entity_type"] = entity_type
    assert validate_entity_proposal(ep) == []


# --- error paths: required fields -------------------------------------------

@pytest.mark.parametrize("field", [
    "proposal_type", "proposal_id", "submitted_at", "submitter",
    "entity", "source", "confidence",
])
def test_missing_required_field_rejected(field: str):
    ep = _minimal_ep()
    del ep[field]
    errors = validate_entity_proposal(ep)
    assert errors, f"removing {field} should have produced an error"
    assert any(field.split(".")[0] in e for e in errors)


def test_wrong_proposal_type_rejected():
    ep = _minimal_ep()
    ep["proposal_type"] = "claim"
    errors = validate_entity_proposal(ep)
    assert any("proposal_type" in e for e in errors)


# --- error paths: proposal_id format ----------------------------------------

@pytest.mark.parametrize("bad_id", [
    "EP-",                                 # truncated
    "P-20260516-1015-9c4d2b78",            # claim shape, not entity
    "EP-2026-05-16-1015-9c4d2b78",         # wrong timestamp shape
    "EP-20260516-1015-zzzzzzzz",           # not hex
    "EP-20260516-1015-9c4d2b78-extra",     # trailing junk
])
def test_malformed_proposal_id_rejected(bad_id: str):
    ep = _minimal_ep()
    ep["proposal_id"] = bad_id
    errors = validate_entity_proposal(ep)
    assert any("proposal_id" in e for e in errors)


def test_well_formed_bundle_id_accepted():
    ep = _minimal_ep()
    ep["bundle_id"] = "B-20260516-1015-9c4d2b78"
    assert validate_entity_proposal(ep) == []


def test_malformed_bundle_id_rejected():
    ep = _minimal_ep()
    ep["bundle_id"] = "B-not-valid"
    errors = validate_entity_proposal(ep)
    assert any("bundle_id" in e for e in errors)


# --- error paths: submitted_at ----------------------------------------------

def test_malformed_submitted_at_rejected():
    ep = _minimal_ep()
    ep["submitted_at"] = "not-a-date"
    errors = validate_entity_proposal(ep)
    assert any("submitted_at" in e for e in errors)


def test_iso_date_without_time_accepted_in_submitted_at():
    """`YYYY-MM-DD` alone is a valid ISO-8601 date."""
    ep = _minimal_ep()
    ep["submitted_at"] = "2026-05-16"
    assert validate_entity_proposal(ep) == []


# --- error paths: entity block ----------------------------------------------

def test_entity_not_a_mapping_rejected():
    ep = _minimal_ep()
    ep["entity"] = "Tŷ Newyddion"
    errors = validate_entity_proposal(ep)
    assert any("entity" in e for e in errors)


def test_invalid_entity_type_rejected():
    ep = _minimal_ep()
    ep["entity"]["entity_type"] = "monument"   # v0.3 type, not yet enabled
    errors = validate_entity_proposal(ep)
    assert any("entity_type" in e for e in errors)


def test_empty_names_list_rejected():
    ep = _minimal_ep()
    ep["entity"]["names"] = []
    errors = validate_entity_proposal(ep)
    assert any("names" in e for e in errors)


def test_name_with_invalid_language_rejected():
    ep = _minimal_ep()
    ep["entity"]["names"][0]["language"] = "de"
    errors = validate_entity_proposal(ep)
    assert any("language" in e for e in errors)


def test_name_with_invalid_name_type_rejected():
    ep = _minimal_ep()
    ep["entity"]["names"][0]["name_type"] = "not-a-name-type"
    errors = validate_entity_proposal(ep)
    assert any("name_type" in e for e in errors)


def test_name_with_empty_value_rejected():
    ep = _minimal_ep()
    ep["entity"]["names"][0]["value"] = ""
    errors = validate_entity_proposal(ep)
    assert any("value" in e for e in errors)


def test_address_text_non_string_rejected():
    ep = _minimal_ep()
    ep["entity"]["address_text"] = 42
    errors = validate_entity_proposal(ep)
    assert any("address_text" in e for e in errors)


# --- error paths: external_refs ---------------------------------------------

def test_external_refs_with_unknown_scheme_rejected():
    ep = _minimal_ep()
    ep["entity"]["external_refs"] = [
        {"scheme": "loqate-id", "value": "12345"},
    ]
    errors = validate_entity_proposal(ep)
    assert any("scheme" in e for e in errors)


def test_external_refs_with_malformed_uprn_rejected():
    """UPRN scheme expects exactly 12 digits."""
    ep = _minimal_ep()
    ep["entity"]["external_refs"] = [
        {"scheme": "uprn", "value": "12"},
    ]
    errors = validate_entity_proposal(ep)
    assert any("uprn" in e or "well-formed" in e for e in errors)


def test_external_refs_with_well_formed_toid_accepted():
    ep = _minimal_ep()
    ep["entity"]["external_refs"] = [
        {"scheme": "toid", "value": "osgb1000005195614324"},
    ]
    assert validate_entity_proposal(ep) == []


# --- error paths: source ----------------------------------------------------

def test_source_without_id_rejected():
    ep = _minimal_ep()
    ep["source"] = {"title": "no id given"}
    errors = validate_entity_proposal(ep)
    assert any("source" in e for e in errors)


def test_source_with_source_id_field_accepted():
    """entity-proposal-shape.md §3 uses 'source_id' rather than 'id';
    accept either for forward-compatibility with both shapes."""
    ep = _minimal_ep()
    ep["source"] = {"source_id": "SRC-X"}
    assert validate_entity_proposal(ep) == []


# --- error paths: confidence ------------------------------------------------

def test_invalid_confidence_rejected():
    ep = _minimal_ep()
    ep["confidence"] = "very-high"
    errors = validate_entity_proposal(ep)
    assert any("confidence" in e for e in errors)


# --- error paths: qualifiers ------------------------------------------------

def test_unknown_qualifier_key_rejected():
    ep = _minimal_ep()
    ep["qualifiers"] = {"made_up_key": "x"}
    errors = validate_entity_proposal(ep)
    assert any("qualifier" in e for e in errors)


def test_closed_domain_qualifier_out_of_set_rejected():
    ep = _minimal_ep()
    ep["qualifiers"] = {"verification_method": "intuition"}
    errors = validate_entity_proposal(ep)
    assert any("verification_method" in e for e in errors)


def test_cosign_without_field_session_id_rejected():
    """Cross-qualifier rule from design/lleolydd.md §12.A. The single
    most load-bearing test in this file — the principle is that co-sign
    is a synchronous acceptance path that requires a named session."""
    ep = _minimal_ep()
    ep["qualifiers"] = {"co_signed_by": "richard@arloesidolgellau.com"}
    errors = validate_entity_proposal(ep)
    assert any("co_signed_by" in e and "field_session_id" in e for e in errors)


def test_cosign_with_field_session_id_accepted():
    ep = _minimal_ep()
    ep["qualifiers"] = {
        "co_signed_by": "richard@arloesidolgellau.com",
        "field_session_id": "FS-20260516-bridge-street-walk",
    }
    assert validate_entity_proposal(ep) == []


def test_verified_at_not_iso_rejected():
    ep = _minimal_ep()
    ep["qualifiers"] = {"verified_at": "yesterday afternoon"}
    errors = validate_entity_proposal(ep)
    assert any("verified_at" in e for e in errors)


# --- error paths: note ------------------------------------------------------

def test_note_as_string_rejected():
    ep = _minimal_ep()
    ep["note"] = "this should be a mapping"
    errors = validate_entity_proposal(ep)
    assert any("note" in e for e in errors)


def test_note_with_non_string_value_rejected():
    ep = _minimal_ep()
    ep["note"] = {"cy": 42}
    errors = validate_entity_proposal(ep)
    assert any("note" in e for e in errors)


def test_note_cy_only_accepted():
    ep = _minimal_ep()
    ep["note"] = {"cy": "Welsh only is fine."}
    assert validate_entity_proposal(ep) == []
