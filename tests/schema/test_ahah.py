"""Access to Healthy Assets and Hazards (AHAH): PROPOSED, HOLD, phase 11 scope 11.2, F2 (card c1321).

Register REQ-arloesidolgellau-9c29cf (AHAH v4, countersigned [sig:6c817dd7], redistributable
[sig:fca1c0cd]). One predicate per thing, as the WIMD and PPFI groups: the ten drive times in MINUTES
(exit 2: "a drive-time claim with its unit in minutes"), the three air pollutants, passive greenspace,
and the combined and four domain percentiles. Each per Welsh LSOA 2021, as published.

Units, from the publisher's own code (GeographicDataService/ahah): v4's times are
((length/1000)/speed_kph)*60 per road edge (cjber/ukroutes), so minutes, aggregated to LSOA by median;
v5's README gives "Raw accessibility times (minutes)".
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

DRIVE = ("gp", "dentist", "pharmacy", "hospital", "leisure_centre", "bluespace", "fast_food", "gambling",
         "pub_bar", "tobacco")
AIR = ("no2", "so2", "pm10")
PCT = ("combined", "health_services", "green_blue_space", "air_quality", "retail_hazards")
NAMES = ([f"ahah_drive_minutes_{d}" for d in DRIVE] + [f"ahah_air_{a}_ugm3" for a in AIR]
         + ["ahah_greenspace_ndvi"] + [f"ahah_percentile_{p}" for p in PCT])


def test_exactly_the_nineteen_ahah_predicates():
    assert sorted(n for n in PREDICATE_REGISTRY if n.startswith("ahah_")) == sorted(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_each_is_single_on_area_at_area_grain_welsh_pending(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.cardinality, p.applies_to_types, p.finest_grain) == ("single", ("area",), Grain.AREA)
    assert p.value_type == ("int" if name.startswith("ahah_percentile_") else "real")
    assert p.description_cy == CY_PENDING
    d = p.description_en
    assert "AHAH" in d and "LSOA" in d and "version in the citation" in d
    assert "never any person" in d


@pytest.mark.parametrize("d", DRIVE)
def test_drive_times_are_in_minutes_by_car_and_modelled(d):
    desc = PREDICATE_REGISTRY[f"ahah_drive_minutes_{d}"].description_en
    assert "MINUTES" in desc and "by car" in desc and "modelled" in desc
    assert "postcodes" in desc


@pytest.mark.parametrize("d", ("fast_food", "gambling", "pub_bar", "tobacco"))
def test_hazard_drive_times_say_nearer_is_more_exposure(d):
    assert "a shorter time means MORE exposure" in PREDICATE_REGISTRY[f"ahah_drive_minutes_{d}"].description_en


def test_hospital_names_the_v5_1_definition_change():
    desc = PREDICATE_REGISTRY["ahah_drive_minutes_hospital"].description_en
    assert "v5.1" in desc and "A&E" in desc


@pytest.mark.parametrize("a", AIR)
def test_air_is_a_modelled_annual_mean_in_micrograms(a):
    desc = PREDICATE_REGISTRY[f"ahah_air_{a}_ugm3"].description_en
    assert "µg/m³" in desc and "annual mean" in desc and "DEFRA" in desc


@pytest.mark.parametrize("p", PCT)
def test_percentiles_are_gb_wide_and_100_is_least_healthy(p):
    desc = PREDICATE_REGISTRY[f"ahah_percentile_{p}"].description_en
    assert "1 to 100" in desc and "100 = the least healthy" in desc and "Great Britain" in desc


def test_not_compared_across_versions():
    for n in NAMES:
        assert "not compared across AHAH versions" in PREDICATE_REGISTRY[n].description_en, n


def test_the_registry_holds_the_new_count():
    from craidd.schema.predicates import SEED_PREDICATES
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES) == BASE + 19 + 1   # + emergency_care_facility_type (c1352)


BASE = 277   # 246 + the 7 exit 6 predicates (c1332) + 3 Llefelys wages and work (#58, c1357), so 275 with AHAH; + 2 Llefelys missed supply (#59, c1394); + usual_residents_welsh_speaking_count and bres_employment_location_quotient (c1487); + premises_in_cluster and premises_in_country (c1545); + community_wider_area and residents_by_place_of_work_count (c1626); + 3 gp_list registers, cancer_treatment_role, deaths_by_place_of_death_count (c1834); + 8 care_establishment predicates (c1878)
