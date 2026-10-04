"""The Open Evidence grammar decisions (a one-gate grammar addition, awen-weave 0.2.28).

Huw as Llys accepted all ten recommendations of PROPOSAL-open-evidence-grammar-2026-10-03.md
section 3 on 04/10/2026 [sig:a40a1dcd], answering question e544a95b. The page is on GitHub at
Awen-Weave/open-evidence docs/PROPOSAL-open-evidence-grammar-2026-10-03.md (#4). These tests hold
what that ruling decided, so a later edit that quietly reverses one goes red:

  * eight predicates are minted (G1-G7, G9) and two are NOT (G8 main_issue, G10 hmo_share: deferred);
  * the area statistics (G1, G9) are AREA grain and refuse a building or site subject;
  * the property tests (G2-G4) bind to building and site; G3 also to area;
  * G5-G7 are event identifiers, NOT_SPATIAL;
  * P-1: conservation_area and listed_grade also bind to `site`; listed_id does NOT (decision 8b);
  * P-2: decision_outcome is a closed domain granted/refused/split/withdrawn, refused off-domain by
    validate_claim (Mac 6's estate search found every held value inside it), with the MHCLG
    grant/refuse mapping for export; listed_grade stays unenforced (decision 7);
  * no Welsh is written: every new description_cy is the pending sentinel.
"""
from __future__ import annotations

import json

import pytest

from craidd.schema.grain import Grain
from craidd.schema.predicates import (
    CY_PENDING, FALSE_FRIENDS, PREDICATE_REGISTRY, SEED_PREDICATES,
)
from craidd.schema.validation import (
    VALUE_CHECKED_PREDICATES, validate_claim, validate_predicate_def,
)

# name -> (value_type, cardinality, applies_to, grain, required_qualifiers)
MINTED = {
    "decision_grant_share": ("real", "multi", ("area",), Grain.AREA, ("source_ran_at",)),       # G1
    "in_flood_zone": ("text", "single", ("building", "site"), Grain.PROPERTY, ("source_ran_at",)),  # G2
    "within_article_4_direction": ("text", "multi", ("building", "site", "area"), Grain.PROPERTY,
                                   ("source_ran_at",)),                                          # G3
    "near_listed_building": ("text", "multi", ("building", "site"), Grain.PROPERTY,
                             ("source_ran_at",)),                                                # G4
    "policy_cited": ("text", "multi", ("event",), Grain.NOT_SPATIAL, ()),                        # G5
    "cites_decision": ("text", "multi", ("event",), Grain.NOT_SPATIAL, ()),                      # G6
    "appeal_reference": ("text", "single", ("event",), Grain.NOT_SPATIAL, ()),                   # G7
    "median_price_paid_gbp": ("real", "multi", ("area",), Grain.AREA, ("source_ran_at",)),      # G9
}
DEFERRED = ("main_issue", "hmo_share")                                                           # G8, G10
OUTCOMES = ["granted", "refused", "split", "withdrawn"]

BASE = dict(source_id="src:oe-test", recorded_by="open-evidence", confidence="high")
RAN = {"source_ran_at": "2026-10-04T00:00:00Z"}


def _claim(pred, subject, qualifiers=None, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": qualifiers or {}, **value}


def test_the_eight_are_registered_once_and_well_formed():
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


def test_g8_and_g10_are_deferred_not_minted():
    for n in DEFERRED:
        assert n not in PREDICATE_REGISTRY, n


def test_no_welsh_is_written():
    for n in MINTED:
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n


def test_the_area_statistics_refuse_a_property_subject():
    for n in ("decision_grant_share", "median_price_paid_gbp"):
        ok = _claim(n, "area:E08000012", RAN, value_real=0.5)
        assert validate_claim(ok, subject_entity_type="area") == [], n
        for t in ("building", "site"):
            assert validate_claim(ok, subject_entity_type=t), (n, t)


def test_the_area_statistics_need_their_run_time():
    for n in ("decision_grant_share", "median_price_paid_gbp"):
        assert validate_claim(_claim(n, "area:E08000012", {}, value_real=0.5), subject_entity_type="area"), n


def test_in_flood_zone_is_a_property_test_with_a_declared_zone_domain():
    p = PREDICATE_REGISTRY["in_flood_zone"]
    assert json.loads(p.constraint_json)["enum"] == ["FZ1", "FZ2", "FZ3"]
    for t in ("building", "site"):
        assert validate_claim(_claim("in_flood_zone", "x", RAN, value_text="FZ3"), subject_entity_type=t) == [], t
    assert validate_claim(_claim("in_flood_zone", "x", RAN, value_text="FZ3"), subject_entity_type="area")


def test_flood_coverage_now_also_points_a_site_reader_to_in_flood_zone():
    pairs = {(f.name, f.use_instead) for f in FALSE_FRIENDS}
    assert ("flood_coverage", "properties_at_flood_risk_count") in pairs   # the existing entry stays
    assert ("flood_coverage", "in_flood_zone") in pairs


def test_the_event_identifiers_validate_on_an_event():
    for n, v in (("policy_cited", "Local Plan 2013-2033 H10"), ("cites_decision", "APP/X0000/W/24/0000000"),
                 ("appeal_reference", "APP/X0000/W/24/0000000")):
        assert validate_claim(_claim(n, "event:oe-1", value_text=v), subject_entity_type="event") == [], n
        assert validate_claim(_claim(n, "event:oe-1", value_text=v), subject_entity_type="building"), n


def test_p1_conservation_area_and_listed_grade_bind_to_site_listed_id_does_not():
    assert PREDICATE_REGISTRY["conservation_area"].applies_to_types == ("building", "site")
    assert PREDICATE_REGISTRY["listed_grade"].applies_to_types == ("building", "site")
    assert PREDICATE_REGISTRY["listed_id"].applies_to_types == ("building",)          # decision 8b
    assert validate_claim(_claim("conservation_area", "site:s1", value_text="Dolgellau"),
                          subject_entity_type="site") == []
    assert validate_claim(_claim("listed_grade", "site:s1", value_text="II"), subject_entity_type="site") == []
    assert validate_claim(_claim("listed_id", "site:s1", value_text="Cadw 4938"), subject_entity_type="site")


def test_p1_building_claims_are_unchanged():
    for n, v in (("conservation_area", "Dolgellau"), ("listed_grade", "II"), ("listed_id", "Cadw 4938")):
        assert validate_claim(_claim(n, "b1", value_text=v), subject_entity_type="building") == [], n


def test_p2_decision_outcome_is_a_closed_domain_and_refuses_an_appeal_value():
    p = PREDICATE_REGISTRY["decision_outcome"]
    assert json.loads(p.constraint_json)["enum"] == OUTCOMES
    assert "decision_outcome" in VALUE_CHECKED_PREDICATES
    for v in OUTCOMES:
        assert validate_claim(_claim("decision_outcome", "event:1", value_text=v),
                              subject_entity_type="event") == [], v
    for v in ("dismissed", "allowed", "Permitted with conditions", "grant"):
        errs = validate_claim(_claim("decision_outcome", "event:1", value_text=v), subject_entity_type="event")
        assert any("decision_outcome" in e and "not one of" in e for e in errs), (v, errs)


def test_p2_the_raw_wording_has_a_home_that_validates():
    q = {"semantics_caveat": "authority wording: 'Permitted with conditions'"}
    assert validate_claim(_claim("decision_outcome", "event:1", q, value_text="granted"),
                          subject_entity_type="event") == []


def test_p2_maps_to_the_mhclg_binary_list_at_export():
    from craidd.schema.predicates import decision_outcome_to_mhclg

    assert decision_outcome_to_mhclg("granted") == "grant"
    assert decision_outcome_to_mhclg("refused") == "refuse"
    assert decision_outcome_to_mhclg("split") is None        # the binary list cannot say it
    assert decision_outcome_to_mhclg("withdrawn") is None    # nor this: no decision was made
    with pytest.raises(ValueError):
        decision_outcome_to_mhclg("dismissed")


def test_decision_7_scope_is_kept_for_listed_grade():
    errs = validate_claim(_claim("listed_grade", "b1", value_text="III"), subject_entity_type="building")
    assert not any("not one of" in e for e in errs), errs
    assert "listed_grade" not in VALUE_CHECKED_PREDICATES
