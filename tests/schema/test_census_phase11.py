"""Census 2021 for Wales, phase 11 scope 11.5: PROPOSED, HOLD (card c1209).

Register REQ-arloesidolgellau-7d070c (ONS statistical tables via Nomis; OGL v3, redistributable;
the Census 2021 bulk files permitted [sig:a7374d4e], confirmed 10/10/2026). One predicate per thing,
as the WIMD and PPFI groups: one per table, each an area count by the table's LEAF category, named
verbatim in value_en (the census pattern; subtotals not carried).

  TS037 general health                 usual_residents_general_health_count
  TS038 disability                     usual_residents_disability_count
  TS039 unpaid care by hours           usual_residents_unpaid_care_count
  TS032 Welsh language skills          usual_residents_welsh_language_skills_count
  TS003 household composition          households_composition_count

Serving grain as proposed on card c1209 (Huw rules): TS037, TS038 and TS039 at LSOA only, the
sensitivity Huw ruled for TS066's 'long-term sick or disabled' [sig:691127c0]; TS032 and TS003 at
output area.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

TABLES = {
    "usual_residents_general_health_count": "TS037",
    "usual_residents_disability_count": "TS038",
    "usual_residents_unpaid_care_count": "TS039",
    "usual_residents_welsh_language_skills_count": "TS032",
    "households_composition_count": "TS003",
}
LSOA_ONLY = ("usual_residents_general_health_count", "usual_residents_disability_count",
             "usual_residents_unpaid_care_count")


@pytest.mark.parametrize("name", sorted(TABLES))
def test_each_is_an_int_multi_area_count_at_area_grain(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "multi", ("area",), Grain.AREA)
    assert p.description_cy == CY_PENDING


@pytest.mark.parametrize("name", sorted(TABLES))
def test_each_names_its_table_and_carries_leaves_verbatim(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert f"({TABLES[name]}" in d and "Census 2021" in d
    assert "VERBATIM from ONS" in d and "subtotals not carried" in d


@pytest.mark.parametrize("name", LSOA_ONLY)
def test_health_disability_and_unpaid_care_are_served_at_lsoa_only(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "LSOA only" in d and "[sig:691127c0]" in d and "never at output area" in d


@pytest.mark.parametrize("name", sorted(set(TABLES) - set(LSOA_ONLY)))
def test_welsh_language_and_household_composition_are_served_at_output_area(name):
    assert "output area" in PREDICATE_REGISTRY[name].description_en


def test_the_universes():
    r = PREDICATE_REGISTRY
    assert "all usual residents" in r["usual_residents_general_health_count"].description_en
    assert "Equality Act" in r["usual_residents_disability_count"].description_en
    assert "aged 5 years and over" in r["usual_residents_unpaid_care_count"].description_en
    assert "aged 3 years and over" in r["usual_residents_welsh_language_skills_count"].description_en
    assert "HOUSEHOLDS" in r["households_composition_count"].description_en


def test_unpaid_care_names_its_two_unmarked_subtotals():
    d = PREDICATE_REGISTRY["usual_residents_unpaid_care_count"].description_en
    assert "'19 hours or less'" in d and "'20 to 49 hours'" in d


def test_older_people_living_alone_is_the_aged_66_category():
    d = PREDICATE_REGISTRY["households_composition_count"].description_en
    assert "One person household: Aged 66 years and over" in d and "not 65" in d


def test_the_registry_holds_253():
    assert len(PREDICATE_REGISTRY) == 253
