"""
Tests for src/lleolydd/cache/bands.py — the UPRN status-band classifier
(v1 point-proximity semantics).

These are the load-bearing Lleolydd tests. Use small synthetic TOID
points + UPRN points (no real OS data); each test sets up an in-memory
DuckDB with the cache schema, populates it with a handful of UPRNs /
TOIDs / linked_id rows, calls classify_bands, and asserts the band
assignment matches the v1 (point-proximity) decision matrix.

Fixtures use OSGB BNG coordinates near Dolgellau (E~272000, N~317000)
so anyone reading a failure can intuit "yes that's a Dolgellau-shaped
test" rather than abstract numbers.

v1 semantics — see src/lleolydd/cache/bands.py module docstring:
  auto-snapped     UPRN within SNAP_THRESHOLD_M of exactly one TOID
                   point AND LIDS agrees with that TOID.
  unsnapped        no TOID point within SNAP_THRESHOLD_M.
  contested-prox   multiple TOID points within SNAP_THRESHOLD_M.
  contested-lids   exactly one within, LIDS disagrees.
  non-postal       no LIDS row (overrides spatial state).

When OS NGD restores polygons in Phase 1.x the polygon-based
classifier returns and contested-prox/contested-lids collapse back
into a single `contested` band — these tests will need to be
re-shaped at that point.
"""
from __future__ import annotations

import duckdb
import pytest

# The cache schema (subset relevant to bands). Re-defined here rather
# than imported from build.py so tests don't depend on build.py's full
# surface — keeps the schema unit-testable in isolation.
#
# Schema matches build.py's CACHE_DDL for the v1 (point-proximity)
# shape: toid carries point_geom + nullable polygon_geom / feature_type
# / description_group / description_term / centroid_geom (the columns
# Phase 1.x will populate via OS NGD).
TEST_DDL = """
INSTALL spatial; LOAD spatial;

CREATE TABLE uprn (
    uprn BIGINT PRIMARY KEY,
    point_geom GEOMETRY,
    snapped_toid VARCHAR,
    snap_band VARCHAR,
    snap_confidence DOUBLE,
    latitude DOUBLE,
    longitude DOUBLE,
    snapshot_id VARCHAR
);

CREATE TABLE toid (
    toid VARCHAR PRIMARY KEY,
    point_geom GEOMETRY,
    polygon_geom GEOMETRY,
    feature_type VARCHAR,
    description_group VARCHAR,
    description_term VARCHAR,
    centroid_geom GEOMETRY,
    snapshot_id VARCHAR
);

CREATE TABLE linked_id (
    uprn BIGINT,
    toid VARCHAR,
    correlation_method VARCHAR,
    snapshot_id VARCHAR,
    PRIMARY KEY (uprn, toid)
);
"""


@pytest.fixture
def conn():
    """In-memory DuckDB with cache schema + spatial extension loaded."""
    c = duckdb.connect(":memory:")
    c.execute(TEST_DDL)
    yield c
    c.close()


def _insert_uprn(conn, uprn: int, x: float, y: float) -> None:
    """Insert a UPRN at OSGB (x, y) BNG coordinates."""
    conn.execute(
        """
        INSERT INTO uprn (uprn, point_geom)
        VALUES (?, ST_Point(?, ?))
        """,
        [uprn, x, y],
    )


def _insert_toid_point(
    conn,
    toid: str,
    x: float,
    y: float,
) -> None:
    """Insert a TOID at its representative point (BNG). v1 shape:
    point_geom populated, polygon_geom + feature_type / description
    columns NULL (Phase 1.x NGD will fill them)."""
    conn.execute(
        """
        INSERT INTO toid (toid, point_geom)
        VALUES (?, ST_Point(?, ?))
        """,
        [toid, x, y],
    )


def _link(conn, uprn: int, toid: str) -> None:
    conn.execute(
        "INSERT INTO linked_id (uprn, toid) VALUES (?, ?)",
        [uprn, toid],
    )


# --- happy paths ------------------------------------------------------------


def test_auto_snapped_single_toid_lids_agrees(conn):
    """UPRN within 15m of exactly one TOID point; LIDS confirms.
    The canonical 'good' case."""
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "osgb-001", x=272030, y=317900)
    _insert_uprn(conn, 100, x=272035, y=317905)  # 7.07m away
    _link(conn, 100, "osgb-001")

    stats = classify_bands(conn, "test-snap")

    row = conn.execute(
        "SELECT snap_band, snapped_toid, snap_confidence FROM uprn"
    ).fetchone()
    assert row[0] == "auto-snapped"
    assert row[1] == "osgb-001"
    assert row[2] == 1.0
    assert stats.auto_snapped == 1
    assert stats.unsnapped == 0
    assert stats.contested_prox == 0
    assert stats.contested_lids == 0
    assert stats.non_postal == 0


def test_unsnapped_uprn_far_from_any_toid(conn):
    """UPRN sits >>15m from any TOID point — the rural-driveway case.
    LIDS still has a row (so it isn't non-postal) but the spatial
    proximity test fails."""
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "osgb-002", x=272030, y=317900)
    _insert_uprn(conn, 200, x=272230, y=317900)   # 200m away
    _link(conn, 200, "osgb-002")

    classify_bands(conn, "test-unsnapped")

    row = conn.execute(
        "SELECT snap_band, snapped_toid, snap_confidence FROM uprn"
    ).fetchone()
    assert row[0] == "unsnapped"
    assert row[1] is None
    assert row[2] == 0.0


def test_unsnapped_just_outside_threshold(conn):
    """Boundary test: UPRN at 16m from the nearest TOID — outside the
    15m default threshold, so unsnapped."""
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "osgb-edge", x=272030, y=317900)
    _insert_uprn(conn, 201, x=272046, y=317900)   # 16m east
    _link(conn, 201, "osgb-edge")

    classify_bands(conn, "test-just-outside")

    row = conn.execute(
        "SELECT snap_band FROM uprn WHERE uprn=201"
    ).fetchone()
    assert row[0] == "unsnapped"


def test_contested_prox_two_toids_within_threshold(conn):
    """UPRN is within 15m of two distinct TOID points — terrace /
    multi-building UPRN case. Classified contested-prox regardless of
    what LIDS says."""
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "osgb-003a", x=272030, y=317900)
    _insert_toid_point(conn, "osgb-003b", x=272040, y=317900)  # 10m east
    _insert_uprn(conn, 300, x=272035, y=317900)                # 5m from each
    _link(conn, 300, "osgb-003a")

    classify_bands(conn, "test-contested-prox")

    row = conn.execute(
        "SELECT snap_band, snap_confidence FROM uprn WHERE uprn=300"
    ).fetchone()
    assert row[0] == "contested-prox"
    assert row[1] == 0.5


def test_contested_lids_one_within_but_disagrees(conn):
    """UPRN has exactly one TOID within 15m, but LIDS says a different
    TOID — genuine conflict between spatial and authority signals."""
    from lleolydd.cache.bands import classify_bands

    # Spatially close TOID A; LIDS says B (which is 500m away — outside
    # threshold so it doesn't count as a second proximity hit).
    _insert_toid_point(conn, "toid-A", x=272030, y=317900)
    _insert_toid_point(conn, "toid-B", x=272530, y=317900)
    _insert_uprn(conn, 400, x=272030, y=317900)
    _link(conn, 400, "toid-B")  # LIDS says B, spatial closest is A

    classify_bands(conn, "test-contested-lids")

    row = conn.execute(
        "SELECT snap_band, snap_confidence FROM uprn WHERE uprn=400"
    ).fetchone()
    assert row[0] == "contested-lids"
    assert row[1] == 0.5


def test_non_postal_no_lids_row(conn):
    """OS-allocated UPRN with no LIDS row — non-postal feature
    (substation, defibrillator). LIDS absence is the authority
    signal; overrides any spatial proximity."""
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "osgb-005", x=272030, y=317900)
    _insert_uprn(conn, 500, x=272030, y=317900)   # coincident
    # No _link call — UPRN has no LIDS row.

    classify_bands(conn, "test-non-postal")

    row = conn.execute(
        "SELECT snap_band, snapped_toid, snap_confidence FROM uprn"
    ).fetchone()
    assert row[0] == "non-postal"
    assert row[1] is None
    assert row[2] == 1.0  # LIDS authority is a confident signal


def test_non_postal_isolated(conn):
    """Edge case — non-postal UPRN (no LIDS) that also has no nearby
    TOID. Still classifies as non-postal: LIDS absence dominates."""
    from lleolydd.cache.bands import classify_bands

    _insert_uprn(conn, 600, x=200000, y=200000)
    # No TOID, no LIDS.

    classify_bands(conn, "test-non-postal-isolated")

    row = conn.execute(
        "SELECT snap_band FROM uprn WHERE uprn=600"
    ).fetchone()
    assert row[0] == "non-postal"


# --- threshold parameterisation --------------------------------------------


def test_threshold_respected_classification_changes(conn):
    """Changing snap_threshold_m must move the boundary. Single
    UPRN-TOID pair at 12m apart:
      - threshold 15m → auto-snapped (within)
      - threshold 5m  → unsnapped (outside)
    This pins the contract that the threshold isn't ignored or
    hard-coded inside the SQL.
    """
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "osgb-thr", x=272000, y=317000)
    _insert_uprn(conn, 700, x=272012, y=317000)   # 12m away
    _link(conn, 700, "osgb-thr")

    # First pass — default 15m, should auto-snap.
    classify_bands(conn, "test-thr-15")
    assert conn.execute(
        "SELECT snap_band FROM uprn WHERE uprn=700"
    ).fetchone()[0] == "auto-snapped"

    # Second pass — tighter 5m threshold; should fall back to unsnapped.
    classify_bands(conn, "test-thr-5", snap_threshold_m=5.0)
    assert conn.execute(
        "SELECT snap_band FROM uprn WHERE uprn=700"
    ).fetchone()[0] == "unsnapped"


# --- mixed populations -----------------------------------------------------


def test_mixed_population_classified_correctly(conn):
    """A handful of UPRNs across all five bands — verifies the band
    stats counts."""
    from lleolydd.cache.bands import classify_bands

    # auto-snapped UPRN — single TOID within 15m, LIDS agrees.
    _insert_toid_point(conn, "tA", x=272000, y=317000)
    _insert_uprn(conn, 1, x=272001, y=317000)
    _link(conn, 1, "tA")

    # unsnapped UPRN — TOID 200m away.
    _insert_toid_point(conn, "tB", x=272500, y=317000)
    _insert_uprn(conn, 2, x=272700, y=317000)
    _link(conn, 2, "tB")

    # contested-prox — UPRN equidistant between two TOIDs within 15m.
    _insert_toid_point(conn, "tC1", x=273000, y=317000)
    _insert_toid_point(conn, "tC2", x=273010, y=317000)
    _insert_uprn(conn, 3, x=273005, y=317000)
    _link(conn, 3, "tC1")

    # contested-lids — one TOID within 15m, LIDS points elsewhere.
    _insert_toid_point(conn, "tDa", x=274000, y=317000)
    _insert_toid_point(conn, "tDb", x=275000, y=317000)
    _insert_uprn(conn, 4, x=274000, y=317000)
    _link(conn, 4, "tDb")

    # non-postal — no LIDS row.
    _insert_toid_point(conn, "tE", x=276000, y=317000)
    _insert_uprn(conn, 5, x=276000, y=317000)

    stats = classify_bands(conn, "test-mixed")

    assert stats.auto_snapped == 1
    assert stats.unsnapped == 1
    assert stats.contested_prox == 1
    assert stats.contested_lids == 1
    assert stats.non_postal == 1
    assert stats.total == 5

    bands_by_uprn = dict(conn.execute(
        "SELECT uprn, snap_band FROM uprn ORDER BY uprn"
    ).fetchall())
    assert bands_by_uprn == {
        1: "auto-snapped",
        2: "unsnapped",
        3: "contested-prox",
        4: "contested-lids",
        5: "non-postal",
    }


def test_band_stats_as_dict_shape():
    """The BandStats.as_dict serialisation pins the manifest keys
    the CLI's `snapshot show` and downstream consumers rely on."""
    from lleolydd.cache.bands import BandStats

    stats = BandStats(
        auto_snapped=10,
        unsnapped=20,
        contested_prox=2,
        contested_lids=1,
        non_postal=2,
    )
    d = stats.as_dict()
    assert d == {
        "auto-snapped": 10,
        "unsnapped": 20,
        "contested-prox": 2,
        "contested-lids": 1,
        "non-postal": 2,
        "total": 35,
    }


def test_classify_bands_is_idempotent(conn):
    """Running classify_bands twice on the same data produces the
    same result. Important because a routine cache refresh re-runs
    classification against a possibly-changed downstream snapshot."""
    from lleolydd.cache.bands import classify_bands

    _insert_toid_point(conn, "tX", x=272030, y=317900)
    _insert_uprn(conn, 700, x=272030, y=317900)
    _link(conn, 700, "tX")

    s1 = classify_bands(conn, "snap-1")
    s2 = classify_bands(conn, "snap-2")
    assert s1.as_dict() == s2.as_dict()

    snapshot_id = conn.execute(
        "SELECT snapshot_id FROM uprn WHERE uprn=700"
    ).fetchone()[0]
    assert snapshot_id == "snap-2"   # latest run wins
