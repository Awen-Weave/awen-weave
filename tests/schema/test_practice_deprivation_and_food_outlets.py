"""GP practice deprivation (P1) and food outlets (F3): PROPOSED, phase 11 scope 11.1 (card c1181).

  * P1, StatsWales "Deprivation at GP practice level" (REQ-arloesidolgellau-4e09d9, countersigned
    14/10/2026 [sig:f8f167fa]): per practice (nhs_org:<ODS code>) and extraction date, the practice
    population, the number and percentage of its patients living in the most deprived 20% of WIMD
    LSOAs, and the practice deprivation quintile (1 = most deprived) under each of two methods.
  * F3, FSA Food Hygiene Rating Scheme open data (REQ-arloesidolgellau-7f5412, countersigned
    [sig:6c817dd7]): food outlets registered with each Welsh local authority, by the FSA's business
    type. A count made from the FSA's list (derived); business names and addresses never served.
The date, method and type ride value_en; source_ran_at is required. No qualifier key, no constitution
change.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

PRACTICE = {
    "practice_population_count": "int",
    "practice_patients_most_deprived_20pct_count": "int",
    "practice_patients_most_deprived_20pct_pct": "real",
    "practice_deprivation_quintile": "int",
}


@pytest.mark.parametrize("name", sorted(PRACTICE))
def test_each_practice_predicate_is_multi_on_nhs_org_and_not_spatial(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        PRACTICE[name], "multi", ("nhs_org",), Grain.NOT_SPATIAL)
    assert p.required_qualifiers == ("source_ran_at",)
    assert p.description_cy == CY_PENDING
    d = p.description_en
    assert "nhs_org:<ODS code>" in d and "value_en" in d and "StatsWales" in d


def test_the_quintile_says_which_end_is_most_deprived_and_names_its_method():
    d = PREDICATE_REGISTRY["practice_deprivation_quintile"].description_en
    assert "1 = the most deprived" in d and "method" in d
    assert "not to be compared across dates" in d


def test_the_deprived_share_names_its_wimd_edition_rule():
    d = PREDICATE_REGISTRY["practice_patients_most_deprived_20pct_count"].description_en
    assert "WIMD 2025" in d and "WIMD 2019" in d and "registered" in d


def test_food_outlets_count_is_a_derived_area_count_with_no_names():
    p = PREDICATE_REGISTRY["food_outlets_count"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == ("source_ran_at",)
    d = p.description_en
    assert "business type" in d and "Food Hygiene Rating Scheme" in d
    assert "no business name or address" in d and "not a measure of what anyone eats" in d


def test_the_registry_holds_272():
    assert len(PREDICATE_REGISTRY) == 272
