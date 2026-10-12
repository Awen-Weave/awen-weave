"""The three Welsh heritage within_* predicates carry Catrin's attested Welsh (card c0890).

Catrin attested the description_cy forms [sig:65a2bd1e]; they are set EXACTLY as attested, no Welsh
composed here. Item 1 keeps its capital 'O' as given, although within_scheduled_monument and items 2
and 3 are lower case: whether to keep it or lower-case it to match is a question for Huw, so this test
pins the attested form until he rules. awen-weave 0.2.33 (PROPOSED, HOLD)."""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY

ATTESTED = {
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


def test_the_capital_o_is_kept_as_given_and_the_sibling_is_lower_case():
    assert PREDICATE_REGISTRY["within_world_heritage_site"].description_cy[0] == "O"
    assert PREDICATE_REGISTRY["within_scheduled_monument"].description_cy == "o fewn heneb gofrestredig"
