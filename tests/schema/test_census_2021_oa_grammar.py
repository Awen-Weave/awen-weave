"""Census 2021 OA tables grammar (a one-gate grammar addition, awen-weave 0.2.31, PROPOSED).

The page is SharedData/PROPOSAL-phase-9-census-grammar-2026-10-09.md (card c0628), under Huw's
09/10/2026 15:23:55Z ruling [sig:8ea7c020] that the census-2021 OA tables (TS001, TS045, TS007A;
register REQ-arloesidolgellau-7d070c) stay in phase 9. These tests hold what it proposes:

  * usual_residents_count (TS001 and TS007A): area, int, multi, AREA grain; the category or
    five-year age band rides value_en/value_cy, as population_estimate's age band does;
  * households_car_van_availability_count (TS045): area, int, multi, AREA grain; the
    availability category rides value_en/value_cy;
  * no required qualifier (the census day is the citation's vintage, as for population_estimate),
    so no constitution change; no Welsh is written.
"""
from __future__ import annotations

from craidd.schema.grain import Grain
from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES
from craidd.schema.validation import validate_claim, validate_predicate_def

MINTED = {
    "usual_residents_count": ("int", "multi", ("area",), Grain.AREA, ()),
    "households_car_van_availability_count": ("int", "multi", ("area",), Grain.AREA, ()),
}
BASE = dict(source_id="src:ons-census-2021", recorded_by="phase9", confidence="high")


def _claim(pred, subject, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": {}, **value}


def test_the_two_are_registered_once_and_well_formed():
    names = [p.name for p in SEED_PREDICATES]
    for n in MINTED:
        assert names.count(n) == 1, n
        assert validate_predicate_def(PREDICATE_REGISTRY[n]) == [], n


def test_each_has_the_shape_the_proposal_gives():
    for n, (vt, card, applies, grain, req) in MINTED.items():
        p = PREDICATE_REGISTRY[n]
        assert (p.value_type, p.cardinality, p.applies_to_types) == (vt, card, applies), n
        assert p.finest_grain is grain, n
        assert p.required_qualifiers == req, n


def test_no_welsh_is_written():
    for n in MINTED:
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n


def test_both_are_output_area_counts_not_building_facts():
    for n, label in (("usual_residents_count", "Aged 0 to 4 years"),
                     ("households_car_van_availability_count", "No cars or vans in household")):
        ok = _claim(n, "area:W00000001", value_int=42, value_en=label)
        assert validate_claim(ok, subject_entity_type="area") == [], n
        assert validate_claim(ok, subject_entity_type="building"), n


def test_the_census_count_is_not_the_mid_year_estimate():
    d = PREDICATE_REGISTRY["usual_residents_count"].description_en
    assert "Census 2021" in d and "population_estimate" in d
    assert "TS001" in d and "TS007A" in d
    assert "TS045" in PREDICATE_REGISTRY["households_car_van_availability_count"].description_en
