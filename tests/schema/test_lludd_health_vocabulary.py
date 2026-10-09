"""Lludd step-0 health vocabulary (card c0616), carried in the phase 9 piece 1 release (c0615).

PROPOSED, not ratified. The Lludd seat sent the 13 predicates inline in its record
(awen_signals.mac5.lludd.jsonl, ts 2026-10-09T14:01:34Z, resolves c0616); 01 October Seat 1 carries
them as written into awen-weave 0.2.30 so the grammar goes through the one gate once. These tests
hold the shape the record gives, so a later edit that changes one goes red:

  * a new _LLUDD_HEALTH group; every dimension (register, sex/age band, site, period, programme,
    practice) rides the bilingual label value_en/value_cy, as population_estimate does, so no new
    qualifier key and no constitution change;
  * only existing qualifier keys are required: source_ran_at, and semantics_caveat on the crude
    prevalence (it names its denominator);
  * no Welsh is written: every description_cy is the pending sentinel.
"""
from __future__ import annotations

from craidd.schema.grain import Grain
from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES
from craidd.schema.qualifiers import QUALIFIER_KEYS
from craidd.schema.validation import validate_claim, validate_predicate_def

# name -> (value_type, cardinality, applies_to, grain, required_qualifiers), as the record gives
MINTED = {
    "disease_register_count": ("int", "multi", ('building', 'area'), Grain.PROPERTY,
        ('source_ran_at',)),
    "disease_prevalence_crude_pct": ("real", "multi", ('building', 'area'), Grain.PROPERTY,
        ('source_ran_at', 'semantics_caveat')),
    "registered_patients_count": ("int", "multi", ('building', 'area'), Grain.PROPERTY,
        ('source_ran_at',)),
    "cancer_incidence_count": ("int", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "cancer_incidence_rate_per_100k_esp2013": ("real", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "cancer_mortality_count": ("int", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "cancer_mortality_rate_per_100k_esp2013": ("real", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "cancer_net_survival_pct": ("real", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "screening_uptake_pct": ("real", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "screening_coverage_pct": ("real", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "cancer_pathway_within_target_pct": ("real", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "cancer_pathway_patients_count": ("int", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
    "registered_patients_resident_count": ("int", "multi", ('area',), Grain.AREA,
        ('source_ran_at',)),
}

BASE = dict(source_id="src:lludd-test", recorded_by="lludd", confidence="high")
RAN = {"source_ran_at": "2026-03-31T00:00:00Z"}


def _claim(pred, subject, qualifiers=None, **value):
    return {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": qualifiers or {}, **value}


def test_the_thirteen_are_registered_once_and_well_formed():
    names = [p.name for p in SEED_PREDICATES]
    for n in MINTED:
        assert names.count(n) == 1, n
        assert validate_predicate_def(PREDICATE_REGISTRY[n]) == [], n


def test_each_has_the_shape_the_record_gives():
    for n, (vt, card, applies, grain, req) in MINTED.items():
        p = PREDICATE_REGISTRY[n]
        assert (p.value_type, p.cardinality, p.applies_to_types) == (vt, card, applies), n
        assert p.finest_grain is grain, n
        assert p.required_qualifiers == req, n


def test_only_existing_qualifier_keys_no_constitution_change():
    for n, (*_, req) in MINTED.items():
        assert set(req) <= QUALIFIER_KEYS, n


def test_no_welsh_is_written():
    for n in MINTED:
        assert PREDICATE_REGISTRY[n].description_cy == CY_PENDING, n


def test_a_practice_count_is_a_building_or_area_fact_and_needs_its_reference_date():
    ok = _claim("disease_register_count", "building:W94001", RAN, value_int=812,
                value_en="Diabetes (17+)")
    assert validate_claim(ok, subject_entity_type="building") == []
    assert validate_claim(ok, subject_entity_type="area") == []
    assert validate_claim(_claim("disease_register_count", "building:W94001", value_int=812),
                          subject_entity_type="building")


def test_crude_prevalence_must_name_its_denominator():
    bad = _claim("disease_prevalence_crude_pct", "area:W11000023", RAN, value_real=7.9)
    assert validate_claim(bad, subject_entity_type="area")
    ok = _claim("disease_prevalence_crude_pct", "area:W11000023",
                {**RAN, "semantics_caveat": "denominator: registered_patients_count, all ages"},
                value_real=7.9)
    assert validate_claim(ok, subject_entity_type="area") == []


def test_cancer_figures_are_area_facts():
    ok = _claim("cancer_incidence_count", "area:W11000023", RAN, value_int=4100,
                value_en="All cancers, persons, 2019-2021")
    assert validate_claim(ok, subject_entity_type="area") == []
    assert validate_claim(ok, subject_entity_type="building")
