"""PPFI v2.1 (F1) and the LSOA-to-cluster link (P2): PROPOSED, phase 11 scope 11.1 (card c1181).

  * F1, Priority Places for Food Index v2.1 (REQ-arloesidolgellau-e2c2c8, countersigned [sig:6c817dd7],
    redistributable [sig:fca1c0cd]): per Welsh LSOA, the combined rank and the seven domain ranks
    within Wales, and their deciles. One predicate per thing, the WIMD-domains pattern ([sig:0c677900]).
  * P2, Data Map Wales Primary Care Clusters (REQ-arloesidolgellau-5ba9fe, countersigned
    [sig:b9864b81], redistributable [sig:fca1c0cd]): the cluster whose best-fit footprint holds an LSOA.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

DOMAINS = ("combined", "supermarket_proximity", "supermarket_accessibility", "ecommerce_access",
           "socio_demographic", "nonsupermarket_proximity", "food_for_families", "fuel_poverty")
RANKS = tuple(f"ppfi_rank_{d}" for d in DOMAINS)
DECILES = tuple(f"ppfi_decile_{d}" for d in DOMAINS)


@pytest.mark.parametrize("name", RANKS + DECILES)
def test_each_ppfi_predicate_is_int_single_area(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "single", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING
    d = p.description_en
    assert "PPFI" in d and "v2.1" in d and "within Wales" in d and "LSOA 2021" in d
    assert "not comparable across countries" in d


@pytest.mark.parametrize("name", RANKS)
def test_each_rank_says_1_is_the_highest_priority_and_how_that_was_established(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "1 = the highest priority" in d and "measured" in d


@pytest.mark.parametrize("name", DECILES)
def test_each_decile_runs_1_to_10(name):
    assert "decile 1 = the highest-priority tenth" in PREDICATE_REGISTRY[name].description_en


def test_exactly_the_sixteen_ppfi_predicates():
    assert sorted(n for n in PREDICATE_REGISTRY if n.startswith("ppfi_")) == sorted(RANKS + DECILES)


def test_area_in_cluster_is_a_single_entity_ref_on_area():
    p = PREDICATE_REGISTRY["area_in_cluster"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "entity_ref", "single", ("area",), Grain.AREA)
    d = p.description_en
    assert "cluster:<publisher code>" in d and "best fit by registration" in d
    assert "not an exact boundary" in d and "October 2024" in d


def test_the_registry_holds_236():
    assert len(PREDICATE_REGISTRY) == 236


# HASP's own domain names, from the dataset page's Method of Collection
# (https://data.hasp.ac.uk/browser/dataset/5276/0, read 16/10/2026). Ruled by Huw as Llys 16/10/2026
# [sig:a00b8fe2]: the rank and decile descriptions name each domain as HASP does. Compared without
# regard to case: HASP writes "Fuel Poverty", the ratified description "Fuel poverty".
HASP_DOMAIN_NAMES = {
    "supermarket_proximity": "Proximity to supermarket retail facilities",
    "supermarket_accessibility": "Accessibility to supermarket retail facilities",
    "ecommerce_access": "Access to online deliveries",
    "nonsupermarket_proximity": "Proximity to non-supermarket food provision",
    "socio_demographic": "Socio-demographic barriers",
    "food_for_families": "Need for family food support",
    "fuel_poverty": "Fuel Poverty",
}


@pytest.mark.parametrize("domain", sorted(HASP_DOMAIN_NAMES))
@pytest.mark.parametrize("kind", ["rank", "decile"])
def test_each_domain_is_named_as_hasp_names_it(domain, kind):
    d = PREDICATE_REGISTRY[f"ppfi_{kind}_{domain}"].description_en
    assert f"the {HASP_DOMAIN_NAMES[domain]} domain".lower() in d.lower()


@pytest.mark.parametrize("kind", ["rank", "decile"])
def test_the_names_hasp_does_not_use_are_gone(kind):
    for old in ("Socio-economic barriers", "Family food support domain"):
        d = PREDICATE_REGISTRY[f"ppfi_{kind}_socio_demographic"].description_en + \
            PREDICATE_REGISTRY[f"ppfi_{kind}_food_for_families"].description_en
        assert f"the {old}" not in d
