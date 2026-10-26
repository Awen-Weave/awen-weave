"""Lludd (AWE-009): the GP disease registers at practice and cluster, and cancer treatment roles on sites. Card
c1834 (Lludd Code seat 2), widening c1833. RATIFIED by Huw 26/10/2026 [sig:699b0367]; released in 0.2.54 (card c1842).

  * Huw ruled 25/10/2026 [sig:e88c3c11] that lludd-registers is re-indexed onto practice (`nhs_org:<ODS code>`) and
    cluster (`cluster:<code>`). disease_register_count, disease_prevalence_crude_pct and registered_patients_count
    cannot simply widen: they apply to `building` and `area` (places), and a predicate about places may not also
    accept a `not_spatial` subject (validation.validate_predicate_def). So three NEW predicates carry the same
    readings on `nhs_org` and `cluster`: gp_list_disease_register_count, gp_list_disease_prevalence_crude_pct and
    gp_list_registered_patients_count. The three place predicates stay exactly as they are (the board and Wales
    rows keep them).
  * NEW deaths_by_place_of_death_count: ONS deaths by place of death (home, hospital, hospice, care home, other
    communal establishment, elsewhere) for a council or health board, REQ-arloesidolgellau-987a0f, countersigned by
    Huw 25/10/2026 [sig:bb825c01] with its carve-out: provisional; the weekly series ended (figures stop in 2023);
    all causes, not 'palliative deaths'; council and board only; registrations or occurrences named.
  * NEW cancer_treatment_role: the role words of REQ-arloesidolgellau-72d6b3's use transition (c1642, countersigned
    as a WORKING LIST [sig:f34720ce]; "the role words go to the release queue"), on `nhs_org` sites, a closed list.
"""
from __future__ import annotations

import json

import pytest

from craidd.schema.predicates import (CANCER_TREATMENT_ROLES, CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES,
                                      Grain)
from craidd.schema.validation import VALUE_CHECKED_PREDICATES, validate_claim, validate_predicate_def

GP_LIST = {  # new name -> (the place predicate it mirrors, value type, required qualifiers)
    "gp_list_disease_register_count": ("disease_register_count", "int", ("source_ran_at",)),
    "gp_list_disease_prevalence_crude_pct": ("disease_prevalence_crude_pct", "real",
                                             ("source_ran_at", "semantics_caveat")),
    "gp_list_registered_patients_count": ("registered_patients_count", "int", ("source_ran_at",)),
}


def _claim(subject, pred, *, caveat="test", **value):
    q = {"binding": "asserted", "source_ran_at": "2025-04-01"}
    if caveat is not None:
        q["semantics_caveat"] = caveat
    return {"subject_id": subject, "predicate": pred, "source_id": "s", "recorded_by": "t@example.org",
            "confidence": "high", "qualifiers": q, **value}


# ── the three GP-list predicates ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(GP_LIST))
def test_each_gp_list_predicate_is_multi_on_nhs_org_and_cluster_not_spatial(name):
    mirror, vtype, required = GP_LIST[name]
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        vtype, "multi", ("nhs_org", "cluster"), Grain.NOT_SPATIAL)
    assert p.required_qualifiers == required == PREDICATE_REGISTRY[mirror].required_qualifiers
    assert p.description_cy == CY_PENDING
    assert validate_predicate_def(p) == []


@pytest.mark.parametrize("name", sorted(GP_LIST))
def test_each_gp_list_description_says_registered_not_resident_and_names_both_keys(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "nhs_org:<ODS code>" in d and "cluster:<code>" in d
    assert "not residents" in d or "not resident" in d
    assert GP_LIST[name][0] in d                 # names the place predicate it mirrors


@pytest.mark.parametrize("subject,kind", [("nhs_org:W95024", "nhs_org"), ("cluster:CC504", "cluster")])
def test_a_practice_and_a_cluster_claim_validate(subject, kind):
    assert validate_claim(_claim(subject, "gp_list_disease_register_count", value_int=212, value_en="Cancer"),
                          subject_entity_type=kind) == []
    assert validate_claim(_claim(subject, "gp_list_registered_patients_count", value_int=5120,
                                 value_en="Persons, all ages"), subject_entity_type=kind) == []
    assert validate_claim(_claim(subject, "gp_list_disease_prevalence_crude_pct", value_real=4.14,
                                 value_en="Cancer"), subject_entity_type=kind) == []


def test_the_crude_rate_still_needs_its_denominator_named():
    assert validate_claim(_claim("nhs_org:W95024", "gp_list_disease_prevalence_crude_pct", caveat=None,
                                 value_real=4.14, value_en="Cancer"), subject_entity_type="nhs_org") != []


def test_the_place_predicates_are_unchanged_and_still_refuse_a_practice():
    for mirror, _, _ in GP_LIST.values():
        assert PREDICATE_REGISTRY[mirror].applies_to_types == ("building", "area")
    assert validate_claim(_claim("nhs_org:W95024", "disease_register_count", value_int=1, value_en="Cancer"),
                          subject_entity_type="nhs_org") != []
    assert validate_claim(_claim("area:W11000023", "gp_list_disease_register_count", value_int=1,
                                 value_en="Cancer"), subject_entity_type="area") != []


# ── cancer_treatment_role ─────────────────────────────────────────────────────────────────────────────
def test_the_role_list_is_the_working_lists_four_words_closed():
    assert CANCER_TREATMENT_ROLES == ("cancer-centre", "radiotherapy", "chemotherapy", "outpatient")
    p = PREDICATE_REGISTRY["cancer_treatment_role"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "text", "multi", ("nhs_org",), Grain.NOT_SPATIAL)
    assert json.loads(p.constraint_json) == {"enum": list(CANCER_TREATMENT_ROLES)}
    assert "cancer_treatment_role" in VALUE_CHECKED_PREDICATES
    assert p.required_qualifiers == ("semantics_caveat",)


@pytest.mark.parametrize("role", ["cancer-centre", "radiotherapy", "chemotherapy", "outpatient"])
def test_each_role_validates_on_a_site_and_a_near_miss_does_not(role):
    assert validate_claim(_claim("nhs_org:RQFH5", "cancer_treatment_role", value_text=role),
                          subject_entity_type="nhs_org") == []
    assert validate_claim(_claim("nhs_org:RQFH5", "cancer_treatment_role", value_text=role.replace("-", " ").title()),
                          subject_entity_type="nhs_org") != []


def test_a_role_needs_its_caveat():
    assert validate_claim(_claim("nhs_org:RQFH5", "cancer_treatment_role", caveat=None, value_text="radiotherapy"),
                          subject_entity_type="nhs_org") != []


def test_the_role_description_says_quoted_working_list_and_not_capacity():
    d = PREDICATE_REGISTRY["cancer_treatment_role"].description_en
    assert "WORKING LIST" in d and "quoted" in d and "72d6b3" in d
    assert "absence" in d.lower() and "capacity" in d


# ── deaths_by_place_of_death_count ────────────────────────────────────────────────────────────────
def test_deaths_by_place_is_an_area_count_with_its_carve_out_required():
    p = PREDICATE_REGISTRY["deaths_by_place_of_death_count"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == ("int", "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == ("source_ran_at", "semantics_caveat")
    d = p.description_en
    for words in ("place of death", "registrations or occurrences", "not 'palliative deaths'", "provisional",
                  "value_en", "Hospice"):
        assert words in d, words
    assert validate_predicate_def(p) == []
    ok = _claim("W06000002", "deaths_by_place_of_death_count", value_int=41, value_en="Home, all causes, 2023")
    assert validate_claim(ok, subject_entity_type="area") == []
    assert validate_claim(_claim("W06000002", "deaths_by_place_of_death_count", caveat=None, value_int=41),
                          subject_entity_type="area") != []
    assert validate_claim(_claim("nhs_org:W95024", "deaths_by_place_of_death_count", value_int=1),
                          subject_entity_type="nhs_org") != []


def test_the_registry_holds_289():
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES) == 289
