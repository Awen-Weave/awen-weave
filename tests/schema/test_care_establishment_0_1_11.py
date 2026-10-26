"""Registered care establishments as subjects: constitution 0.1.11 in the grammar (awen-weave 0.2.55).

Card c1878, step 2 of the c1871 plan. Huw signed revision 2 of the care_establishment proposal as Llys 26/10/2026
[sig:0ad68cf6] (all six decisions as recommended), after the Class A scrutiny c1852; constitution v0.1.11 is his tag
(tag object e617e668, commit f4f07e04). These tests hold what r2 draws:

  * one entity type, `care_establishment`, grain `not_spatial`, written `care_establishment:<register>-<id>` in lower
    case: `hiw-m` and four digits (minted) or a CIW URN lower-cased; a bare id or another spelling is refused (C1, C2);
  * the seven premises_* predicates take it as well as `nhs_org` (both not_spatial, so the grain rule allows it);
  * eight new predicates, among them registration_status (closed: registered, de-registered) and also_listed_on_ods
    (entity_ref to an nhs_org, MULTI, its caveat required) (C8);
  * care_establishment_type is closed to the one type ruled so far, 'Hospices' (C9: each further type needs a ruling);
  * no Welsh is written.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from craidd import CONSTITUTION_TAG, CONSTITUTION_VERSION
from craidd.constitution_vendor import __file__ as _vendor_init
from craidd.schema.entity_types import VALID_ENTITY_TYPES
from craidd.schema.grain import Grain, grain_of_entity_type
from craidd.schema.predicates import (
    CARE_ESTABLISHMENT_TYPES, CY_PENDING, PREDICATE_REGISTRY, REGISTRATION_STATUSES, SEED_PREDICATES,
)
from craidd.schema.validation import (
    ORG_SUBJECT_SHAPES, VALUE_CHECKED_PREDICATES, validate_claim, validate_entity, validate_predicate_def,
)

PREMISES = ("premises_point", "premises_postcode", "premises_in_lsoa", "premises_in_authority",
            "premises_in_health_board", "premises_in_country", "premises_in_cluster")
NEW = {  # name: (value type, cardinality)
    "registered_name": ("text", "single"), "care_establishment_type": ("text", "single"),
    "care_services_provided": ("text", "multi"), "care_sector": ("text", "single"),
    "last_inspection_date": ("date", "single"), "registration_status": ("text", "single"),
    "register_reference": ("text", "single"), "also_listed_on_ods": ("entity_ref", "multi"),
}
BASE = dict(source_id="src:hiw-test", recorded_by="lludd", confidence="high")
HOSPICE = "care_establishment:hiw-m0010"


def _ok(pred, subject=HOSPICE, qualifiers=None, etype="care_establishment", **value):
    c = {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": qualifiers or {}, **value}
    return validate_claim(c, subject_entity_type=etype)


# ── the release pin (version-bound: retires at the next constitution release) ───────────────────
def test_the_package_pins_constitution_0_1_11():
    assert (CONSTITUTION_VERSION, CONSTITUTION_TAG) == ("0.1.11", "v0.1.11")


def test_the_vendored_copy_is_the_tag():
    d = Path(_vendor_init).parent
    pinned = json.loads((d / "PINNED.json").read_text())
    assert pinned["tag"] == "v0.1.11" and pinned["commit"] == "f4f07e0487deb1f02f93fb4a83119088a9efcb2f"
    assert (d / "VERSION").read_text().strip() == "0.1.11"
    enum = json.loads((d / "schema" / "entity.schema.json").read_text())["properties"]["entity_type"]["enum"]
    assert enum[-1] == "care_establishment" and set(enum) == VALID_ENTITY_TYPES and len(enum) == 15


# ── the kind and its key ─────────────────────────────────────────────────────────────────────────
def test_the_kind_is_not_spatial():
    assert "care_establishment" in VALID_ENTITY_TYPES
    assert grain_of_entity_type("care_establishment") is Grain.NOT_SPATIAL


@pytest.mark.parametrize("subject,ok", [
    ("care_establishment:hiw-m0001", True), ("care_establishment:hiw-m0011", True),
    ("care_establishment:ciw-sin-00012345-abcd", True), ("care_establishment:ciw-abc-00000001", True),
    ("care_establishment:hiw-M0001", False), ("care_establishment:hiw-m001", False),
    ("care_establishment:hiw-m00001", False), ("care_establishment:ciw-SIN-00012345-ABCD", False),
    ("care_establishment:ciw-m0001", False), ("care_establishment:cqc-1-123", False),
    ("hiw-m0001", False), ("m0001", False), ("nhs_org:7A1LZ", False),
])
def test_the_key_shape(subject, ok):
    assert bool(ORG_SUBJECT_SHAPES["care_establishment"].fullmatch(subject)) is ok
    assert (_ok("registered_name", subject, value_text="Ty Gobaith") == []) is ok


def test_a_bare_id_is_refused_with_its_reason():
    errs = _ok("registered_name", "hiw-m0001", value_text="Ty Gobaith")
    assert errs and any("bare" in e and "care_establishment:<register>-<id>" in e for e in errs), errs


@pytest.mark.parametrize("eid,ok", [(HOSPICE, True), ("hiw-m0010", False), ("care_establishment:HIW-m0010", False)])
def test_entity_ids(eid, ok):
    assert (validate_entity(eid, "care_establishment") == []) is ok


# ── the premises family widened ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", PREMISES)
def test_each_premises_predicate_takes_both_kinds(name):
    p = PREDICATE_REGISTRY[name]
    assert p.applies_to_types == ("nhs_org", "care_establishment") and p.finest_grain is Grain.NOT_SPATIAL
    assert validate_predicate_def(p) == []


def test_a_hospice_takes_its_premises_claims():
    caveat = {"semantics_caveat": "ONS postcode centroid of the HIW postcode, not the door"}
    assert _ok("premises_postcode", value_text="LL32 8SS") == []
    assert _ok("premises_point", qualifiers=caveat, value_geom="POINT(-3.83 53.27)") == []
    assert _ok("premises_in_authority", value_entity_ref="area:W06000003") == []
    assert _ok("premises_postcode", "nhs_org:7A1LZ", etype="nhs_org", value_text="LL32 8SS") == []   # unchanged


# ── the eight new predicates ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(NEW))
def test_each_new_predicate_is_well_formed_on_care_establishment_only(name):
    p = PREDICATE_REGISTRY[name]
    assert [q.name for q in SEED_PREDICATES].count(name) == 1
    assert (p.value_type, p.cardinality) == NEW[name]
    assert p.applies_to_types == ("care_establishment",) and p.finest_grain is Grain.NOT_SPATIAL
    assert p.description_cy == CY_PENDING and validate_predicate_def(p) == []
    assert _ok(name, "nhs_org:7A1LZ", etype="nhs_org", value_text="x") != []


def test_registration_status_is_closed_and_checked():
    assert REGISTRATION_STATUSES == ("registered", "de-registered")
    assert "registration_status" in VALUE_CHECKED_PREDICATES
    assert _ok("registration_status", value_text="de-registered") == []
    assert _ok("registration_status", value_text="deregistered") != []


def test_the_type_is_closed_to_hospices_until_another_is_ruled():
    assert CARE_ESTABLISHMENT_TYPES == ("Hospices",)
    assert "care_establishment_type" in VALUE_CHECKED_PREDICATES
    assert _ok("care_establishment_type", value_text="Hospices") == []
    assert _ok("care_establishment_type", value_text="Hospitals") != []


def test_also_listed_on_ods_is_multi_points_at_an_nhs_org_and_says_what_it_is_not():
    p = PREDICATE_REGISTRY["also_listed_on_ods"]
    assert p.cardinality == "multi" and p.required_qualifiers == ("semantics_caveat",)
    assert "not a claim that the NHS runs" in p.description_en
    q = {"semantics_caveat": "a seat-confirmed postcode-and-name match to an ODS list; not NHS operation"}
    assert _ok("also_listed_on_ods", qualifiers=q, value_entity_ref="nhs_org:7A1LZ") == []
    assert _ok("also_listed_on_ods", qualifiers=q, value_entity_ref="7A1LZ") != []
    assert _ok("also_listed_on_ods", qualifiers=q, value_entity_ref="area:W11000023") != []
    assert _ok("also_listed_on_ods", value_entity_ref="nhs_org:7A1LZ") != []


def test_the_definition_words_travel_into_the_type_description():
    from craidd.schema.entity_types import ENTITY_TYPES
    d = ENTITY_TYPES["care_establishment"]
    for words in ("premises the public attends", "Not an NHS body", "Not a place", "private dwelling"):
        assert words in d, words


def test_the_registry_holds_297():
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES) == 297
