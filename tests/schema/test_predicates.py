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
    tenancy + event + research_question + source + town. §10 item 7
    adds two more (verified_building_toid, location_verification_status),
    bringing the total to 60. The 4 Egni demand predicates (post-bootstrap,
    2026-07-20) bring it to 64."""
    assert len(SEED_PREDICATES) == 98


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


# --- §10 item 7 predicate assertions ------------------------------------------

def test_verified_building_toid_predicate_shape():
    """v0.1-schema.md §10 item 7.1 — TOID-string, single, building only,
    requires the three verification-provenance qualifiers."""
    pred = PREDICATE_REGISTRY["verified_building_toid"]
    assert pred.value_type == "text"
    assert pred.cardinality == "single"
    assert pred.applies_to_types == ("building",)
    assert "verification_method" in pred.required_qualifiers
    assert "verified_at" in pred.required_qualifiers
    assert "cache_snapshot_id" in pred.required_qualifiers


def test_location_verification_status_predicate_shape():
    """v0.1-schema.md §10 item 7.1 — enum-as-text status band, building
    only at v0.1 (UPRN-as-subject deferred to v0.3 per Huw 2026-05-16),
    requires cache_snapshot_id for reproducibility, enum constraint."""
    pred = PREDICATE_REGISTRY["location_verification_status"]
    assert pred.value_type == "text"
    assert pred.cardinality == "single"
    assert pred.applies_to_types == ("building",), (
        "v0.1 scope is building only — UPRN entity-type deferred to v0.3"
    )
    assert "cache_snapshot_id" in pred.required_qualifiers
    # Enum carried via constraint_json — the closed set of status bands.
    assert pred.constraint_json is not None
    import json
    constraint = json.loads(pred.constraint_json)
    assert set(constraint["enum"]) == {
        "verified", "auto-snapped", "unsnapped", "contested", "non-postal",
    }


def test_item_7_predicates_pass_validate_predicate_def():
    """Both new predicates must pass the same self-consistency check
    every seed predicate gets at craidd-init bootstrap."""
    from craidd.schema.validation import validate_predicate_def
    for name in ("verified_building_toid", "location_verification_status"):
        pred = PREDICATE_REGISTRY[name]
        assert validate_predicate_def(pred) == [], (
            f"{name} should pass validate_predicate_def cleanly"
        )


# --- Egni demand predicates (post-bootstrap, 2026-07-20) ----------------------

def test_egni_demand_predicate_shapes():
    """The four Egni M2 demand predicates, per the ratified decision note
    §2a. All apply to the existing area/building kinds — no new entity kind."""
    expected = {
        "electricity_consumption_kwh": ("real", "single", "area"),
        "gas_consumption_kwh": ("real", "single", "area"),
        # multi — one claim per main-fuel class in the small area (TS046).
        "heating_fuel_share": ("real", "multi", "area"),
        "main_fuel": ("text", "single", "building"),
    }
    for name, (vt, card, applies) in expected.items():
        pred = PREDICATE_REGISTRY[name]
        assert pred.value_type == vt, f"{name} value_type"
        assert pred.cardinality == card, f"{name} cardinality"
        assert pred.applies_to_types == (applies,), f"{name} applies_to"


def test_egni_demand_predicates_pass_validate_predicate_def():
    """Each demand predicate must pass the same self-consistency check
    craidd-init runs at bootstrap (valid value_type/cardinality, applies_to
    an existing entity type, non-empty descriptions)."""
    from craidd.schema.validation import validate_predicate_def
    for name in (
        "electricity_consumption_kwh", "gas_consumption_kwh",
        "heating_fuel_share", "main_fuel",
    ):
        pred = PREDICATE_REGISTRY[name]
        assert validate_predicate_def(pred) == [], (
            f"{name} should pass validate_predicate_def cleanly"
        )
