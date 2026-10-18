"""Census profiles for Llefelys (AWE-011), build item 2: PROPOSED, HOLD (cards c1272/c1281).

  * R3, REQ-arloesidolgellau-7d070c (ONS statistical tables via Nomis, OGL v3.0): the consumer addition
    for Llefelys, Census TS066 and TS067, countersigned by Huw 17/10/2026 [sig:607e58a8] with the grain
    rule: a community's TS066/TS067 figures are published only where it has at least 1,000 residents
    and 400 households; smaller communities are shown merged with a neighbour or the wider area and
    labelled; output-area values never leave the Llefelys working copy.
  * NEW: usual_residents_highest_qualification_count (TS067).
  * AMENDED: usual_residents_economic_activity_count (TS066) says it may be served at Welsh community
    grain under that rule, approximate; its LSOA and Lludd wording [sig:691127c0] is kept.
"""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

RULE = ("at least 1,000 residents and 400 households", "607e58a8")


def test_highest_qualification_is_an_int_multi_area_count():
    p = PREDICATE_REGISTRY["usual_residents_highest_qualification_count"]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == () and p.description_cy == CY_PENDING


def test_highest_qualification_names_its_table_universe_and_leaves():
    d = PREDICATE_REGISTRY["usual_residents_highest_qualification_count"].description_en
    assert "TS067" in d and "usual residents aged 16 years and over" in d and "VERBATIM" in d
    for leaf in ("no qualifications", "level 1 and entry level", "level 2", "apprenticeship",
                 "level 3", "level 4 and above", "other"):
        assert leaf in d.lower(), leaf
    assert "Vintage in the citation" in d


def test_both_say_the_community_grain_rule_and_that_community_figures_are_approximate():
    for name in ("usual_residents_highest_qualification_count", "usual_residents_economic_activity_count"):
        d = PREDICATE_REGISTRY[name].description_en
        assert "Welsh community (W04)" in d and all(r in d for r in RULE), name
        assert "approximate" in d and "best-fit" in d, name
        assert "output area" in d.lower() and "never served" in d, name


def test_economic_activity_keeps_its_lsoa_and_lludd_ruling():
    d = PREDICATE_REGISTRY["usual_residents_economic_activity_count"].description_en
    assert "LSOA" in d and "691127c0" in d and "Lludd" in d and "not served openly" in d


def test_the_registry_holds_248():
    assert len(PREDICATE_REGISTRY) == 248
