"""Llefelys (AWE-011) phase 13, exits L1 and L2: the three predicate changes queued by Llefelys Code seat 2
(record of 2026-10-20T14:29:57Z), released on Huw's ruling of 21/10/2026 [sig:8e70be16] (card c1487).

  * NEW usual_residents_welsh_speaking_count: Census 2021 TS033 (Welsh language skills, speaking), under
    REQ-arloesidolgellau-7d070c. The Llefelys transition naming TS032 and TS033 is DRAFT on awen-shared#998;
    defining the predicate serves nothing, and no TS032/TS033 community claim is served until Huw countersigns it.
  * DESCRIPTION ONLY on usual_residents_welsh_language_skills_count (TS032): the Llefelys W04 serving note, as on
    the TS066 predicate, with the same wait.
  * NEW bres_employment_location_quotient: the BRES open access location quotient against Wales, one predicate
    for L2 (jobs nearby) and L6 (sectors with room to grow).
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

NEW = {"usual_residents_welsh_speaking_count": "int", "bres_employment_location_quotient": "real"}
WELSH = ("usual_residents_welsh_speaking_count", "usual_residents_welsh_language_skills_count")


@pytest.mark.parametrize("name,vtype", sorted(NEW.items()))
def test_each_new_one_is_a_multi_area_figure(name, vtype):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (vtype, "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


def test_the_speaking_count_is_ts033_on_census_day():
    d = PREDICATE_REGISTRY["usual_residents_welsh_speaking_count"].description_en
    assert "TS033" in d and "aged 3 years and over" in d and "speak Welsh" in d and "21/03/2021" in d


@pytest.mark.parametrize("name", WELSH)
def test_both_welsh_tables_carry_the_llefelys_community_grain_and_its_wait(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "Welsh community (W04) grain for Llefelys" in d and "[sig:607e58a8]" in d
    assert "1,000 residents and 400 households" in d
    assert "awen-shared#998" in d and "countersign" in d


def test_the_ts032_change_is_description_only():
    p = PREDICATE_REGISTRY["usual_residents_welsh_language_skills_count"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == ("int", "multi", ("area",), Grain.AREA)
    assert "TS032" in p.description_en and "Served at output area" in p.description_en


def test_the_quotient_says_how_it_is_made():
    d = PREDICATE_REGISTRY["bres_employment_location_quotient"].description_en
    assert "open access" in d and "Employment" in d and "over Wales's share" in d
    assert "sum of the 22 local authorities" in d and "above 1" in d
    assert "never split to a community" in d and "no forecast" in d


def test_the_registry_holds_282():
    assert len(PREDICATE_REGISTRY) == 282
