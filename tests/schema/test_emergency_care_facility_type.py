"""emergency_care_facility_type: PROPOSED, HOLD, phase 11 scope 11.4 / exit 4 (card c1352, after c1334).

Huw ruled [sig:e8842016]: A&E sites come from REQ-arloesidolgellau-8fcae2 (StatsWales 3ce1cc28, emergency
department performance, OGL-3.0), extended by the use transition drafted under c1342. A site is A&E when
its Hospital Type is 'Major Emergency Departments' in the latest month, joined to ods-wlhbsite (3b1c41)
by ODS site code (board code stripped); the month used is recorded on every flag.

So the grammar carries the publisher's own field, VERBATIM, on the site's nhs_org: never inferred from a
site's name, size or services. The two values are StatsWales' own 'Hospital Type' labels below the
'All Emergency Care Facilities' total, enforced as a closed domain, so a renamed label stops a build
rather than slipping through. The month rides in semantics_caveat, which is required.
"""
from __future__ import annotations

import json

import pytest

from craidd.schema.predicates import (CY_PENDING, EMERGENCY_CARE_FACILITY_TYPES, PREDICATE_REGISTRY,
                                      SEED_PREDICATES, Grain)
from craidd.schema.validation import VALUE_CHECKED_PREDICATES, validate_claim

NAME = "emergency_care_facility_type"
MAJOR = "Major Emergency Departments"
OTHER = "Other Emergency Departments/Minor Injury Units"


def _claim(value, caveat="StatsWales 3ce1cc28 Hospital Type, August 2026 (2026m08)"):
    q = {"binding": "asserted"}
    if caveat is not None:
        q["semantics_caveat"] = caveat
    return {"subject_id": "nhs_org:7A1AU", "predicate": NAME, "value_text": value,
            "source_id": "statswales-emergency-department-performance",
            "recorded_by": "test@example.org", "confidence": "high", "qualifiers": q}


def test_the_predicate_is_text_single_on_nhs_org_not_spatial():
    p = PREDICATE_REGISTRY[NAME]
    assert (p.value_type, p.cardinality, p.applies_to_types) == ("text", "single", ("nhs_org",))
    assert p.finest_grain == Grain.NOT_SPATIAL
    assert p.description_cy == CY_PENDING


def test_the_two_values_are_the_publishers_labels_verbatim():
    assert EMERGENCY_CARE_FACILITY_TYPES == (MAJOR, OTHER, "ECDS Type 1 & 2 (England)")   # + the English ECDS value (c1545)
    assert json.loads(PREDICATE_REGISTRY[NAME].constraint_json) == {"enum": [MAJOR, OTHER, "ECDS Type 1 & 2 (England)"]}


def test_the_description_says_which_value_is_an_ae_and_names_the_source_and_month():
    d = PREDICATE_REGISTRY[NAME].description_en
    assert "VERBATIM" in d and "Hospital Type" in d and "3ce1cc28" in d
    assert f"A&E when the value is '{MAJOR}'" in d
    assert "month" in d and "never inferred" in d


def test_semantics_caveat_is_required_so_the_month_travels():
    assert PREDICATE_REGISTRY[NAME].required_qualifiers == ("semantics_caveat",)
    assert validate_claim(_claim(MAJOR, caveat=None), subject_entity_type="nhs_org") != []


@pytest.mark.parametrize("value", [MAJOR, OTHER])
def test_each_published_value_is_accepted(value):
    assert validate_claim(_claim(value), subject_entity_type="nhs_org") == []


@pytest.mark.parametrize("value", ["Major", "A&E", "major emergency departments", "All Emergency Care Facilities"])
def test_anything_else_is_refused(value):
    assert NAME in VALUE_CHECKED_PREDICATES
    errs = validate_claim(_claim(value), subject_entity_type="nhs_org")
    assert errs and "is not one of" in errs[0]


def test_only_on_nhs_org():
    assert validate_claim(_claim(MAJOR) | {"subject_id": "area:W01000001"},
                          subject_entity_type="area") != []


def test_the_registry_holds_the_new_count():
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES) == BASE + 1


BASE = 296   # 265 + the 7 exit 6 predicates (c1332, #61) + 3 Llefelys wages and work (#58, c1389); + 2 Llefelys missed supply (#59, c1394); + usual_residents_welsh_speaking_count and bres_employment_location_quotient (c1487); + premises_in_cluster and premises_in_country (c1545); + community_wider_area and residents_by_place_of_work_count (c1626); + 3 gp_list registers, cancer_treatment_role, deaths_by_place_of_death_count (c1834); + 8 care_establishment predicates (c1878)
