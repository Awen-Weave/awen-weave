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
