"""
tests/craidd/test_federation_spine.py — the S1 federation spine exit conditions.

Covers the three deliverables against the OFFLINE gate (vendored machine-layer
schemas) so the suite needs no tailnet:
  A. snapshot builder — validates every record, fails loud on any invalid one
     (no partial snapshot), deterministic output, manifest pins.
  B. stamp emitter — reuses provenance_stamp, ran_at_utc read from the source
     (fail loud if missing), claim-level federated gate.
  C. request queue — the requests/{inbox,claimed,done} contract + reader stub.

The live porth gate (PorthValidator) is exercised separately/at deploy on craidd;
here SchemaValidator stands in and validates the same records against the same
pinned constitution machine layer.
"""
from __future__ import annotations

import json

import pytest

from craidd.federation import FederationError, SourceOfRecord
from craidd.gazetteer import federated_name_claim, gazetteer_stamp, place_anchor
from craidd.queue import RequestQueue, QueueError, validate_request, write_request
from craidd.snapshot import (
    SnapshotBuilder,
    SnapshotError,
    SnapshotRecords,
    compact_snapshot_id,
)
from craidd.validation_gate import SchemaValidator, resolve_kind, vendored_pin


BUILT_UTC = "2026-07-11T04:30:00+00:00"
SOURCE_RAN_AT = "2026-05-26T16:04:43+00:00"


def _dol_source() -> SourceOfRecord:
    return SourceOfRecord(
        instance="dolgellau-town-dataset",
        repo="arloesidolgellau/town-dataset",
        framework="tref",
        root="/srv/town-dataset",
        paths={"gazetteer": "craidd.duckdb"},
        ran_at_utc=SOURCE_RAN_AT,
        release="complete",
    )


def _clean_records() -> SnapshotRecords:
    src = _dol_source()
    anchor = place_anchor(
        uprn="200003184697", county_gss="W06000002",
        lat=52.7438, lng=-3.8848,
        label_cy="Tŷ Newyddion", label_en="Glyndwr Buildings",
    )
    claim = federated_name_claim(
        subject_id="TDS-DOL-B-00001", predicate="name_en",
        value="Glyndwr Buildings",
        source_id="TDS-DOL-SRC-INTERNAL-HUW-2026",
        recorded_by="huw@arloesidolgellau.cymru",
        source=src, name_type="vernacular", dialect="cy-GB-north",
    )
    stamp = gazetteer_stamp(
        source=src, consumer_instance="care-home-insight",
        craidd_node="place:dolgellau", craidd_source="dolgellau-town-dataset",
        grade="B", counts={"place_anchors": 1, "claims": 1},
        federated_utc=BUILT_UTC,
    )
    return SnapshotRecords(
        place_anchors=[anchor], claims=[claim], stamps=[stamp],
        source_ran_at={"dolgellau-town-dataset": SOURCE_RAN_AT},
    )


# --- gate sanity -------------------------------------------------------------

def test_offline_gate_accepts_clean_records():
    gate = SchemaValidator()
    recs = _clean_records()
    assert gate.validate("place-anchor", recs.place_anchors[0]).valid
    assert gate.validate("claim", recs.claims[0]).valid
    assert gate.validate("federation-stamp", recs.stamps[0]).valid


def test_resolve_kind_aliases():
    assert resolve_kind("SCH-FEDERATION-001") == "federation-stamp"
    assert resolve_kind("honiad") == "claim"


# --- Deliverable B: stamp emitter -------------------------------------------

def test_stamp_reuses_provenance_stamp_shape():
    stamp = _clean_records().stamps[0]
    assert stamp["binding"] == "federated"
    assert stamp["source_of_record"]["instance"] == "dolgellau-town-dataset"
    # ran_at_utc is the SOURCE run time; federated_utc is the read time — distinct.
    assert stamp["source_of_record"]["ran_at_utc"] == SOURCE_RAN_AT
    assert stamp["read"]["federated_utc"] == BUILT_UTC
    assert stamp["source_of_record"]["ran_at_utc"] != stamp["read"]["federated_utc"]


def test_stamp_fails_loud_without_source_ran_at():
    src = _dol_source()
    src.ran_at_utc = None  # verify-not-recall: no manufactured run-UTC
    with pytest.raises(FederationError):
        gazetteer_stamp(source=src, consumer_instance="care-home-insight")


def test_federated_claim_carries_gate_qualifiers():
    claim = _clean_records().claims[0]
    q = claim["qualifiers"]
    assert q["binding"] == "federated"
    assert q["federated_from"] == "dolgellau-town-dataset"
    assert q["source_ran_at"] == SOURCE_RAN_AT


# --- Deliverable A: snapshot builder ----------------------------------------

def test_build_writes_snapshot_and_manifest(tmp_path):
    gate = SchemaValidator()
    snap_dir = SnapshotBuilder(gate).build(
        _clean_records(), tmp_path, built_utc=BUILT_UTC,
    )
    assert snap_dir.name == "snapshot-20260711T043000Z"
    for fname in ("manifest.json", "place-anchors.json", "claims.json", "stamps.json"):
        assert (snap_dir / fname).is_file()
    manifest = json.loads((snap_dir / "manifest.json").read_text())
    assert manifest["counts"] == {"place_anchors": 1, "claims": 1, "stamps": 1}
    # source_ran_at carried verbatim from the source (verify-not-recall).
    assert manifest["source_ran_at"]["dolgellau-town-dataset"] == SOURCE_RAN_AT
    # pins present; offline build records the vendored pin source.
    assert manifest["pins"]["awen_weave"] == "0.2.0"
    assert manifest["pins"]["constitution_tag"] == vendored_pin().constitution_tag
    assert manifest["constitution_pin_source"] == "vendored"


def test_build_is_deterministic(tmp_path):
    gate = SchemaValidator()
    a = SnapshotBuilder(gate).build(_clean_records(), tmp_path / "a", built_utc=BUILT_UTC)
    b = SnapshotBuilder(gate).build(_clean_records(), tmp_path / "b", built_utc=BUILT_UTC)
    for fname in ("manifest.json", "place-anchors.json", "claims.json", "stamps.json"):
        assert (a / fname).read_text() == (b / fname).read_text()


def test_build_fails_loud_and_writes_nothing_on_invalid_record(tmp_path):
    gate = SchemaValidator()
    recs = _clean_records()
    # Strip source_ran_at from a federated claim — porth/offline both reject it.
    del recs.claims[0]["qualifiers"]["source_ran_at"]
    with pytest.raises(SnapshotError) as exc:
        SnapshotBuilder(gate).build(recs, tmp_path, built_utc=BUILT_UTC)
    assert exc.value.problems  # carries the per-record violations
    assert "source_ran_at" in " ".join(exc.value.problems)
    # No partial snapshot left behind.
    assert not any(tmp_path.iterdir())


def test_compact_snapshot_id():
    assert compact_snapshot_id("2026-07-11T04:30:00+00:00") == "snapshot-20260711T043000Z"


# --- Deliverable C: request queue -------------------------------------------

def test_queue_directory_contract(tmp_path):
    q = RequestQueue(tmp_path / "requests")
    q.ensure()
    for stage in ("inbox", "claimed", "done"):
        assert (tmp_path / "requests" / stage).is_dir()


def test_request_schema_validation():
    good = {
        "place": "Dolgellau", "nation": "wales",
        "wanted_layers": ["gazetteer"], "requested_by": "care-home-insight",
        "reason": "S2 pull_tref proof", "emitted_at": BUILT_UTC,
    }
    assert validate_request(good) == []
    bad = dict(good)
    del bad["wanted_layers"]
    assert any("wanted_layers" in p for p in validate_request(bad))


def test_queue_reader_stub_and_lifecycle(tmp_path):
    root = tmp_path / "requests"
    req = {
        "place": "Dolgellau", "nation": "wales",
        "wanted_layers": ["gazetteer"], "requested_by": "care-home-insight",
        "reason": "S2 pull_tref proof", "emitted_at": BUILT_UTC,
    }
    write_request(root, "req-0001", req)
    q = RequestQueue(root)
    parsed = q.read_inbox()
    assert len(parsed) == 1 and parsed[0].valid
    assert parsed[0].raw["place"] == "Dolgellau"
    # lifecycle wired for S6: inbox -> claimed -> done
    q.claim("req-0001")
    assert (root / "claimed" / "req-0001.json").is_file()
    q.mark_done("req-0001")
    assert (root / "done" / "req-0001.json").is_file()


def test_write_request_refuses_malformed(tmp_path):
    with pytest.raises(QueueError):
        write_request(tmp_path / "requests", "bad", {"place": "Dolgellau"})


# --- committed sample: diffable provenance backstop (exit #5) ----------------

def test_committed_sample_snapshot_still_validates():
    """The committed sample under samples/ must stay constitution-clean against
    the offline gate — a regression guard on the diffable backstop, and proof a
    consumer can re-verify a fetched snapshot record-by-record."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    snap = repo / "samples" / "dolgellau-gazetteer" / "snapshot-20260711T000000Z"
    if not snap.is_dir():
        pytest.skip("sample snapshot not present in this checkout")
    gate = SchemaValidator()
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    for fname, kind in (
        ("place-anchors.json", "place-anchor"),
        ("claims.json", "claim"),
        ("stamps.json", "federation-stamp"),
    ):
        records = json.loads((snap / fname).read_text(encoding="utf-8"))
        assert len(records) == manifest["counts"][
            {"place-anchor": "place_anchors", "claim": "claims",
             "federation-stamp": "stamps"}[kind]
        ]
        for i, rec in enumerate(records):
            result = gate.validate(kind, rec)
            assert result.valid, f"{fname}[{i}] drifted: {result.violations}"
