"""NHS organisations as subjects: constitution 0.1.10 in the grammar (awen-weave 0.2.37, PROPOSED).

Card c0944: step 1 of IDR-006 Awen/PROPOSAL-nhs-organisation-subject-kind-2026-10-10-r2.md, under
its rulings of Llys 10/10/2026 (Q1 [sig:8f0740b4], Q2 as amended [sig:3cc4cb54], Q3 [sig:dc513d4d],
Q4 [sig:02dd6f4c], Q5 [sig:cc120f20]). Held for Huw's ratification. These tests hold what the
proposal draws, so a later edit that quietly reverses one goes red:

  * two entity types, `nhs_org` and `cluster`, both grain `not_spatial` (Q1, Q2);
  * the grain rule REFUSES r2 section 3 step 1 as written: a predicate cannot apply to `building`
    and `nhs_org` at once, which is why the location is a new family and `gp_location` is untouched;
  * five location claims, the same for a practice and a site (Q2): point, postcode, containing
    LSOA, authority and board;
  * "contained in" is not "run by" (Q3): two predicates, false friends both ways, and a reference of
    the wrong kind is refused;
  * a bare code is refused, as a subject and as an entity id; the kind is never guessed (Q4);
  * the role is a closed-domain claim the gate checks;
  * no Welsh is written.
"""
from __future__ import annotations

import json

import pytest

from craidd.constitution_vendor import __file__ as _vendor_init
from craidd.schema.entity_types import VALID_ENTITY_TYPES
from craidd.schema.grain import Grain, grain_of_entity_type
from craidd.schema.predicates import (
    CY_PENDING, FALSE_FRIENDS, NHS_ORG_ROLES, PREDICATE_REGISTRY, PredicateDef, SEED_PREDICATES,
)
from craidd.schema.validation import (
    VALUE_CHECKED_PREDICATES, validate_claim, validate_entity, validate_predicate_def,
)

LOCATION = ("premises_point", "premises_postcode", "premises_in_lsoa", "premises_in_authority",
            "premises_in_health_board")
MINTED = LOCATION + ("nhs_org_role", "run_by", "in_cluster")

BASE = dict(source_id="src:lludd-test", recorded_by="lludd", confidence="high")
CAVEAT = {"semantics_caveat": "ONS postcode centroid of the practice postcode, not the door"}


def _claim(pred, subject="nhs_org:W00005", qualifiers=None, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": qualifiers or {}, **value}


def _ok(pred, subject="nhs_org:W00005", qualifiers=None, etype="nhs_org", **value):
    return validate_claim(_claim(pred, subject, qualifiers, **value), subject_entity_type=etype)


# ── the release pin moved to test_care_establishment_0_1_11.py at 0.1.11 (card c1878) ──────────
def test_the_vendored_entity_schema_carries_both_types():
    from pathlib import Path
    schema = json.loads((Path(_vendor_init).parent / "schema" / "entity.schema.json").read_text())
    enum = schema["properties"]["entity_type"]["enum"]
    assert enum[12:14] == ["nhs_org", "cluster"]                 # 0.1.11 appends care_establishment
    assert set(enum) == VALID_ENTITY_TYPES


# ── the two kinds ────────────────────────────────────────────────────────────────────────────────
def test_both_kinds_are_not_spatial():
    assert grain_of_entity_type("nhs_org") is Grain.NOT_SPATIAL
    assert grain_of_entity_type("cluster") is Grain.NOT_SPATIAL


def test_r2_section_3_step_1_as_written_is_refused_by_the_grain_rule():
    """Widening gp_location (property grain, on building) to nhs_org is a registration error."""
    widened = PredicateDef("gp_location", "geom", "single", ("building", "nhs_org"),
                           "x", finest_grain=Grain.PROPERTY)
    errs = validate_predicate_def(widened)
    assert any("not comparable" in e and "'nhs_org'" in e for e in errs), errs


def test_the_existing_gp_predicates_are_untouched():
    for name in ("gp_location", "ods_code", "list_size", "operational_status", "address"):
        p = PREDICATE_REGISTRY[name]
        assert p.applies_to_types == ("building",) and p.finest_grain is Grain.PROPERTY, name
    assert PREDICATE_REGISTRY["unitary_authority"].applies_to_types == ("town",)


# ── the eight predicates ─────────────────────────────────────────────────────────────────────────
def test_the_eight_are_registered_once_well_formed_on_nhs_org_and_not_spatial():
    names = [p.name for p in SEED_PREDICATES]
    for n in MINTED:
        assert names.count(n) == 1, n
        p = PREDICATE_REGISTRY[n]
        assert validate_predicate_def(p) == [], n
        # the premises family also takes care_establishment since 0.1.11 (card c1878)
        assert p.applies_to_types == (("nhs_org", "care_establishment") if n.startswith("premises_")
                                      else ("nhs_org",)), n
        assert p.finest_grain is Grain.NOT_SPATIAL, n
        assert p.cardinality == "single", n
        assert p.description_cy == CY_PENDING, n


def test_value_types():
    vt = {n: PREDICATE_REGISTRY[n].value_type for n in MINTED}
    assert vt == {"premises_point": "geom", "premises_postcode": "text",
                  "premises_in_lsoa": "entity_ref", "premises_in_authority": "entity_ref",
                  "premises_in_health_board": "entity_ref", "nhs_org_role": "text",
                  "run_by": "entity_ref", "in_cluster": "entity_ref"}


def test_a_practice_and_a_site_take_the_same_five_location_claims():
    for subject in ("nhs_org:W00005", "nhs_org:7A2AJ"):   # a practice, then a site
        assert _ok("premises_point", subject, CAVEAT, value_geom="POINT(-3.88 52.74)") == []
        assert _ok("premises_postcode", subject, value_text="LL40 1AA") == []
        assert _ok("premises_in_lsoa", subject, value_entity_ref="area:W01000123") == []
        assert _ok("premises_in_authority", subject, value_entity_ref="area:W06000002") == []
        assert _ok("premises_in_health_board", subject, value_entity_ref="area:W11000023") == []


def test_the_point_must_say_how_it_was_derived():
    errs = _ok("premises_point", value_geom="POINT(-3.88 52.74)")
    assert any("semantics_caveat" in e for e in errs), errs


def test_a_location_predicate_is_refused_on_a_building():
    errs = _ok("premises_point", "building:W00005", CAVEAT, etype="building",
               value_geom="POINT(-3.88 52.74)")
    assert any("does not apply to entity type 'building'" in e for e in errs), errs


# ── Q3: contained in is not run by ───────────────────────────────────────────────────────────────
def test_containment_and_governance_are_false_friends_both_ways():
    pairs = {(f.name, f.use_instead) for f in FALSE_FRIENDS}
    assert ("premises_in_health_board", "run_by") in pairs
    assert ("run_by", "premises_in_health_board") in pairs
    assert ("operated_by", "run_by") in pairs


def test_a_board_reference_of_the_wrong_kind_is_refused_either_way():
    # a board's ODS code where its containing W11 GSS code belongs
    assert _ok("premises_in_health_board", value_entity_ref="nhs_org:7A1")
    # a board's area where the organisation that runs it belongs
    assert _ok("run_by", value_entity_ref="area:W11000023")
    # and the right kinds pass
    assert _ok("premises_in_health_board", value_entity_ref="area:W11000023") == []
    assert _ok("run_by", value_entity_ref="nhs_org:7A1") == []


@pytest.mark.parametrize("pred,bad", [
    ("premises_in_lsoa", "W01000123"),            # bare
    ("premises_in_lsoa", "area:W06000002"),       # an authority, not an LSOA
    ("premises_in_authority", "area:W11000023"),  # a board, not an authority
    ("in_cluster", "W96012"),                     # bare
    ("run_by", "7A1"),                            # bare
])
def test_reference_shapes(pred, bad):
    assert _ok(pred, value_entity_ref=bad)


def test_no_serves_predicate_exists():
    """Q3: no 'serves' link until practice-by-LSOA counts are licensed."""
    assert not [n for n in PREDICATE_REGISTRY if "serve" in n and n != "service_provided"]


# ── Q4: a bare code is refused ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("subject", ["W00005", "building:W00005", "nhs_org:", "nhs_org:w00005",
                                     "nhs_org:nhs_org:W00005", "cluster:W96012"])
def test_a_subject_not_written_nhs_org_code_is_refused(subject):
    errs = _ok("premises_postcode", subject, value_text="LL40 1AA")
    assert any("subject '" in e for e in errs), (subject, errs)


def test_the_bare_code_message_names_the_ruling():
    errs = _ok("premises_postcode", "W00005", value_text="LL40 1AA")
    assert any("bare code" in e and "02dd6f4c" in e for e in errs), errs


def test_the_bare_code_rule_touches_no_existing_predicate():
    """gp-locations' bare-coded claims on building predicates are judged exactly as before."""
    before = validate_claim(_claim("ods_code", "W00005", value_text="W00005"), subject_entity_type=None)
    assert not any("bare code" in e for e in before), before


@pytest.mark.parametrize("etype,eid,ok", [
    ("nhs_org", "nhs_org:W00005", True), ("nhs_org", "W00005", False),
    ("nhs_org", "cluster:W96012", False), ("cluster", "cluster:W96012", True),
    ("cluster", "W96012", False), ("building", "W00005", True),
])
def test_entity_ids(etype, eid, ok):
    assert (validate_entity(eid, etype) == []) is ok, validate_entity(eid, etype)


# ── the role ─────────────────────────────────────────────────────────────────────────────────────
def test_the_role_is_a_closed_domain_the_gate_checks():
    assert NHS_ORG_ROLES == ("gp-practice", "site", "health-board", "service", "community-pharmacy", "dental-practice")   # + service, 0.2.40 [sig:81e81fa4]
    assert json.loads(PREDICATE_REGISTRY["nhs_org_role"].constraint_json) == {"enum": list(NHS_ORG_ROLES)}
    assert "nhs_org_role" in VALUE_CHECKED_PREDICATES
    for r in NHS_ORG_ROLES:
        assert _ok("nhs_org_role", value_text=r) == [], r
    assert _ok("nhs_org_role", value_text="practice")


def test_a_cluster_takes_none_of_the_eight():
    errs = _ok("premises_postcode", "cluster:W96012", etype="cluster", value_text="LL40 1AA")
    assert any("does not apply to entity type 'cluster'" in e for e in errs), errs
