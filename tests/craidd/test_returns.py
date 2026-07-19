"""Returns channel (Doctrine §8) — slice selection + snapshot validity.

Proves, with an in-memory DuckDB standing in for /srv/town-dataset/craidd.duckdb:
  - the ADJ-RETURN-001 predicate allowlist selects open-identifier identity/linkage
    claims and EXCLUDES descriptive content (names) — the slice discipline;
  - the built claims + stamp are constitution.validate-clean against the vendored
    gate (so SnapshotBuilder writes a real, valid returns snapshot);
  - every exported claim carries source_of_record = the Town Dataset instance.
"""
from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb")

from craidd.federation import SourceOfRecord
from craidd.gazetteer import gazetteer_stamp
from craidd.returns import (
    RETURNABLE_PREDICATES,
    build_returns,
    read_returnable_claims,
)
from craidd.snapshot import SnapshotBuilder
from craidd.validation_gate import SchemaValidator

BUILT_UTC = "2026-07-18T20:00:00+00:00"
SOURCE_RAN_AT = "2026-05-26T16:04:43+00:00"


def _source() -> SourceOfRecord:
    return SourceOfRecord(
        instance="dolgellau-town-dataset",
        repo="arloesidolgellau/town-dataset",
        framework="tref",
        root="/srv/town-dataset",
        paths={"craidd": "/srv/town-dataset/craidd.duckdb"},
        ran_at_utc=SOURCE_RAN_AT,
        release="returns",
    )


def _con_with_claims():
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE current_claim ("
        " subject_id TEXT, predicate TEXT, value_text TEXT, value_int BIGINT,"
        " value_cy TEXT, value_en TEXT, source_id TEXT, confidence TEXT)"
    )
    rows = [
        # returnable: linkage (Cadw↔building) + identity (uprn)
        ("TDS-DOL-B-00001", "listed_id", "Cadw 4938", None, None, None, "TDS-DOL-SRC-CADW-4938", "high"),
        ("TDS-DOL-B-00001", "uprn", None, 100100123, None, None, "TDS-DOL-SRC-OSOPEN", "high"),
        # NOT returnable: descriptive content — must be excluded by the allowlist
        ("TDS-DOL-B-00001", "name_en", "Glyndwr Buildings", None, None, "Glyndwr Buildings", "TDS-DOL-SRC-INTERNAL", "high"),
        ("TDS-DOL-B-00001", "address", "High St", None, None, "High St", "TDS-DOL-SRC-INTERNAL", "medium"),
    ]
    con.executemany(
        "INSERT INTO current_claim VALUES (?,?,?,?,?,?,?,?)", rows
    )
    return con


def test_allowlist_selects_identity_linkage_excludes_content():
    con = _con_with_claims()
    got = read_returnable_claims(con)
    preds = sorted(r["predicate"] for r in got)
    assert preds == ["listed_id", "uprn"]          # names/address excluded
    assert all(p in RETURNABLE_PREDICATES for p in preds)


def test_uprn_int_value_carried_as_text():
    con = _con_with_claims()
    got = {r["predicate"]: r for r in read_returnable_claims(con)}
    # value comes from value_int for uprn; downstream claim carries it as value_text
    src = _source()
    recs = build_returns(
        list(got.values()), source=src,
        consumer_instance="craidd:core", recorded_by="huw@arloesidolgellau.cymru",
        stamp=gazetteer_stamp(source=src, consumer_instance="craidd:core"),
    )
    uprn_claim = next(c for c in recs.claims if c["predicate"] == "uprn")
    assert uprn_claim["value_text"] == "100100123"


def test_returns_snapshot_is_validate_clean(tmp_path):
    con = _con_with_claims()
    src = _source()
    claim_rows = read_returnable_claims(con)
    stamp = gazetteer_stamp(
        source=src, consumer_instance="craidd:core",
        craidd_node="place:dolgellau", craidd_source="dolgellau-town-dataset",
        grade="A", counts={"claims": len(claim_rows)}, federated_utc=BUILT_UTC,
    )
    recs = build_returns(
        claim_rows, source=src, consumer_instance="craidd:core",
        recorded_by="huw@arloesidolgellau.cymru", stamp=stamp,
    )
    gate = SchemaValidator()
    for c in recs.claims:
        res = gate.validate("claim", c)
        assert res.valid, res.violations
    assert gate.validate("federation-stamp", recs.stamps[0]).valid

    snap_dir = SnapshotBuilder(gate).build(recs, tmp_path, built_utc=BUILT_UTC)
    assert snap_dir.exists()
    # every exported claim points source_of_record back to the Pi instance
    assert stamp["source_of_record"]["instance"] == "dolgellau-town-dataset"
    for c in recs.claims:
        assert c["qualifiers"]["federated_from"] == "dolgellau-town-dataset"
        assert c["qualifiers"]["binding"] == "federated"


def test_empty_when_no_returnable_predicates():
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE current_claim ("
        " subject_id TEXT, predicate TEXT, value_text TEXT, value_int BIGINT,"
        " value_cy TEXT, value_en TEXT, source_id TEXT, confidence TEXT)"
    )
    con.execute(
        "INSERT INTO current_claim VALUES "
        "('X','name_en','n',NULL,NULL,'n','S','high')"
    )
    assert read_returnable_claims(con) == []
