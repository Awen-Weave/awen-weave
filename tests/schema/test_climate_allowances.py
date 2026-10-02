"""The Welsh Government allowance predicates (a one-gate grammar-addition payload, prepared not shipped).

Huw as Llys accepted every recommendation of PROPOSAL-climate-allowances-grammar-2026-10-02-r2.md
on 02/10/2026 [sig:dc82671f]. These tests hold the decisions that page made, so a later edit that
quietly reverses one goes red:

  * one name, one meaning: a council allowance is its own predicate, paired with sea_level_rise_m
    both ways in FALSE_FRIENDS, and sea_level_rise_m itself is untouched (coastal_cell only);
  * the flow and rainfall uplifts require ONLY `horizon`, because the source states no scenario or
    baseline for those tables (Climate's reading, [sig:9fdf7354]);
  * every one is AREA grain and refuses a station or building subject;
  * no Welsh is written: each description_cy is the pending sentinel until a tutor attests it.
"""
from __future__ import annotations

from craidd.schema.grain import Grain
from craidd.schema.predicates import (
    CY_PENDING, FALSE_FRIENDS, PREDICATE_REGISTRY, SEED_PREDICATES,
)
from craidd.schema.validation import validate_claim, validate_predicate_def

SLR = "sea_level_rise_allowance_m"
FLOW = "peak_river_flow_allowance_pct"
RAIN = "rainfall_intensity_allowance_pct"
NEW = (SLR, FLOW, RAIN)

BASE = dict(subject_id="area:W06000002", source_id="src:wg-climate-change-allowances-2026-03",
            recorded_by="arloesidolgellau", confidence="high", value_real=1.0)


def _claim(pred, qualifiers, **kw):
    return {**BASE, "predicate": pred, "qualifiers": qualifiers, **kw}


def test_the_three_are_registered_once_and_valid():
    names = [p.name for p in SEED_PREDICATES]
    for n in NEW:
        assert names.count(n) == 1, n
        assert validate_predicate_def(PREDICATE_REGISTRY[n]) == [], n


def test_each_is_area_grain_real_multi_and_area_only():
    for n in NEW:
        p = PREDICATE_REGISTRY[n]
        assert (p.value_type, p.cardinality, p.applies_to_types) == ("real", "multi", ("area",)), n
        assert p.finest_grain is Grain.AREA, n


def test_required_qualifiers_follow_what_the_source_states():
    assert PREDICATE_REGISTRY[SLR].required_qualifiers == ("scenario", "horizon", "baseline")
    assert PREDICATE_REGISTRY[FLOW].required_qualifiers == ("horizon",)
    assert PREDICATE_REGISTRY[RAIN].required_qualifiers == ("horizon",)


def test_no_welsh_is_written():
    for n in NEW:
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n


def test_sea_level_rise_m_is_unchanged():
    p = PREDICATE_REGISTRY["sea_level_rise_m"]
    assert p.applies_to_types == ("coastal_cell",)
    assert p.required_qualifiers == ("scenario", "horizon", "baseline")
    errs = validate_claim(_claim("sea_level_rise_m", {"scenario": "RCP8.5", "horizon": "2100",
                                                      "baseline": "1981/2000"}),
                          subject_entity_type="area")
    assert any("does not apply to entity type 'area'" in e for e in errs)


def test_the_false_friend_pair_runs_both_ways():
    pairs = {(f.name, f.use_instead) for f in FALSE_FRIENDS}
    assert ("sea_level_rise_m", SLR) in pairs
    assert (SLR, "sea_level_rise_m") in pairs


def test_a_council_sea_level_allowance_validates_with_the_full_triple():
    q = {"scenario": "RCP8.5", "horizon": "2100", "baseline": "1981/2000",
         "semantics_caveat": "Welsh Government planning allowance, 70th percentile, Table 3 pp.5-6"}
    assert validate_claim(_claim(SLR, q, value_real=0.82), subject_entity_type="area") == []
    del q["baseline"]
    assert validate_claim(_claim(SLR, q, value_real=0.82), subject_entity_type="area")


def test_an_uplift_validates_on_horizon_alone_and_refuses_a_borrowed_scenario():
    note = ("Upper allowance, Table 1 p.3; RCP8.5 stated document-wide on p.1; "
            "baseline not stated by the source")
    for n in (FLOW, RAIN):
        ok = _claim(n, {"horizon": "2070/2125", "semantics_caveat": note}, value_real=50.0)
        assert validate_claim(ok, subject_entity_type="area") == [], n
        # carrying p.1's scenario would pull in a baseline the source does not give
        borrowed = _claim(n, {"horizon": "2070/2125", "scenario": "RCP8.5"}, value_real=50.0)
        assert validate_claim(borrowed, subject_entity_type="area"), n
        assert validate_claim(_claim(n, {}, value_real=50.0), subject_entity_type="area"), n


def test_finer_subjects_are_refused():
    for n in NEW:
        q = {"scenario": "x", "horizon": "y", "baseline": "z"}
        for t in ("station", "building", "coastal_cell"):
            assert validate_claim(_claim(n, q), subject_entity_type=t), (n, t)
