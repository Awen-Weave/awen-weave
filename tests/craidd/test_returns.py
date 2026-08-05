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


# --------------------------------------------------------------------------- #
# PR #13 ruling conditions (02/08) — the merge alone does not establish these
# --------------------------------------------------------------------------- #
from craidd.returns import (  # noqa: E402
    DEFERRED_PREDICATES,
    RETURN_SEMANTICS_CAVEAT,
    federated_return_claim,
)


def test_allowlist_fails_closed_on_an_unknown_predicate():
    """Condition 1. The slice is a positive allowlist — an identifier nobody has classified is
    EXCLUDED by default, not leaked. Red against a hypothetical default-return (a denylist)."""
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE current_claim ("
        " subject_id TEXT, predicate TEXT, value_text TEXT, value_int BIGINT,"
        " value_cy TEXT, value_en TEXT, source_id TEXT, confidence TEXT)"
    )
    con.executemany(
        "INSERT INTO current_claim VALUES (?,?,?,?,?,?,?,?)",
        [
            ("b1", "uprn", None, 100, None, None, "s1", "high"),          # in allowlist
            ("b1", "some_new_identifier", "X", None, None, None, "s1", "high"),  # unclassified
            ("b1", "resident_name", "Jane", None, None, "Jane", "s2", "high"),   # content
        ],
    )
    preds = {r["predicate"] for r in read_returnable_claims(con)}
    assert preds == {"uprn"}, "only the allowlisted predicate returns; the unknown one is excluded"
    assert "some_new_identifier" not in preds, "an unclassified identifier must fail CLOSED"


def test_geometry_is_owed_and_deferred_not_silently_excluded():
    """Condition 2. Geometry is recorded as a deferral WITH its condition, as data — so it
    cannot decay into a silent exclusion. It must not be returnable yet, and it must be
    named as owed with the WKT/CRS condition."""
    assert "geometry" not in RETURNABLE_PREDICATES          # not returned yet
    assert "geometry" in DEFERRED_PREDICATES                 # but explicitly owed, not dropped
    condition = DEFERRED_PREDICATES["geometry"].lower()
    assert "wkt" in condition and "crs" in condition, "the deferral must name its WKT/CRS condition"


def test_every_federated_return_claim_carries_binding_and_a_semantics_caveat():
    """Condition 3. A returned claim shows its binding visibly, and a federated one carries a
    semantics_caveat so the consumer sees it is reading an unverified federated linkage."""
    c = federated_return_claim(
        subject_id="b1", predicate="uprn", value="100100123",
        source_id="s1", recorded_by="huw@arloesidolgellau.cymru", source=_source(),
    )
    q = c["qualifiers"]
    assert q["binding"] == "federated"                       # binding visible
    assert q["federated_from"] == "dolgellau-town-dataset"
    assert q["semantics_caveat"] == RETURN_SEMANTICS_CAVEAT   # caveat present
    # and it still validates against the live grammar
    gate = SchemaValidator()
    assert gate.validate("claim", c).valid


def test_the_caveat_survives_the_full_build_and_validates(tmp_path):
    con = _con_with_claims()
    src = _source()
    rows = read_returnable_claims(con)
    stamp = gazetteer_stamp(source=src, consumer_instance="craidd:core",
                            counts={"claims": len(rows)}, federated_utc=BUILT_UTC)
    recs = build_returns(rows, source=src, consumer_instance="craidd:core",
                         recorded_by="huw@arloesidolgellau.cymru", stamp=stamp)
    gate = SchemaValidator()
    for c in recs.claims:
        assert c["qualifiers"]["semantics_caveat"] == RETURN_SEMANTICS_CAVEAT
        assert gate.validate("claim", c).valid
