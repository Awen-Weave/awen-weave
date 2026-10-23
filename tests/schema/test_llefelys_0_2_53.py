"""Release 0.2.53, Llefelys (AWE-011) phase 13 L2: the two predicates in the release queue (card c1626).

  * NEW community_wider_area: the MSOA (2021) wholly holding a Welsh community, from the plan's pairs [sig:f0b1fb85],
    queued by Huw's ruling of 23/10/2026 [sig:a884ac2d] (card c1595). For phase 13 the link stays in captions.
  * NEW residents_by_place_of_work_count: Census 2021 ODWP01EW, usual residents aged 16+ in employment living in the
    subject MSOA by place of work named in value_en (an MSOA or local authority code), census day 21/03/2021,
    suppressed as published; ruled 23/10/2026 [sig:3c709fd0] (card c1626), under the countersigned Llefelys transition on
    REQ-arloesidolgellau-7d070c [sig:a5012975].
"""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain


def test_community_wider_area_is_a_single_area_link():
    p = PREDICATE_REGISTRY["community_wider_area"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == ("entity_ref", "single", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING
    d = p.description_en
    assert "MSOA (2021) wholly holding this Welsh community" in d and "[sig:f0b1fb85]" in d
    assert "never split" in d and "area:" in d


def test_residents_by_place_of_work_count_is_a_multi_area_count():
    p = PREDICATE_REGISTRY["residents_by_place_of_work_count"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == ("int", "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


def test_the_flow_count_says_what_it_counts_and_where():
    d = PREDICATE_REGISTRY["residents_by_place_of_work_count"].description_en
    assert "ODWP01EW" in d and "aged 16" in d and "in employment" in d and "21/03/2021" in d
    assert "living in the subject MSOA" in d and "place of work named in value_en" in d
    assert "MSOA or local authority code" in d and "suppressed as published" in d and "never split to a community" in d


def test_the_registry_holds_284():
    assert len(PREDICATE_REGISTRY) == 284
