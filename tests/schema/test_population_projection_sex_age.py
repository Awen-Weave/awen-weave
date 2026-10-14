"""population_projection names the sex and single-year age in value_en / value_cy (awen-weave 0.2.38).

Ruled by Huw 13/10/2026 [sig:105df4ca], Q1 and Q2, on PROPOSAL-wg-projections-age-sex-2026-10-12.md
section 3: the description is amended through the one gate so that value_en names sex and age, in the
words of the registered_patients_count precedent (awen-weave 0.2.30). Today's Persons / all-ages
claims keep value_en 'All ages' byte-identical; the rest write '<Sex>, <Age>'.

ONLY THE DESCRIPTION MOVES. No qualifier key is added (the constitution's set is closed), and the
type, cardinality, applies_to, grain, required qualifiers and Welsh stay exactly as registered.
"""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, Grain

P = PREDICATE_REGISTRY["population_projection"]


def test_the_description_names_sex_and_single_year_age_in_value_en():
    d = P.description_en
    assert "sex and single-year age named in value_en / value_cy" in d
    assert "age band named in" not in d          # the old wording is gone


def test_all_ages_alone_is_the_persons_total():
    d = P.description_en
    assert "'All ages' alone is persons, all ages" in d


def test_the_value_shape_is_sex_then_age():
    assert "'<Sex>, <Age>'" in P.description_en


def test_nothing_but_the_description_moves():
    assert (P.value_type, P.cardinality, P.applies_to_types, P.finest_grain) == (
        "int", "multi", ("area",), Grain.AREA)
    assert P.required_qualifiers == ("scenario", "horizon", "baseline")   # no new qualifier key
    assert P.description_cy == CY_PENDING
    d = P.description_en                          # the rest of the definition stands
    assert "not a forecast" in d.lower() and "population_estimate" in d and "variant" in d.lower()


def test_it_follows_the_registered_patients_count_precedent():
    assert "for the sex and" in PREDICATE_REGISTRY["registered_patients_count"].description_en
    assert "for the sex and" in P.description_en
