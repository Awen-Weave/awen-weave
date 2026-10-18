"""Jobs and firms for Llefelys (AWE-011), build item 3: PROPOSED, HOLD (cards c1297/c1281).

  * R4, REQ-arloesidolgellau-551c2c: ONS Business Register and Employment Survey, OPEN ACCESS tier only
    (Nomis), countersigned by Huw 17/10/2026 [sig:607e58a8]: "the open-access tier only; never
    safeguarded or confidential cells".
  * R5, REQ-arloesidolgellau-c1fbf7: ONS UK Business Counts, enterprises and local units by industry and
    employment size band (Nomis), countersigned [sig:607e58a8] "as filed".
Both are shown at MSOA and local authority, never split to a community.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

NEW = ("bres_employment_count", "enterprises_count", "local_units_count")


@pytest.mark.parametrize("name", NEW)
def test_each_is_an_int_multi_area_count(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


@pytest.mark.parametrize("name", NEW)
def test_each_says_msoa_and_authority_never_a_community_and_rounded(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "MSOA" in d and "local authority" in d and "never split to a community" in d
    assert "rounded" in d and "value_en" in d


def test_bres_says_open_access_only_never_confidential_and_farm_agriculture():
    d = PREDICATE_REGISTRY["bres_employment_count"].description_en
    assert "open access" in d and "never the safeguarded tier" in d and "confidential" in d
    assert "farm agriculture" in d and "workplace" in d
    for status in ("Employees", "Full-time employees", "Part-time employees", "Employment"):
        assert status in d


def test_business_counts_keep_enterprises_and_local_units_apart():
    e = PREDICATE_REGISTRY["enterprises_count"].description_en
    u = PREDICATE_REGISTRY["local_units_count"].description_en
    assert "enterprise" in e and "local_units_count" in e
    assert "local unit" in u and "enterprises_count" in u
    for d in (e, u):
        assert "employment size band" in d and "not necessarily true zeros" in d


def test_the_registry_holds_272():
    assert len(PREDICATE_REGISTRY) == 272
