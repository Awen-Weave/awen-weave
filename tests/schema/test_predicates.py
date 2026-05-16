"""
Smoke tests for the seed predicate registry — src/craidd/schema/predicates.py.

Pins:
- the seed set itself is well-formed (every PredicateDef passes
  validate_predicate_def);
- expected count (v0.1-schema.md §3.5 enumerates 58 predicates);
- PREDICATE_REGISTRY is a complete name→def lookup with no duplicates;
- value_type and cardinality values are all in their permitted sets;
- a representative selection of well-known predicates resolve.
"""
from __future__ import annotations

from craidd.schema.predicates import (
    CARDINALITIES,
    PREDICATE_REGISTRY,
    SEED_PREDICATES,
    VALUE_TYPES,
)
from craidd.schema.validation import validate_seed_predicates


def test_seed_predicates_validate_clean():
    """The seed set must be self-consistent. If this fails, craidd-init
    would refuse to bootstrap."""
    assert validate_seed_predicates() == []


def test_seed_predicate_count_matches_v01_schema():
    """v0.1-schema.md §3.5 enumerates 58 predicates across building +
    tenancy + event + research_question + source + town."""
    assert len(SEED_PREDICATES) == 58


def test_predicate_registry_matches_seed_set():
    """Registry is a name→def lookup with no duplicates."""
    assert len(PREDICATE_REGISTRY) == len(SEED_PREDICATES)
    for pred in SEED_PREDICATES:
        assert PREDICATE_REGISTRY[pred.name] is pred


def test_no_duplicate_predicate_names():
    names = [p.name for p in SEED_PREDICATES]
    assert len(names) == len(set(names))


def test_every_value_type_is_permitted():
    for pred in SEED_PREDICATES:
        assert pred.value_type in VALUE_TYPES, (
            f"{pred.name} has invalid value_type {pred.value_type!r}"
        )


def test_every_cardinality_is_permitted():
    for pred in SEED_PREDICATES:
        assert pred.cardinality in CARDINALITIES, (
            f"{pred.name} has invalid cardinality {pred.cardinality!r}"
        )


def test_every_predicate_applies_to_at_least_one_type():
    for pred in SEED_PREDICATES:
        assert len(pred.applies_to_types) >= 1, (
            f"{pred.name} has empty applies_to_types"
        )


def test_well_known_predicates_resolve():
    """A handful of predicates the Tŷ Newyddion pilot relies on."""
    expected = {
        "address": ("bilingual", "single", "building"),
        "geometry": ("geom", "single", "building"),
        "uprn": ("int", "single", "building"),
        "name_cy": ("text", "multi", "building"),
        "name_en": ("text", "multi", "building"),
        "build_year": ("int", "single", "building"),
        "floor_area_m2": ("real", "single", "building"),
    }
    for name, (vt, card, applies) in expected.items():
        pred = PREDICATE_REGISTRY[name]
        assert pred.value_type == vt, f"{name} value_type"
        assert pred.cardinality == card, f"{name} cardinality"
        assert applies in pred.applies_to_types, f"{name} applies_to"


def test_name_predicates_require_name_type_qualifier():
    """v0.1-schema.md §3.5 + §3.2 — naming claims carry a required
    name_type qualifier."""
    for name in ("name_cy", "name_en"):
        pred = PREDICATE_REGISTRY[name]
        assert "name_type" in pred.required_qualifiers, (
            f"{name} should require name_type qualifier"
        )
