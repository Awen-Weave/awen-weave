"""Constitution 0.1.8 in the grammar: `tide_level`, a required `vertical_datum`, and multi series.

WHY THIS TEST EXISTS
====================
Ruled by Huw as Llys, 26/09/2026 [sig:c8426dc4] (dispatch 428): Option C of the Climate
tide-level proposal with every amendment of the 424 independent pass, bundled into constitution
0.1.8 with `geometry_basis += field-placed-witnessed` (dispatch 417) and
`verification_method += sensor-measured` (dispatch 381).

WHERE THE REQUIREMENT IS ENFORCED (424 pass, N1). `vertical_datum` is required on `tide_level`
and `water_level` HERE — `PredicateDef.required_qualifiers`, checked by `validate_claim` and so by
`craidd.validation_gate`, which every catalogue snapshot module calls. The constitution schema
carries no per-predicate requirement (the `travel_mode` precedent), so a producer that validates
only against porth is not refused. These tests are the guard for the requirement; the drift
check (scripts/constitution_drift.py) is the guard for the vocabulary.

`unstated` ONLY WHERE THE PUBLISHER SAYS SO (N3). The unit->datum table is total over the units
the estate has measured, refuses an unknown unit rather than guessing, and yields `unstated` only
from the units that themselves state no datum (EA bare `m`, "metres with an unspecified datum",
and `---`). A snapshot that carries level claims reports its per-datum counts, `unstated`
included, so a layer leaning on it is visible in its own manifest.
"""
from __future__ import annotations

import json

import pytest

from craidd import CONSTITUTION_TAG, CONSTITUTION_VERSION
from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY
from craidd.schema.grain import Grain
from craidd.schema.qualifiers import (
    CLOSED_QUALIFIER_DOMAINS,
    GEOMETRY_BASES,
    QUALIFIER_KEYS,
    VERIFICATION_METHODS,
    VERTICAL_DATUMS,
)
from craidd.schema.validation import validate_claim
from craidd.schema.vertical_datum import (
    DATUM_REQUIRED_PREDICATES,
    UNIT_TO_DATUM,
    UnknownUnit,
    datum_counts,
    datum_for_unit,
)

FOUR = {"ordnance-datum-newlyn", "chart-datum", "local-stage-datum", "unstated"}
STATION_WATER = ("tide_level", "water_flow", "water_level", "rainfall", "groundwater_level")


def _level_claim(predicate: str, **qualifiers) -> dict:
    return {
        "subject_id": "STN-E70039",
        "predicate": predicate,
        "value_real": 3.412,
        "source_id": "SRC-EA-FLOOD-MONITORING",
        "recorded_by": "catalogue@awenweave.com",
        "confidence": "high",
        "qualifiers": {"binding": "measured", **qualifiers},
    }


# --- the vocabulary -----------------------------------------------------------------------

def test_vertical_datum_is_a_closed_domain_of_the_four_ruled_values():
    assert VERTICAL_DATUMS == FOUR
    assert CLOSED_QUALIFIER_DOMAINS["vertical_datum"] is VERTICAL_DATUMS
    assert "vertical_datum" in QUALIFIER_KEYS


def test_key_and_closed_domain_counts_are_24_and_10():
    assert len(QUALIFIER_KEYS) == 24
    assert len(CLOSED_QUALIFIER_DOMAINS) == 10


def test_the_two_bundled_values_ride_the_same_release():
    assert "sensor-measured" in VERIFICATION_METHODS
    assert {"on-site", "aerial", "local-knowledge", "documentary", "desk-derived"} <= VERIFICATION_METHODS
    assert "field-placed-witnessed" in GEOMETRY_BASES
    assert "curator-placed" in GEOMETRY_BASES


def test_the_package_pins_constitution_0_1_8():
    assert CONSTITUTION_VERSION == "0.1.8"
    assert CONSTITUTION_TAG == "v0.1.8"


# --- the predicates -----------------------------------------------------------------------

def test_tide_level_is_registered_on_station_as_a_multi_real_series_requiring_its_datum():
    p = PREDICATE_REGISTRY["tide_level"]
    assert p.value_type == "real"
    assert p.cardinality == "multi"
    assert p.applies_to_types == ("station",)
    assert p.required_qualifiers == ("vertical_datum",)
    assert p.description_cy == CY_PENDING          # N5: no invented Welsh
    assert p.finest_grain is Grain.PROPERTY
    assert "vertical_datum" in p.description_en


def test_water_level_requires_the_datum_and_says_so():
    p = PREDICATE_REGISTRY["water_level"]
    assert p.required_qualifiers == ("vertical_datum",)
    assert "vertical_datum" in p.description_en
    assert "or mAOD where datum-referenced" not in p.description_en


def test_all_five_station_water_predicates_are_multi():
    """B4: the 06/08 ratified text said multi ('a site carries a time series'); the code said
    single. Ruled multi for all five."""
    assert {n: PREDICATE_REGISTRY[n].cardinality for n in STATION_WATER} == {
        n: "multi" for n in STATION_WATER}


def test_the_three_not_asked_about_keep_no_required_datum():
    """Only tide_level and water_level were ruled to require it; groundwater (mAOD/mBDAT),
    flow and rainfall are not heights against a datum or were not in the ask."""
    for n in ("water_flow", "rainfall", "groundwater_level"):
        assert "vertical_datum" not in PREDICATE_REGISTRY[n].required_qualifiers, n
    assert DATUM_REQUIRED_PREDICATES == frozenset({"tide_level", "water_level"})
    for n in DATUM_REQUIRED_PREDICATES:
        assert "vertical_datum" in PREDICATE_REGISTRY[n].required_qualifiers


# --- refusal at validation (the surface N1 names) -------------------------------------------

@pytest.mark.parametrize("predicate", ["tide_level", "water_level"])
def test_a_level_with_no_datum_is_refused(predicate):
    errors = validate_claim(_level_claim(predicate), subject_entity_type="station")
    assert any("requires the 'vertical_datum' qualifier" in e for e in errors), errors


@pytest.mark.parametrize("predicate", ["tide_level", "water_level"])
def test_an_unknown_datum_is_refused(predicate):
    errors = validate_claim(_level_claim(predicate, vertical_datum="mean-sea-level"),
                            subject_entity_type="station")
    assert any("vertical_datum" in e and "not one of" in e for e in errors), errors


@pytest.mark.parametrize("predicate", ["tide_level", "water_level"])
@pytest.mark.parametrize("datum", sorted(FOUR))
def test_each_ruled_datum_is_accepted_including_unstated(predicate, datum):
    assert validate_claim(_level_claim(predicate, vertical_datum=datum),
                          subject_entity_type="station") == []


def test_a_tide_level_on_a_coastal_cell_is_refused():
    """A reading is taken by an instrument at a place; a sediment-cell area is the mis-attachment
    the station amendment's five-ways test exists to prevent."""
    errors = validate_claim(_level_claim("tide_level", vertical_datum="chart-datum"),
                            subject_entity_type="coastal_cell")
    assert any("does not apply to entity type" in e for e in errors), errors


def test_a_sensor_measured_reading_validates():
    claim = _level_claim("water_level", vertical_datum="local-stage-datum",
                         verification_method="sensor-measured")
    assert validate_claim(claim, subject_entity_type="station") == []


# --- the unit -> datum table (N3) -----------------------------------------------------------

def test_the_unit_table_maps_each_publisher_unit_to_its_ruled_datum():
    assert UNIT_TO_DATUM == {
        "mAOD": "ordnance-datum-newlyn",
        "mASD": "local-stage-datum",
        "mACD": "chart-datum",
        "m": "unstated",
        "---": "unstated",
    }


def test_unstated_arises_ONLY_from_the_units_that_state_no_datum():
    assert {u for u, d in UNIT_TO_DATUM.items() if d == "unstated"} == {"m", "---"}
    for unit, datum in UNIT_TO_DATUM.items():
        assert datum_for_unit(unit) == datum
        assert datum in VERTICAL_DATUMS


def test_the_table_covers_every_datum_value():
    assert set(UNIT_TO_DATUM.values()) == VERTICAL_DATUMS


@pytest.mark.parametrize("unit", ["mBDAT", "ft", "", "MAOD", " mAOD", "mLAT", None])
def test_an_unknown_unit_is_refused_never_guessed(unit):
    """An unmapped unit is a gap to report, not a reason to reach for `unstated` or the nearest
    datum. mBDAT is a sign convention below a datum, not a datum (proposal §2.2)."""
    with pytest.raises(UnknownUnit):
        datum_for_unit(unit)


# --- the per-layer count in the snapshot report ---------------------------------------------

def test_datum_counts_reports_every_value_including_zero_unstated():
    claims = [
        _level_claim("tide_level", vertical_datum="ordnance-datum-newlyn"),
        _level_claim("water_level", vertical_datum="local-stage-datum"),
        _level_claim("water_level", vertical_datum="local-stage-datum"),
    ]
    assert datum_counts(claims) == {
        "chart-datum": 0, "local-stage-datum": 2, "ordnance-datum-newlyn": 1, "unstated": 0}


def test_datum_counts_counts_unstated():
    claims = [_level_claim("water_level", vertical_datum="unstated"),
              _level_claim("tide_level", vertical_datum="unstated")]
    assert datum_counts(claims)["unstated"] == 2


def test_datum_counts_is_none_for_a_layer_with_no_level_claims():
    """A layer with nothing to count reports nothing, so every existing snapshot's manifest is
    byte-identical after this release."""
    assert datum_counts([{"predicate": "address", "qualifiers": {}}]) is None


def test_datum_counts_accepts_qualifiers_as_stored_json():
    claim = _level_claim("tide_level", vertical_datum="chart-datum")
    claim["qualifiers"] = json.dumps(claim["qualifiers"])
    assert datum_counts([claim])["chart-datum"] == 1


def test_the_snapshot_manifest_carries_the_per_datum_count(tmp_path):
    from craidd.snapshot import SnapshotBuilder, SnapshotRecords
    from craidd.validation_gate import ConstitutionPin, ValidationResult

    class _Gate:
        def validate(self, kind, doc):
            return ValidationResult(kind=kind, valid=True, violations=[])

        def pin(self):
            return ConstitutionPin(constitution_version="0.1.8", constitution_tag="v0.1.8",
                                   constitution_commit="x", source="vendored")

    records = SnapshotRecords(claims=[
        _level_claim("water_level", vertical_datum="unstated"),
        _level_claim("tide_level", vertical_datum="ordnance-datum-newlyn"),
    ])
    manifest = SnapshotBuilder(_Gate())._manifest(records, "sid", "2026-09-26T00:00:00Z")
    assert manifest["counts"]["vertical_datum"] == {
        "chart-datum": 0, "local-stage-datum": 0, "ordnance-datum-newlyn": 1, "unstated": 1}

    empty = SnapshotBuilder(_Gate())._manifest(SnapshotRecords(), "sid", "2026-09-26T00:00:00Z")
    assert "vertical_datum" not in empty["counts"]


# --- the drift check sees the new vocabulary (N2: use the existing check, prove it fails) -----

def _drift_module():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / "scripts" / "constitution_drift.py"
    spec = importlib.util.spec_from_file_location("constitution_drift_0_1_8", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _vendored_schemas() -> dict:
    from pathlib import Path
    import craidd
    root = Path(craidd.__file__).parent / "constitution_vendor" / "schema"
    return {n: json.loads((root / f"{n}.schema.json").read_text(encoding="utf-8"))
            for n in ("claim", "entity")}


def test_the_drift_check_is_clean_against_the_vendored_0_1_8_schema():
    assert _drift_module().model_diff(_vendored_schemas()) == []


@pytest.mark.parametrize("key,value", [
    ("vertical_datum", "unstated"),
    ("verification_method", "sensor-measured"),
    ("geometry_basis", "field-placed-witnessed"),
])
def test_the_drift_check_REDS_when_the_schema_loses_a_ruled_value(key, value):
    """Proved to fail, not trusted: drop one ruled value from the schema side and the existing
    model diff names that domain."""
    schemas = _vendored_schemas()
    enum = schemas["claim"]["$defs"]["qualifiers"]["properties"][key]["enum"]
    enum.remove(value)
    findings = _drift_module().model_diff(schemas)
    assert any(f.startswith(f"closed_domain.{key}:") and value in f for f in findings), findings


def test_the_drift_check_REDS_when_the_schema_loses_the_key():
    schemas = _vendored_schemas()
    del schemas["claim"]["$defs"]["qualifiers"]["properties"]["vertical_datum"]
    findings = _drift_module().model_diff(schemas)
    assert any(f.startswith("qualifier_keys:") and "vertical_datum" in f for f in findings), findings
