"""Life expectancy, healthy life expectancy and fuel poverty: PROPOSED, HOLD, phase 11 exit 6 (card c1332).

Registers (countersigned [sig:55e8e1e2], awen-shared#930): REQ-arloesidolgellau-837c00 (ONS Healthy life
expectancy, UK: HLE only, Welsh local authorities, health boards and Wales), c4f429 (ONS health state life
expectancies by WIMD 2019 quintile, Wales: LE, HLE and the gap) and 513c1d (Welsh Government fuel poverty
modelled estimates, Wales level only [sig:aa8f1685]). One predicate per thing, as the WIMD and PPFI groups;
the sex, age band, period and (where published) WIMD quintile or breakdown ride value_en.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

YEARS = ("life_expectancy_years", "healthy_life_expectancy_years")
GAPS = ("life_expectancy_gap_years", "healthy_life_expectancy_gap_years")
NAMES = YEARS + GAPS + ("good_health_life_share_pct", "fuel_poverty_households_count",
                        "fuel_poverty_households_share")


@pytest.mark.parametrize("name", NAMES)
def test_each_is_multi_on_area_at_area_grain_welsh_pending(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.cardinality, p.applies_to_types, p.finest_grain) == ("multi", ("area",), Grain.AREA)
    assert p.value_type == ("int" if name.endswith("_count") else "real")
    assert p.description_cy == CY_PENDING
    assert "value_en" in p.description_en and "never any person" in p.description_en


@pytest.mark.parametrize("name", YEARS + GAPS)
def test_years_are_period_life_tables_in_years(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "YEARS" in d and "three-year period" in d and "not a prediction for anyone" in d


def test_hle_says_good_health_is_self_reported():
    d = PREDICATE_REGISTRY["healthy_life_expectancy_years"].description_en
    assert "'good' or 'very good'" in d and "self-reported" in d


@pytest.mark.parametrize("name", GAPS)
def test_gaps_name_range_and_slope_index(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "range" in d and "Slope Index of Inequality" in d and "quintile 1" in d and "quintile 5" in d
    # measured on ONS's own file (c1332): the published range equals quintile 5 minus quintile 1, all 8 rows
    assert "least deprived quintile 5 minus the most deprived quintile 1" in d


def test_fuel_poverty_is_a_modelled_wales_level_estimate():
    for name in ("fuel_poverty_households_count", "fuel_poverty_households_share"):
        d = PREDICATE_REGISTRY[name].description_en
        assert "modelled" in d and "Wales level" in d and "[sig:aa8f1685]" in d and "10%" in d
    assert "0 to 1" in PREDICATE_REGISTRY["fuel_poverty_households_share"].description_en
    assert "nearest 1,000" in PREDICATE_REGISTRY["fuel_poverty_households_count"].description_en


def test_the_registry_holds_the_new_count():
    from craidd.schema.predicates import SEED_PREDICATES
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES) == BASE + 7 + 1   # + emergency_care_facility_type (c1352)


BASE = 268   # + 3 Llefelys wages and work (#58, c1357, c1389)


# Card c1375: ONS's life expectancy for local areas publishes a lower and upper confidence interval beside each
# figure, and the constitution's open-form confidence_interval qualifier carries it. The descriptions say so,
# rather than "not here"; no predicate is added.
@pytest.mark.parametrize("name", YEARS)
def test_a_published_confidence_interval_rides_the_qualifier(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "confidence_interval qualifier" in d and "not here" not in d
