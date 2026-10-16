"""Delayed hospital discharges and online job adverts (PROPOSED; cards c1125, c1130, c1132).

Phase 10 task 10.4 and exit 4. Two sources, each REGISTER FIRST:
  * StatsWales "Delayed hospital discharges: total pathway of care delays and total days delayed,
    April 2023 onwards" (REQ-arloesidolgellau-9fdd66, countersigned 12/10/2026). Its rule: the
    provider health board and the residence local authority are two different counts of the same
    delays, NEVER mixed, summed or joined across. So each view has its own predicates, and a
    board figure can never sit in an authority's predicate.
  * ONS "Labour demand volumes by SOC 2020" (REQ-arloesidolgellau-f89d55, countersigned 15/10/2026
    [sig:fd1a1adc]): new online job adverts by local authority and occupation. Adverts, not
    vacancies; ONS's [x] suppressions are never filled.

The category (reason for delay; SOC 2020 group) and the period ride value_en, the
cancer_pathway_patients_count pattern: int, multi, area, Grain.AREA, source_ran_at required. No
qualifier key, no constitution change.
"""
from __future__ import annotations

import pytest

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

DELAYS = ("care_delays_count_by_provider_board", "care_delays_days_by_provider_board",
          "care_delays_count_by_residence_authority", "care_delays_days_by_residence_authority")
ADVERTS = ("online_job_adverts_count",)


@pytest.mark.parametrize("name", DELAYS + ADVERTS)
def test_each_is_an_int_multi_area_count_with_source_ran_at(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == (
        "int", "multi", ("area",), Grain.AREA)
    assert p.required_qualifiers == ("source_ran_at",)
    assert p.description_cy == CY_PENDING
    assert "value_en" in p.description_en


@pytest.mark.parametrize("name", DELAYS)
def test_each_delays_predicate_names_its_view_and_forbids_mixing_them(name):
    d = PREDICATE_REGISTRY[name].description_en
    if "provider_board" in name:
        assert "health board that PROVIDED the care" in d
        assert "can include patients who live outside its area" in d
    else:
        assert "local authority where the patient LIVES" in d
    assert "never mixed, summed or joined" in d
    assert "reasons nest" in d.lower()
    assert "census day" in d


def test_count_and_days_are_distinct_measures():
    assert "Number of pathway of care delays" in PREDICATE_REGISTRY[DELAYS[0]].description_en
    assert "days delayed" in PREDICATE_REGISTRY[DELAYS[1]].description_en


def test_job_adverts_say_adverts_not_vacancies_and_suppression_is_not_zero():
    d = PREDICATE_REGISTRY["online_job_adverts_count"].description_en
    assert "adverts, not vacancies" in d
    assert "[x]" in d and "never filled" in d
    assert "SOC 2020" in d and "Textkernel" in d


def test_exactly_these_five_are_new():
    assert sorted(n for n in PREDICATE_REGISTRY if n.startswith("care_delays_")) == sorted(DELAYS)
    assert [n for n in PREDICATE_REGISTRY if "job_advert" in n] == list(ADVERTS)


def test_the_registry_holds_236():
    assert len(PREDICATE_REGISTRY) == 236
