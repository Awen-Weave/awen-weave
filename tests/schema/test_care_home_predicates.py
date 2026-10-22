"""The eleven CIW care home predicates (awen-weave 0.2.41, PROPOSED).

Section 2 of PROPOSAL-care-home-predicates-2026-10-14.md (awen-shared main, as merged in #809), ruled by
Huw [sig:7d9c7466]: the 11 predicates approved; care_home_supports' six terms enforced; the as-of date
of a rating is source_ran_at only. Each applies to `building` at property grain, keyed on the service
address UPRN, for the ciw-adult-care-homes layer. Values are CIW's verbatim. No constitution change and no
new qualifier key (source_ran_at and semantics_caveat already exist). url and inspection_date untouched.
"""
from __future__ import annotations

import json

import pytest

from craidd.schema.predicates import CARE_HOME_SUPPORTS, CY_PENDING, PREDICATE_REGISTRY, Grain
from craidd.schema.validation import VALUE_CHECKED_PREDICATES, validate_claim

# name -> (value_type, cardinality), exactly as the page's section 2
SECTION_2 = {
    "care_home_urn": ("text", "multi"),
    "care_home_type": ("text", "single"),
    "care_home_sub_type": ("text", "single"),
    "care_home_supports": ("text", "multi"),
    "care_home_max_places": ("int", "single"),
    "care_home_language": ("text", "single"),
    "care_home_website": ("text", "single"),
    "care_home_rating_well_being": ("text", "single"),
    "care_home_rating_care_support": ("text", "single"),
    "care_home_rating_leadership_management": ("text", "single"),
    "care_home_rating_environment": ("text", "single"),
}
RATINGS = [n for n in SECTION_2 if n.startswith("care_home_rating_")]
SIX = ("dementia", "mental health", "learning disability", "short breaks/respite",
       "physical disability", "younger adults up to 25")


@pytest.mark.parametrize("name,shape", sorted(SECTION_2.items()))
def test_each_predicate_is_as_section_2_says(name, shape):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality) == shape
    assert p.applies_to_types == ("building",) and p.finest_grain == Grain.PROPERTY
    assert p.required_qualifiers == ()                 # no new qualifier key
    assert p.description_cy == CY_PENDING              # pending for Catrin


def test_exactly_eleven_care_home_predicates():
    assert sorted(n for n in PREDICATE_REGISTRY if n.startswith("care_home_")) == sorted(SECTION_2)


@pytest.mark.parametrize("name", sorted(SECTION_2))
def test_values_are_ciws_verbatim(name):
    assert "verbatim" in PREDICATE_REGISTRY[name].description_en


def test_max_places_is_capacity_never_occupancy():
    d = PREDICATE_REGISTRY["care_home_max_places"].description_en
    assert "registered capacity" in d and "never occupancy" in d


@pytest.mark.parametrize("name", RATINGS)
def test_each_rating_is_as_published_at_source_ran_at_not_an_inspection_date(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "as published in CIW's extract at source_ran_at" in d
    assert "not an inspection date" in d


def test_url_and_inspection_date_are_untouched():
    assert PREDICATE_REGISTRY["url"].applies_to_types == ("source",)
    assert PREDICATE_REGISTRY["inspection_date"].description_en == "Date the assessment was carried out."


# ── care_home_supports' closed list, enforced ───────────────────────────────────────────────────
def _errors(value: str) -> list:
    claim = {"subject_id": "building:10023456789", "predicate": "care_home_supports",
             "value_text": value, "source_id": "ciw-care-services-extract",
             "recorded_by": "test@example.org", "confidence": "high", "qualifiers": {"binding": "asserted"}}
    return validate_claim(claim, subject_entity_type="building")


def test_the_six_terms_are_the_closed_list_and_enforced():
    assert CARE_HOME_SUPPORTS == SIX
    assert json.loads(PREDICATE_REGISTRY["care_home_supports"].constraint_json) == {"enum": list(SIX)}
    assert "care_home_supports" in VALUE_CHECKED_PREDICATES


@pytest.mark.parametrize("term", SIX)
def test_each_term_is_accepted(term):
    assert _errors(term) == [], term


@pytest.mark.parametrize("bad", ["dementa", "Dementia", "mental-health", "short breaks", "respite",
                                 "younger adults", "nursing", ""])
def test_a_misspelt_or_unknown_term_is_refused(bad):
    assert _errors(bad), bad


def test_the_registry_holds_282():
    assert len(PREDICATE_REGISTRY) == 282
