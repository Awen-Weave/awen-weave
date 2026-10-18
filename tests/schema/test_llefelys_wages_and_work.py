"""Wages and work for Llefelys (AWE-011), build item 4: PROPOSED, HOLD (cards c1317/c1298).

  * R6, REQ-arloesidolgellau-727844: ONS ASHE, countersigned by Huw 17/10/2026 [sig:607e58a8]; route moved
    to ONS's published Tables 5, 7 and 8 on ons.gov.uk (awen-shared#921).
  * R7, REQ-arloesidolgellau-e14238: ONS Annual Population Survey via Nomis, countersigned [sig:607e58a8].
Item 4: "by sector for all 22 Welsh local authorities, using regional figures where an authority's are
suppressed. Exit: every borrowed figure is flagged on the page."
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

NEW = {"aps_estimate_pct": "real", "earnings_median_annual_gross_gbp": "int",
       "earnings_median_hourly_excl_overtime_gbp": "real"}


@pytest.mark.parametrize("name,vtype", sorted(NEW.items()))
def test_each_is_a_multi_area_figure(name, vtype):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (vtype, "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


@pytest.mark.parametrize("name", sorted(NEW))
def test_each_says_a_borrowed_figure_is_labelled_and_names_its_area(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "Borrowed from" in d and "semantics_caveat" in d and "never presented as the authority's own" in d
    assert "local authority" in d and "value_en" in d


def test_aps_says_estimate_interval_and_its_markers():
    d = PREDICATE_REGISTRY["aps_estimate_pct"].description_en
    assert "Annual Population Survey" in d and "confidence_interval" in d and "95%" in d
    assert "'!'" in d and "never served" in d and "'*'" in d and "unreliable" in d
    assert "accredited" in d


def test_ashe_says_median_place_basis_and_suppression():
    for n in ("earnings_median_annual_gross_gbp", "earnings_median_hourly_excl_overtime_gbp"):
        d = PREDICATE_REGISTRY[n].description_en
        assert "Annual Survey of Hours and Earnings" in d and "median" in d
        assert "workplace" in d and "residence" in d and "'x'" in d and "'..'" in d
        assert "industry" in d


def test_the_registry_holds_275():
    assert len(PREDICATE_REGISTRY) == 275
