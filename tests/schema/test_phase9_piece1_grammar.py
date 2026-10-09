"""Phase 9 piece 1 grammar (a one-gate grammar addition, awen-weave 0.2.30, PROPOSED).

The page is awen-shared PROPOSAL-phase-9-piece-1-grammar-release-2026-10-09.md (card c0615). These
tests hold what it proposes, so a later edit that quietly reverses one goes red:

  * within_protected_wreck: building, text, multi, PROPERTY grain, the same within-only shape as
    within_world_heritage_site and within_registered_historic_landscape. Huw as Llys RATIFIED all
    three on 01/09/2026 [sig:57ce9e14] ("Wrecks are NOT held"); 0.2.16 registered only two;
  * the two registered in 0.2.16 carried description_cy="CY_PENDING" as a LITERAL string, not the
    CY_PENDING sentinel, so they read as if their Welsh were written. They now carry the sentinel;
  * population_projection (task 9.5, Huw's 13:29:51Z ruling of 09/10, PROPOSED and not yet
    ratified): area, int, multi, AREA grain, required qualifiers scenario + horizon + baseline
    (the existing constitution 0.1.6 projection keys, so no constitution change);
  * no Welsh is written: every new or corrected description_cy is the pending sentinel.
"""
from __future__ import annotations

from craidd.schema.grain import Grain
from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES
from craidd.schema.validation import validate_claim, validate_predicate_def

# name -> (value_type, cardinality, applies_to, grain, required_qualifiers)
MINTED = {
    "within_protected_wreck": ("text", "multi", ("building",), Grain.PROPERTY, ()),
    "population_projection": ("int", "multi", ("area",), Grain.AREA,
                              ("scenario", "horizon", "baseline")),
}
HERITAGE_THREE = ("within_world_heritage_site", "within_registered_historic_landscape",
                  "within_protected_wreck")

BASE = dict(source_id="src:wg-la-population-projections-2022", recorded_by="phase9", confidence="high")
PRINCIPAL_2047 = {"scenario": "Principal projection", "horizon": "2047", "baseline": "2022"}


def _claim(pred, subject, qualifiers=None, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": qualifiers or {}, **value}


def test_the_two_are_registered_once_and_well_formed():
    names = [p.name for p in SEED_PREDICATES]
    for n in MINTED:
        assert names.count(n) == 1, n
        assert validate_predicate_def(PREDICATE_REGISTRY[n]) == [], n


def test_each_has_the_shape_the_proposal_gives():
    for n, (vt, card, applies, grain, req) in MINTED.items():
        p = PREDICATE_REGISTRY[n]
        assert (p.value_type, p.cardinality, p.applies_to_types) == (vt, card, applies), n
        assert p.finest_grain is grain, n
        assert p.required_qualifiers == req, n


def test_the_three_heritage_within_predicates_share_one_shape():
    shapes = {(p.value_type, p.cardinality, p.applies_to_types, p.finest_grain)
              for p in (PREDICATE_REGISTRY[n] for n in HERITAGE_THREE)}
    assert shapes == {("text", "multi", ("building",), Grain.PROPERTY)}


def test_no_welsh_is_written_and_the_literal_is_gone():
    # The two 0.2.16 entries held the literal "CY_PENDING", which is not the sentinel.
    for n in HERITAGE_THREE + ("population_projection",):
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n
    assert not [p.name for p in SEED_PREDICATES if p.description_cy == "CY_PENDING"]


def test_wreck_is_a_building_within_flag():
    ok = _claim("within_protected_wreck", "b1", value_text="Cadw PW-0001")
    assert validate_claim(ok, subject_entity_type="building") == []
    assert validate_claim(ok, subject_entity_type="area")


def test_projection_is_an_area_count_that_needs_variant_year_and_base():
    ok = _claim("population_projection", "area:W06000002", PRINCIPAL_2047,
                value_int=123456, value_en="all ages")
    assert validate_claim(ok, subject_entity_type="area") == []
    assert validate_claim(ok, subject_entity_type="building")
    for missing in ("scenario", "horizon", "baseline"):
        q = {k: v for k, v in PRINCIPAL_2047.items() if k != missing}
        bad = _claim("population_projection", "area:W06000002", q, value_int=123456)
        assert validate_claim(bad, subject_entity_type="area"), missing


def test_projection_says_what_it_is_and_is_not():
    d = PREDICATE_REGISTRY["population_projection"].description_en
    assert "projection" in d.lower() and "not a forecast" in d.lower()
    assert "population_estimate" in d          # points to the observed sibling
    assert "variant" in d.lower()
