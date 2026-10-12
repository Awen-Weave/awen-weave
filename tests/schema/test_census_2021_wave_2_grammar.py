"""Census 2021 wave 2 OA tables grammar (a one-gate grammar addition, awen-weave 0.2.32, PROPOSED).

Card c0840, from awen-shared PROPOSAL-census-wave-2-2026-10-11.md (card c0826), under Huw's 10/10/2026
rulings on the census store's grammar: Q1, every further Census 2021 table gets its own predicate named
after its subject; Q2, they come as one generated batch after the measured table list (catalogue
census2021-ts-tables.json, card c0694). Register row REQ-arloesidolgellau-7d070c. These tests hold
what it proposes, in wave 1's form (usual_residents_count, households_car_van_availability_count):

  * five category counts, each area, int, multi, AREA grain, the category riding value_en/value_cy:
    households_central_heating_count (TS046), households_tenure_count (TS054),
    households_accommodation_type_count (TS044), household_spaces_by_size_count (TS017: its universe
    is household SPACES, empty ones included), usual_residents_economic_activity_count (TS066);
  * households_count (TS041): area, int, SINGLE, AREA grain: one figure per area, the base the
    household tables are checked against;
  * no required qualifier, no constitution change, no Welsh written;
  * EPC's building-level `tenure` predicate is NOT reused for TS054, and stays a building fact.
"""
from __future__ import annotations

from craidd.schema.grain import Grain
from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES
from craidd.schema.validation import validate_claim, validate_predicate_def

MINTED = {
    "households_central_heating_count": ("int", "multi", ("area",), Grain.AREA, (), "TS046"),
    "households_tenure_count": ("int", "multi", ("area",), Grain.AREA, (), "TS054"),
    "households_accommodation_type_count": ("int", "multi", ("area",), Grain.AREA, (), "TS044"),
    "household_spaces_by_size_count": ("int", "multi", ("area",), Grain.AREA, (), "TS017"),
    "usual_residents_economic_activity_count": ("int", "multi", ("area",), Grain.AREA, (), "TS066"),
    "households_count": ("int", "single", ("area",), Grain.AREA, (), "TS041"),
}
LABELS = {
    "households_central_heating_count": "Renewable energy only",
    "households_tenure_count": "Owned: Owns outright",
    "households_accommodation_type_count": "Semi-detached",
    "household_spaces_by_size_count": "0 people in household",
    "usual_residents_economic_activity_count": "Economically inactive: Retired",
    "households_count": "Number of households",
}
BASE = dict(source_id="src:ons-census-2021", recorded_by="phase-next", confidence="high")


def _claim(pred, subject, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": {}, **value}


def test_the_six_are_registered_once_and_well_formed():
    names = [p.name for p in SEED_PREDICATES]
    for n in MINTED:
        assert names.count(n) == 1, n
        assert validate_predicate_def(PREDICATE_REGISTRY[n]) == [], n


def test_each_has_the_shape_the_proposal_gives():
    for n, (vt, card, applies, grain, req, _table) in MINTED.items():
        p = PREDICATE_REGISTRY[n]
        assert (p.value_type, p.cardinality, p.applies_to_types) == (vt, card, applies), n
        assert p.finest_grain is grain, n
        assert p.required_qualifiers == req, n


def test_each_names_its_table_and_says_census_2021():
    for n, spec in MINTED.items():
        d = PREDICATE_REGISTRY[n].description_en
        assert "Census 2021" in d and spec[5] in d, n


def test_no_welsh_is_written():
    for n in MINTED:
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n


def test_all_are_area_counts_not_building_facts():
    for n, label in LABELS.items():
        ok = _claim(n, "area:W00000001", value_int=42, value_en=label)
        assert validate_claim(ok, subject_entity_type="area") == [], n
        assert validate_claim(ok, subject_entity_type="building"), n


def test_census_tenure_is_not_epc_tenure():
    assert "households_tenure_count" != "tenure"
    epc = PREDICATE_REGISTRY["tenure"]
    assert epc.applies_to_types == ("building",) and epc.value_type == "text"
    census = PREDICATE_REGISTRY["households_tenure_count"]
    assert census.applies_to_types == ("area",) and census.value_type == "int"
    assert "not the EPC" in census.description_en


def test_the_household_space_universe_and_the_residents_universe_are_said():
    assert "household spaces" in PREDICATE_REGISTRY["household_spaces_by_size_count"].description_en
    assert "empty" in PREDICATE_REGISTRY["household_spaces_by_size_count"].description_en
    d = PREDICATE_REGISTRY["usual_residents_economic_activity_count"].description_en
    assert "aged 16" in d and "usual residents" in d


def test_the_heating_count_is_not_the_lsoa_share():
    d = PREDICATE_REGISTRY["households_central_heating_count"].description_en
    assert "heating_fuel_share" in d


def test_economic_activity_is_declared_served_at_lsoa_only_with_oa_kept_for_lludd():
    """Huw 12/10/2026 [sig:691127c0] (card c0846): TS066 is SERVED for general use at LSOA only; the
    OA grain is built for Lludd (AWE-009) and never served openly. The grain vocabulary holds only
    property / area / not_spatial (a fourth value is a ruling), so finest_grain stays AREA and the
    served grain is declared in the description; the layer and the serving rules enforce it."""
    p = PREDICATE_REGISTRY["usual_residents_economic_activity_count"]
    assert p.finest_grain is Grain.AREA
    d = p.description_en
    assert "LSOA" in d and "691127c0" in d
    assert "Lludd" in d and "not served openly" in d
