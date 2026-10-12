"""The three Welsh heritage within_* predicates carry Catrin's attested Welsh (card c0890).

Catrin attested the description_cy forms [sig:65a2bd1e]; no Welsh is composed here. Huw ruled the
capital, 12/10/2026, in chat to the Mac 5 builder: "when starting a sentence or as a single descriptor
then O should be used". A description_cy is a single descriptor, so all three begin with a capital O:
item 1 was attested so; items 2 and 3 are Catrin's words with only their first letter capitalised.
The older heritage siblings on main (within_scheduled_monument and others) are left to a separate
card. awen-weave 0.2.33 (PROPOSED, HOLD)."""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY

ATTESTED = {
    "within_world_heritage_site": "O fewn safle treftadaeth y byd",
    "within_registered_historic_landscape": "O fewn tirwedd hanesyddol gofrestredig",
    "within_protected_wreck": "O fewn llongddrylliad gwarchodedig",
}
# Catrin's words, before Huw's capital rule: only the first letter may differ
CATRIN = {
    "within_world_heritage_site": "O fewn safle treftadaeth y byd",
    "within_registered_historic_landscape": "o fewn tirwedd hanesyddol gofrestredig",
    "within_protected_wreck": "o fewn llongddrylliad gwarchodedig",
}


def test_each_carries_the_attested_welsh_exactly():
    for name, cy in ATTESTED.items():
        assert PREDICATE_REGISTRY[name].description_cy == cy, name


def test_none_of_the_three_is_pending_any_more():
    for name in ATTESTED:
        assert PREDICATE_REGISTRY[name].description_cy != CY_PENDING, name


def test_only_the_welsh_changed():
    """The English, shape and grain are as 0.2.32 left them."""
    for name in ATTESTED:
        p = PREDICATE_REGISTRY[name]
        assert (p.value_type, p.cardinality, p.applies_to_types) == ("text", "multi", ("building",))
    assert PREDICATE_REGISTRY["within_world_heritage_site"].description_en.startswith(
        "World Heritage Site whose inscribed area contains the property")
    assert PREDICATE_REGISTRY["within_registered_historic_landscape"].description_en.startswith(
        "Registered historic landscape containing the property")
    assert PREDICATE_REGISTRY["within_protected_wreck"].description_en.startswith(
        "Protected wreck site (restricted area designated under the Protection of")


def test_all_three_begin_with_a_capital_and_otherwise_are_catrins_words():
    for name, words in CATRIN.items():
        cy = PREDICATE_REGISTRY[name].description_cy
        assert cy[0] == "O" and cy[1:] == words[1:], name


def test_the_older_sibling_is_left_to_a_separate_card():
    assert PREDICATE_REGISTRY["within_scheduled_monument"].description_cy == "o fewn heneb gofrestredig"
