"""
Tests for design/proposed-schemas/prawf-batch-commitment.schema.json — the
PROPOSED SCH-BATCH-001 Prawf batch commitment (Huw as Llys, 23/09/2026,
IDR-006-9D914F; Dispatch 381).

The schema is a proposal, not constitution: these tests hold the three design
points the ruling says must survive landing, pin the verbatim draft by digest,
and assert it has not leaked into the vendored constitution or the wheel.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tomllib
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "design" / "proposed-schemas" / "prawf-batch-commitment.schema.json"
# sha256 of the 15/09/2026 draft as landed. An edit to the schema must move
# this pin in the same commit — a proposal changes by a visible act.
DRAFT_SHA256 = "47a22329600096c1d74269f4f5dc87ce503a423c402e181b6d40aa71da98c379"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def validator(schema) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(schema)


def _empty_window() -> dict:
    return {
        "batch_id": "b-0001",
        "period": {"from_utc": "2026-09-23T00:00:00Z", "to_utc": "2026-09-23T01:00:00Z"},
        "devices": [{"source_id": "src-soil-1", "stamp_id": "stamp-soil-1", "stamp_version": 1}],
        "observation_count": 0,
        "storage_ref": "ts://soil/2026-09-23T00",
        "commitment": {
            "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "hash_algorithm": "SHA-256",
            "canonicalisation": "RFC-8785-JCS",
            "leaf_definition": "source_id,stamp_id,stamp_version,observed_at_utc,payload,verification_outcome",
            "previous_root": None,
        },
        "sealed_at_utc": "2026-09-23T01:00:05Z",
        "schema_version": "0.1.7",
        "witness": None,
        "trusted_time": None,
    }


def test_draft_is_verbatim():
    assert hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest() == DRAFT_SHA256


def test_is_valid_json_schema_2020_12(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_rule_id_is_proposed_not_allocated(schema):
    assert schema["x-awen-rule-id"] == "SCH-BATCH-001"
    assert "not allocated" in schema["x-awen-status"]


def test_not_vendored_into_constitution():
    vendor = ROOT / "src" / "craidd" / "constitution_vendor"
    names = {p.name for p in vendor.rglob("*.json")}
    assert "prawf-batch-commitment.schema.json" not in names
    assert not any("SCH-BATCH-001" in p.read_text() for p in vendor.rglob("*.json"))


def test_not_shipped_in_the_wheel():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert not any(p.startswith("design") for p in packages)


def test_empty_window_without_witness_is_recordable_as_itself(validator):
    assert list(validator.iter_errors(_empty_window())) == []


def test_every_device_carries_the_stamp_version_in_force(validator):
    for field in ("stamp_version", "stamp_id", "source_id"):
        doc = _empty_window()
        del doc["devices"][0][field]
        assert not validator.is_valid(doc), field


def test_a_batch_names_at_least_one_device(validator):
    doc = _empty_window()
    doc["devices"] = []
    assert not validator.is_valid(doc)


def test_integrity_is_tallied_per_reading(validator):
    doc = _empty_window()
    doc["observation_count"] = 3
    doc["verification_tally"] = {"verified": 1, "unverified": 1, "failed": 1}
    assert validator.is_valid(doc)
    for field in ("verified", "unverified", "failed"):
        bad = copy.deepcopy(doc)
        del bad["verification_tally"][field]
        assert not validator.is_valid(bad), field


def test_commitment_records_how_it_was_computed(validator):
    for field in ("merkle_root", "hash_algorithm", "canonicalisation", "leaf_definition"):
        doc = _empty_window()
        del doc["commitment"][field]
        assert not validator.is_valid(doc), field


def test_closed_shape_refuses_unknown_fields(validator):
    doc = _empty_window()
    doc["readings"] = [{"value": 0.31}]  # Prawf commits to readings; it never carries them
    assert not validator.is_valid(doc)
