"""The output-area-to-community link for Llefelys (AWE-011): RATIFIED [sig:1ffc4503] (cards c1232/c1237, build step 1).

  * R1, ONS Output Area (2021) to PARNCP (December 2025) best-fit lookup (REQ-arloesidolgellau-e56561,
    countersigned by Huw 17/10/2026 [sig:607e58a8], OGL v3.0): each 2021 output area goes WHOLLY to the
    Welsh community (W04), English parish (E04) or non-civil-parished area (E43) holding its
    population-weighted centre. A best fit, so every community figure built from it is approximate.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain
from craidd.schema.validation import ENTITY_REF_SHAPES


def test_area_in_community_is_a_single_entity_ref_on_area():
    p = PREDICATE_REGISTRY["area_in_community"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "entity_ref", "single", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


def test_area_in_community_says_best_fit_and_approximate():
    d = PREDICATE_REGISTRY["area_in_community"].description_en
    assert "Output Area 2021" in d and "December 2025" in d and "`area:<GSS code>`" in d
    assert "population-weighted centre" in d and "best fit" in d and "approximate" in d
    assert "not a statement that the whole output area lies inside the community" in d


@pytest.mark.parametrize("value", ["area:W04000466", "area:E04000255", "area:E43000001"])
def test_a_community_or_parish_code_is_accepted(value):
    assert ENTITY_REF_SHAPES["area_in_community"].match(value)


@pytest.mark.parametrize("value", ["W04000466", "area:W06000002", "area:W00000067",
                                   "area:W0400046", "cluster:W04000466"])
def test_anything_else_is_refused(value):
    assert not ENTITY_REF_SHAPES["area_in_community"].match(value)


def test_the_registry_holds_273():
    assert len(PREDICATE_REGISTRY) == 273
