"""Lludd (AWE-009) phase 12, items 12.1 and 12.3: the four grammar changes queued by Lludd Code seat 3 (record of
2026-10-22T11:37:06Z, card c1537), released on card c1545 after Huw's yes to all five c1537 questions [sig:f1f70215].

  * nhs_org_role gains 'community-pharmacy' (ODS edispensary, role RO182) and 'dental-practice' (ODS egdpprac), the
    UK ODS lists filtered to Wales standing for the NHS Wales lists [sig:daeee9e6]; egdpprac mixes NHS and private
    practices, so the role never says 'NHS dentist'.
  * NEW premises_in_cluster: the cluster whose area_in_cluster footprint holds the premises' LSOA. LOCATION, NOT
    MEMBERSHIP (that is in_cluster) (Q2 [sig:d4fba4cf]).
  * NEW premises_in_country: the country containing the premises, from ONSPD, so an English site is flagged as
    English and Welsh-only figures never count it (REQ-arloesidolgellau-72d6b3).
  * emergency_care_facility_type gains 'ECDS Type 1 & 2 (England)': NHS England publishes Type 1 and Type 2
    together at site level in ECDS (REQ-arloesidolgellau-90d742), so the English value says so (Q4 [sig:0c5ab5a8]).
"""
from __future__ import annotations

import json

import pytest

from craidd.schema.predicates import (CY_PENDING, EMERGENCY_CARE_FACILITY_TYPES, NHS_ORG_ROLES, PREDICATE_REGISTRY,
                                      SEED_PREDICATES, Grain)
from craidd.schema.validation import validate_claim

ECDS = "ECDS Type 1 & 2 (England)"


def _claim(pred, *, caveat="test", **value):
    q = {"binding": "asserted"}
    if caveat is not None:
        q["semantics_caveat"] = caveat
    return {"subject_id": "nhs_org:FA371", "predicate": pred, "source_id": "s", "recorded_by": "t@example.org",
            "confidence": "high", "qualifiers": q, **value}


# ── nhs_org_role ────────────────────────────────────────────────────────────────────────────────────
def test_the_two_new_roles_close_the_list_after_service():
    assert NHS_ORG_ROLES == ("gp-practice", "site", "health-board", "service", "community-pharmacy", "dental-practice")
    assert json.loads(PREDICATE_REGISTRY["nhs_org_role"].constraint_json) == {"enum": list(NHS_ORG_ROLES)}


@pytest.mark.parametrize("role", ["community-pharmacy", "dental-practice"])
def test_each_new_role_validates_and_a_near_miss_does_not(role):
    assert validate_claim(_claim("nhs_org_role", caveat=None, value_text=role), subject_entity_type="nhs_org") == []
    assert validate_claim(_claim("nhs_org_role", caveat=None, value_text=role.replace("-", " ")),
                          subject_entity_type="nhs_org") != []


def test_the_role_description_names_the_two_ods_lists_and_never_nhs_dentist():
    d = PREDICATE_REGISTRY["nhs_org_role"].description_en
    assert "community-pharmacy" in d and "edispensary" in d and "RO182" in d
    assert "dental-practice" in d and "egdpprac" in d and "NHS and private" in d
    assert "never 'NHS dentist'" in d


# ── premises_in_cluster and premises_in_country ────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["premises_in_cluster", "premises_in_country"])
def test_each_new_one_is_a_single_entity_ref_on_nhs_org(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "entity_ref", "single", ("nhs_org",), Grain.NOT_SPATIAL)
    assert p.description_cy == CY_PENDING


def test_premises_in_cluster_is_location_not_membership_and_says_so_on_every_claim():
    p = PREDICATE_REGISTRY["premises_in_cluster"]
    assert p.required_qualifiers == ("semantics_caveat",)
    d = p.description_en
    assert "LOCATION, NOT MEMBERSHIP" in d and "in_cluster" in d and "area_in_cluster" in d and "cluster:<" in d
    assert validate_claim(_claim("premises_in_cluster", caveat=None, value_entity_ref="cluster:CC040"),
                          subject_entity_type="nhs_org") != []
    assert validate_claim(_claim("premises_in_cluster", value_entity_ref="cluster:CC040"),
                          subject_entity_type="nhs_org") == []


def test_premises_in_country_is_containment_from_onspd():
    p = PREDICATE_REGISTRY["premises_in_country"]
    assert p.required_qualifiers == ()
    d = p.description_en
    assert "CONTAINMENT" in d and "W92000004" in d and "E92000001" in d and "Welsh-only" in d
    assert validate_claim(_claim("premises_in_country", caveat=None, value_entity_ref="area:E92000001"),
                          subject_entity_type="nhs_org") == []


# ── emergency_care_facility_type ───────────────────────────────────────────────────────────────────────
def test_the_ecds_value_follows_the_two_statswales_labels():
    assert EMERGENCY_CARE_FACILITY_TYPES == ("Major Emergency Departments",
                                             "Other Emergency Departments/Minor Injury Units", ECDS)
    assert json.loads(PREDICATE_REGISTRY["emergency_care_facility_type"].constraint_json) == {
        "enum": list(EMERGENCY_CARE_FACILITY_TYPES)}
    assert validate_claim(_claim("emergency_care_facility_type", value_text=ECDS), subject_entity_type="nhs_org") == []


def test_the_description_says_type_1_and_2_are_published_together_in_england():
    d = PREDICATE_REGISTRY["emergency_care_facility_type"].description_en
    assert ECDS in d and "ECDS" in d and "together" in d and "England" in d and "Type 1" in d
    assert "3ce1cc28" in d                       # the Welsh reading is unchanged


def test_the_registry_holds_288():
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES) == 288
