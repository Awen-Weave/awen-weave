"""Every single-descriptor description_cy that began 'o fewn' begins 'O fewn' (card c0892).

Huw's rule, 12/10/2026, in chat to the Mac 5 builder: "when starting a sentence or as a single
descriptor then O should be used" (applied to the three heritage within_* in 0.2.33, #35). Only the
first letter changes: no other character, no Welsh composed. awen-weave 0.2.34 (PROPOSED, HOLD)."""
from __future__ import annotations

from craidd.schema.predicates import PREDICATE_REGISTRY, SEED_PREDICATES

# the five as they stood on main at 0.2.33 (2bb8370), before the capital
BEFORE = {
    "within_scheduled_monument": "o fewn heneb gofrestredig",
    "near_scheduled_monument_250m": "o fewn 250 m i heneb gofrestredig",
    "in_registered_park_garden": "o fewn parc a gardd hanesyddol gofrestredig",
    "in_registered_battlefield": "o fewn maes brwydr cofrestredig",
    "in_coal_high_risk_area": "o fewn ardal risg uchel oherwydd datblygiad (glo)",
}


def test_each_begins_with_a_capital_and_no_other_character_changed():
    for name, before in BEFORE.items():
        cy = PREDICATE_REGISTRY[name].description_cy
        assert cy == "O" + before[1:], name


def test_no_description_cy_still_begins_lower_case_o_fewn():
    assert not [p.name for p in SEED_PREDICATES
                if isinstance(p.description_cy, str) and p.description_cy.startswith("o fewn")]


def test_a_description_not_beginning_o_fewn_is_untouched():
    # outside this card's rule: it begins 'yn agos at', not 'o fewn'
    assert PREDICATE_REGISTRY["near_scheduled_monument"].description_cy == (
        "yn agos at heneb gofrestredig (o fewn dalgylch ei gosodiad)")
