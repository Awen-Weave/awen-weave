"""The eight WIMD 2025 domain ranks (awen-weave 0.2.39, PROPOSED).

Option A of PROPOSAL-wimd-domains-grammar-2026-10-14.md (awen-shared, card c1007), ruled by Huw
[sig:0c677900]: eight predicates, one per domain, each int / single / area / Grain.AREA, 1 = most
deprived among the 1,917 LSOAs. It answers the question 10/10 ruling Q5 [sig:b1dc51f4] deferred, on
the one-predicate-per-thing pattern of Q3 [sig:1451bb92]. deprivation_rank (the overall rank, Q4
[sig:563f0c3c]) does not move. No qualifier key, no constitution change.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

DOMAINS = ("income", "employment", "health", "education", "access_to_services", "housing",
           "community_safety", "physical_environment")
NAMES = tuple(f"deprivation_domain_rank_{d}" for d in DOMAINS)


@pytest.mark.parametrize("name", NAMES)
def test_each_domain_rank_is_int_single_area(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "single", ("area",), Grain.AREA)
    assert p.required_qualifiers == ()          # no qualifier key: the domain is in the name


@pytest.mark.parametrize("name", NAMES)
def test_each_description_says_what_every_option_must_say(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "WIMD 2025" in d and "LSOA 2021" in d
    assert "1 = most deprived" in d and "1,917" in d
    assert "a RANK, not a score" in d
    assert "not to be summed or averaged into an overall rank" in d
    assert "deprivation_rank" in d                         # points at the overall rank
    assert "not comparable with WIMD 2019 or earlier" in d


def test_each_description_names_its_own_domain():
    words = {"income": "Income", "employment": "Employment", "health": "Health",
             "education": "Education", "access_to_services": "Access to Services",
             "housing": "Housing", "community_safety": "Community Safety",
             "physical_environment": "Physical Environment"}
    for d, word in words.items():
        assert f"{word} domain" in PREDICATE_REGISTRY[f"deprivation_domain_rank_{d}"].description_en


@pytest.mark.parametrize("name", NAMES)
def test_welsh_is_pending(name):
    assert PREDICATE_REGISTRY[name].description_cy == CY_PENDING


def test_exactly_eight_domains_and_deprivation_rank_unchanged():
    assert sorted(n for n in PREDICATE_REGISTRY if n.startswith("deprivation_domain_rank_")) == sorted(NAMES)
    p = PREDICATE_REGISTRY["deprivation_rank"]
    assert (p.value_type, p.cardinality, p.applies_to_types) == ("int", "single", ("area",))
    assert p.description_en.startswith("Multiple-deprivation rank of an area (1 = most deprived).")


def test_the_registry_holds_275():
    # 198 at 0.2.39 (+ 8 WIMD domains); + 11 CIW care home predicates at 0.2.41 (c1055) = 209.
    assert len(PREDICATE_REGISTRY) == 276
