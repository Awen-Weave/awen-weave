"""The Lludd dialysis grammar decisions (a one-gate grammar addition, awen-weave 0.2.29).

Huw as Llys accepted the decisions of PROPOSAL-lludd-dialysis-grammar-2026-10-05.md sections 3-4 as
recommended on 05/10/2026 [sig:75935d1b]. The page is on GitHub at Awen-Weave/lludd
docs/PROPOSAL-lludd-dialysis-grammar-2026-10-05.md (#7, c91aebe). These tests hold what that ruling
decided, so a later edit that quietly reverses one goes red:

  * A-1: ods_code and operational_status are no longer practice-only in their descriptions; their
    type, cardinality and applies_to do not change, so LL01 and gp-locations claims are unchanged;
  * G1 service_provided: building, text, multi, PROPERTY grain, a CLOSED enum that the gate checks
    (it joins VALUE_CHECKED_PREDICATES as decision_outcome did); current_use is its false friend;
  * G2 operated_by: building, text, single, PROPERTY grain; the value is an ODS organisation code
    (an identifier) and the name goes in value_en; organisation and tenant_organisation are its
    false friends;
  * G3 population_share_within_travel_time: area, real (a fraction 0-1), multi, AREA grain,
    required qualifiers source_ran_at and travel_mode; labelled ODbL when Valhalla-derived;
  * no Welsh is written: every new description_cy is the pending sentinel.
"""
from __future__ import annotations

import json

from craidd.schema.grain import Grain
from craidd.schema.predicates import (
    CY_PENDING, FALSE_FRIENDS, PREDICATE_REGISTRY, SEED_PREDICATES,
)
from craidd.schema.validation import (
    VALUE_CHECKED_PREDICATES, validate_claim, validate_predicate_def,
)

# name -> (value_type, cardinality, applies_to, grain, required_qualifiers)
MINTED = {
    "service_provided": ("text", "multi", ("building",), Grain.PROPERTY, ()),               # G1
    "operated_by": ("text", "single", ("building",), Grain.PROPERTY, ()),                   # G2
    "population_share_within_travel_time": ("real", "multi", ("area",), Grain.AREA,
                                            ("source_ran_at", "travel_mode")),              # G3
}
SERVICES = ["haemodialysis-main-unit", "haemodialysis-satellite-unit", "home-therapies-training"]

BASE = dict(source_id="src:lludd-test", recorded_by="lludd", confidence="high")
RAN_BY_CAR = {"source_ran_at": "2026-10-05T00:00:00Z", "travel_mode": "auto"}


def _claim(pred, subject, qualifiers=None, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": qualifiers or {}, **value}


def test_the_three_are_registered_once_and_well_formed():
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


def test_no_welsh_is_written():
    for n in MINTED:
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n


def test_a1_ods_code_and_operational_status_are_not_practice_only():
    for n in ("ods_code", "operational_status"):
        d = PREDICATE_REGISTRY[n].description_en
        assert "ODS-coded organisation or site" in d, n
        assert "for a practice" not in d and "whether a practice" not in d.lower(), n


def test_a1_changes_wording_only():
    for n in ("ods_code", "operational_status"):
        p = PREDICATE_REGISTRY[n]
        assert (p.value_type, p.cardinality, p.applies_to_types) == ("text", "single", ("building",)), n
        assert p.finest_grain is Grain.PROPERTY, n
        assert validate_claim(_claim(n, "b1", value_text="W12345"), subject_entity_type="building") == [], n


def test_g1_service_provided_is_a_gate_checked_closed_enum():
    p = PREDICATE_REGISTRY["service_provided"]
    assert json.loads(p.constraint_json)["enum"] == SERVICES
    assert "service_provided" in VALUE_CHECKED_PREDICATES
    for v in SERVICES:
        assert validate_claim(_claim("service_provided", "b1", value_text=v),
                              subject_entity_type="building") == [], v
    for v in ("dialysis", "Haemodialysis main unit", "renal-unit", "outpatients"):
        errs = validate_claim(_claim("service_provided", "b1", value_text=v), subject_entity_type="building")
        assert any("service_provided" in e and "not one of" in e for e in errs), (v, errs)


def test_g1_is_a_building_fact():
    for t in ("area", "site", "event"):
        assert validate_claim(_claim("service_provided", "x", value_text=SERVICES[0]), subject_entity_type=t), t


def test_g2_operated_by_is_a_building_identifier():
    ok = _claim("operated_by", "b1", value_text="7A1", value_en="Betsi Cadwaladr University Health Board")
    assert validate_claim(ok, subject_entity_type="building") == []
    assert validate_claim(ok, subject_entity_type="area")
    assert "operated_by" not in VALUE_CHECKED_PREDICATES        # an identifier, not a closed list


def test_g3_is_an_area_share_that_needs_its_run_time_and_mode():
    ok = _claim("population_share_within_travel_time", "area:W06000001", RAN_BY_CAR,
                value_real=0.82, value_text="lludd-dialysis-units", value_en="all ages")
    assert validate_claim(ok, subject_entity_type="area") == []
    for t in ("building", "site"):
        assert validate_claim(ok, subject_entity_type=t), t
    for missing in ("source_ran_at", "travel_mode"):
        q = {k: v for k, v in RAN_BY_CAR.items() if k != missing}
        bad = _claim("population_share_within_travel_time", "area:W06000001", q, value_real=0.82)
        assert validate_claim(bad, subject_entity_type="area"), missing


def test_g3_states_its_odbl_label_and_that_it_is_modelled():
    d = PREDICATE_REGISTRY["population_share_within_travel_time"].description_en
    assert "ODbL" in d
    assert "0-1" in d
    assert "not" in d.lower() and "patient" in d.lower()


def test_false_friends_point_readers_to_the_new_predicates():
    pairs = {(f.name, f.use_instead) for f in FALSE_FRIENDS}
    assert ("current_use", "service_provided") in pairs
    assert ("organisation", "operated_by") in pairs
    assert ("tenant_organisation", "operated_by") in pairs


def test_decision_outcome_and_source_kind_stay_value_checked():
    assert {"source_kind", "decision_outcome"} <= VALUE_CHECKED_PREDICATES
