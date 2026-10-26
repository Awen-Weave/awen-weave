"""Missed local supply for Llefelys (AWE-011), build item 6: PROPOSED, HOLD (cards c1318/c1304).

  * R9, REQ-arloesidolgellau-ed7120: Sell2Wales OCDS, countersigned by Huw 17/10/2026 [sig:607e58a8] "as filed;
    supplier names in processing only, never published [sig:e449210e]"; route the OCP Data Registry copy
    (awen-shared#923). Huw, c1318: hide any count under 5 and any value total built from fewer than 5 awards
    [sig:e580fe02]; label every figure 'April 2022 to March 2026, Sell2Wales via the OCP Data Registry'; lead
    with counts; values only where stated, labelled with how many awards carry one.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

NEW = {"public_contract_supplier_awards_count": "int", "public_contract_award_value_gbp": "int"}


@pytest.mark.parametrize("name,vtype", sorted(NEW.items()))
def test_each_is_a_multi_area_figure(name, vtype):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (vtype, "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


@pytest.mark.parametrize("name", sorted(NEW))
def test_each_names_its_classes_its_rule_and_its_range(name):
    d = PREDICATE_REGISTRY[name].description_en
    for cls in ("in the buyer's community", "in the buyer's authority", "elsewhere in Wales", "outside Wales",
                "location unknown"):
        assert cls in d, cls
    assert "April 2022 to March 2026, Sell2Wales via the OCP Data Registry" in d
    assert "fewer than 5" in d and "no supplier is ever named" in d and "CPV" in d


def test_the_count_says_what_it_counts():
    d = PREDICATE_REGISTRY["public_contract_supplier_awards_count"].description_en
    assert "each supplier named on an award counts once" in d and "buyer" in d


def test_the_value_says_stated_only_and_how_many_carry_one():
    d = PREDICATE_REGISTRY["public_contract_award_value_gbp"].description_en
    assert "only where the award states a value" in d and "how many" in d and "pounds" in d


def test_the_registry_holds_289():
    assert len(PREDICATE_REGISTRY) == 289
