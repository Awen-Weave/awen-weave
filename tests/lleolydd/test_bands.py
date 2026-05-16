"""
Tests for src/lleolydd/cache/bands.py — the UPRN status-band classifier.

These are the load-bearing Lleolydd tests. Use small synthetic polygons
+ points (no real OS data); each test sets up an in-memory DuckDB with
the cache schema, populates it with a handful of UPRNs / TOIDs /
linked_id rows, calls classify_bands, and asserts the band assignment
matches the rule from design/lleolydd.md §4.

The fixtures use OSGB BNG coordinates near Dolgellau (E~272000, N~317000)
so anyone reading a failure can intuit "yes that's a Dolgellau-shaped
test" rather than abstract numbers.
"""
from __future__ import annotations

import duckdb
import pytest

# The cache schema. Re-defined here rather than imported from build.py
# so tests don't depend on build.py's full surface — keeps the schema
# unit testable in isolation.
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


def _insert_building_toid(
    conn,
    toid: str,
    cx: float,
    cy: float,
    half_side: float = 5.0,
) -> None:
    """Insert a building TOID as a square polygon centred at (cx, cy)
    in BNG, with half-side `half_side` metres. ~10m square by default
    — small Welsh terraced house scale."""
    minx, miny = cx - half_side, cy - half_side
    maxx, maxy = cx + half_side, cy + half_side
    wkt = (
        f"POLYGON(({minx} {miny}, {maxx} {miny}, "
        f"{maxx} {maxy}, {minx} {maxy}, {minx} {miny}))"
    )
    conn.execute(
        """
        INSERT INTO toid (toid, polygon_geom, feature_type,
                          description_group, description_term,
                          centroid_geom)
        VALUES (?, ST_GeomFromText(?), 'TopographicArea',
                'Building', 'Building',
                ST_Point(?, ?))
        """,
        [toid, wkt, cx, cy],
    )


def _link(conn, uprn: int, toid: str) -> None:
    conn.execute(
        "INSERT INTO linked_id (uprn, toid) VALUES (?, ?)",
        [uprn, toid],
    )


# --- happy paths ------------------------------------------------------------


def test_auto_snapped_single_toid_lids_agrees(conn):
    """UPRN inside exactly one building TOID; LIDS confirms the link.
    The canonical 'good' case."""
    from lleolydd.cache.bands import classify_bands

    # Building roughly at Tŷ Newyddion, Bridge Street.
    _insert_building_toid(conn, "osgb-001", cx=272030, cy=317900)
    _insert_uprn(conn, 100, x=272030, y=317900)
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
    assert stats.contested == 0
    assert stats.non_postal == 0


def test_unsnapped_uprn_outside_any_toid(conn):
    """UPRN point sits well outside any TOID polygon — classic rural
    farmstead case where the UPRN coordinate is on the road junction
    and the building is 200m down the driveway."""
    from lleolydd.cache.bands import classify_bands

    # TOID at one location, UPRN 200m away.
    _insert_building_toid(conn, "osgb-002", cx=272030, cy=317900)
    _insert_uprn(conn, 200, x=272230, y=317900)
    # LIDS records that the UPRN belongs to the TOID (so it ISN'T
    # non-postal — LIDS has a row). The UPRN just doesn't sit in the
    # polygon spatially. This is exactly the rural-driveway shape
    # Lleolydd is for.
    _link(conn, 200, "osgb-002")

    classify_bands(conn, "test-unsnapped")

    row = conn.execute(
        "SELECT snap_band, snapped_toid, snap_confidence FROM uprn"
    ).fetchone()
    assert row[0] == "unsnapped"
    assert row[1] is None
    assert row[2] == 0.0


def test_contested_uprn_inside_two_overlapping_toids(conn):
    """UPRN point sits inside two TOIDs. Happens with party-wall
    geometries where OS records two adjacent building polygons that
    abut — the UPRN can fall on the boundary and ST_Within picks both.
    """
    from lleolydd.cache.bands import classify_bands

    # Two slightly-overlapping building TOIDs.
    _insert_building_toid(conn, "osgb-003", cx=272030, cy=317900, half_side=5)
    _insert_building_toid(conn, "osgb-004", cx=272036, cy=317900, half_side=5)
    # UPRN sits exactly on their overlap.
    _insert_uprn(conn, 300, x=272032, y=317900)
    _link(conn, 300, "osgb-003")

    classify_bands(conn, "test-contested-spatial")

    row = conn.execute(
        "SELECT snap_band, snap_confidence FROM uprn WHERE uprn=300"
    ).fetchone()
    assert row[0] == "contested"
    assert row[1] == 0.5


def test_contested_lids_disagrees_with_spatial(conn):
    """UPRN spatially in TOID A, but LIDS says it belongs to TOID B.
    Genuine conflict between the two authority signals — curator
    judgement needed."""
    from lleolydd.cache.bands import classify_bands

    _insert_building_toid(conn, "toid-A", cx=272030, cy=317900)
    _insert_building_toid(conn, "toid-B", cx=272500, cy=317900)
    _insert_uprn(conn, 400, x=272030, y=317900)
    _link(conn, 400, "toid-B")  # LIDS says B, spatial says A

    classify_bands(conn, "test-contested-disagree")

    row = conn.execute(
        "SELECT snap_band, snap_confidence FROM uprn WHERE uprn=400"
    ).fetchone()
    assert row[0] == "contested"
    assert row[1] == 0.5


def test_non_postal_no_lids_row(conn):
    """OS-allocated UPRN for a non-postal feature (substation, post
    box, defibrillator). LIDS BLPU-UPRN-TopographicArea-TOID file
    only carries UPRNs that ARE linked to a building TOID; non-postal
    UPRNs are absent. Classify by absence."""
    from lleolydd.cache.bands import classify_bands

    # Building exists, UPRN sits in it, but LIDS has no row → the
    # UPRN is non-postal (e.g. a defibrillator UPRN that happens to
    # be physically inside the village hall TOID).
    _insert_building_toid(conn, "osgb-005", cx=272030, cy=317900)
    _insert_uprn(conn, 500, x=272030, y=317900)
    # No _link call.

    classify_bands(conn, "test-non-postal")

    row = conn.execute(
        "SELECT snap_band, snapped_toid, snap_confidence FROM uprn"
    ).fetchone()
    assert row[0] == "non-postal"
    assert row[1] is None
    assert row[2] == 1.0  # confident classification (LIDS authority)


def test_non_postal_outside_any_toid(conn):
    """Edge case — non-postal UPRN (no LIDS row) that ALSO doesn't sit
    in any TOID polygon. Still classifies as non-postal: LIDS absence
    is the authority signal."""
    from lleolydd.cache.bands import classify_bands

    _insert_uprn(conn, 600, x=200000, y=200000)
    # No TOID near it; no LIDS row.

    classify_bands(conn, "test-non-postal-isolated")

    row = conn.execute(
        "SELECT snap_band FROM uprn WHERE uprn=600"
    ).fetchone()
    assert row[0] == "non-postal"


# --- mixed populations ------------------------------------------------------


def test_mixed_population_classified_correctly(conn):
    """A handful of UPRNs covering all four bands — verifies the band
    stats counts."""
    from lleolydd.cache.bands import classify_bands

    # auto-snapped UPRN
    _insert_building_toid(conn, "tA", cx=272000, cy=317000)
    _insert_uprn(conn, 1, x=272000, y=317000)
    _link(conn, 1, "tA")

    # unsnapped UPRN
    _insert_building_toid(conn, "tB", cx=272500, cy=317000)
    _insert_uprn(conn, 2, x=272700, y=317000)
    _link(conn, 2, "tB")

    # contested (spatial overlap)
    _insert_building_toid(conn, "tC1", cx=273000, cy=317000, half_side=5)
    _insert_building_toid(conn, "tC2", cx=273006, cy=317000, half_side=5)
    _insert_uprn(conn, 3, x=273003, y=317000)
    _link(conn, 3, "tC1")

    # non-postal (no LIDS)
    _insert_building_toid(conn, "tD", cx=273500, cy=317000)
    _insert_uprn(conn, 4, x=273500, y=317000)

    stats = classify_bands(conn, "test-mixed")

    assert stats.auto_snapped == 1
    assert stats.unsnapped == 1
    assert stats.contested == 1
    assert stats.non_postal == 1
    assert stats.total == 4

    bands_by_uprn = dict(conn.execute(
        "SELECT uprn, snap_band FROM uprn ORDER BY uprn"
    ).fetchall())
    assert bands_by_uprn == {
        1: "auto-snapped",
        2: "unsnapped",
        3: "contested",
        4: "non-postal",
    }


def test_band_stats_as_dict_shape():
    """The BandStats.as_dict serialisation pins the keys craidd-status
    and the CLI rely on."""
    from lleolydd.cache.bands import BandStats

    stats = BandStats(
        auto_snapped=10,
        unsnapped=20,
        contested=3,
        non_postal=2,
    )
    d = stats.as_dict()
    assert d == {
        "auto-snapped": 10,
        "unsnapped": 20,
        "contested": 3,
        "non-postal": 2,
        "total": 35,
    }


def test_classify_bands_is_idempotent(conn):
    """Running classify_bands twice on the same data produces the same
    result. Important because a routine cache refresh re-runs band
    classification against a possibly-changed downstream snapshot."""
    from lleolydd.cache.bands import classify_bands

    _insert_building_toid(conn, "tX", cx=272030, cy=317900)
    _insert_uprn(conn, 700, x=272030, y=317900)
    _link(conn, 700, "tX")

    s1 = classify_bands(conn, "snap-1")
    s2 = classify_bands(conn, "snap-2")
    assert s1.as_dict() == s2.as_dict()

    snapshot_id = conn.execute(
        "SELECT snapshot_id FROM uprn WHERE uprn=700"
    ).fetchone()[0]
    assert snapshot_id == "snap-2"  # latest run wins, as expected
