"""
Tests for the cache build orchestrator + snapshot manifest.

These tests exercise the schema, the snapshot manifest writer, the
build orchestrator's dry-run path, and end-to-end band classification
against synthetic CSV / GeoJSON fixtures that we generate at test
time. No live OS Data Hub downloads happen in this suite.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import duckdb
import pytest

# Put src/ on the path so `from lleolydd...` resolves.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))


# --- schema test -----------------------------------------------------------

def test_cache_ddl_applies_cleanly(tmp_path: Path):
    """The full schema in build.CACHE_DDL applies to a fresh DuckDB
    without error. Catches typos / missing-extension issues early."""
    from lleolydd.cache.build import CACHE_DDL
    db = tmp_path / "cache.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute(CACHE_DDL)
    # Confirm the five expected tables exist.
    tables = {
        row[0] for row in conn.execute(
            "SELECT table_name FROM duckdb_tables() "
            "WHERE database_name='cache'"
        ).fetchall()
    }
    expected = {"uprn", "toid", "linked_id", "inspire_parcel",
                "zoomstack_manifest", "snapshot"}
    assert expected.issubset(tables), f"missing tables: {expected - tables}"
    conn.close()


# --- snapshot manifest tests -----------------------------------------------

def test_snapshot_manifest_writes_and_reloads(tmp_path: Path):
    """Round-trip: open_manifest → add_source → write → load_manifest
    produces the same payload."""
    from lleolydd.cache.snapshot import (
        load_manifest,
        open_manifest,
    )

    bounds = tmp_path / "area-bounds.geojson"
    bounds.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    m = open_manifest("lleolydd-cache-2026-05", "2026-05", bounds)
    m.add_source(
        name="os-open-uprn",
        product_id="OpenUPRN",
        files=[tmp_path / "fake.csv"],
        load_stats={"rows_in": 100, "rows_in_area": 5},
    )
    m.band_stats = {"auto-snapped": 4, "unsnapped": 1, "contested": 0,
                    "non-postal": 0, "total": 5}
    snap_dir = tmp_path / "snapshots" / "lleolydd-cache-2026-05"
    written = m.write(snap_dir)

    assert written.is_file()
    loaded = load_manifest(snap_dir)
    assert loaded["snapshot_id"] == "lleolydd-cache-2026-05"
    assert loaded["release"] == "2026-05"
    assert len(loaded["sources"]) == 1
    assert loaded["sources"][0]["name"] == "os-open-uprn"
    assert loaded["band_stats"]["auto-snapped"] == 4


def test_snapshot_manifest_records_area_bounds_hash(tmp_path: Path):
    """The area-bounds file's sha256 lands in the manifest, so future
    builds against a different boundary surface a hash diff."""
    from lleolydd.cache.snapshot import open_manifest

    bounds = tmp_path / "bounds.geojson"
    payload = '{"type":"FeatureCollection","features":[]}'
    bounds.write_text(payload)
    expected = hashlib.sha256(payload.encode()).hexdigest()

    m = open_manifest("snap-x", "2026-05", bounds)
    assert m.area_bounds_sha256 == expected


def test_list_snapshots_returns_sorted_release_names(tmp_path: Path):
    """list_snapshots only counts directories with a manifest.json."""
    from lleolydd.cache.snapshot import list_snapshots

    root = tmp_path / "snapshots"
    (root / "lleolydd-cache-2026-05").mkdir(parents=True)
    (root / "lleolydd-cache-2026-05" / "manifest.json").write_text("{}")
    (root / "lleolydd-cache-2026-04").mkdir()
    (root / "lleolydd-cache-2026-04" / "manifest.json").write_text("{}")
    (root / "junk-no-manifest").mkdir()  # should be ignored

    items = list_snapshots(root)
    assert items == ["lleolydd-cache-2026-04", "lleolydd-cache-2026-05"]


# --- build dry-run --------------------------------------------------------

def _make_gwynedd_bounds_fixture(path: Path) -> None:
    """Write a small synthetic boundary GeoJSON in BNG. Roughly a 10km
    square centred on Dolgellau — enough to contain test UPRNs / TOIDs
    in the synthetic ranges used by test_bands."""
    feature = {
        "type": "Feature",
        "properties": {"name": "Gwynedd-synthetic"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [265000, 310000],
                [285000, 310000],
                [285000, 325000],
                [265000, 325000],
                [265000, 310000],
            ]],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [feature],
    }))


def test_build_dry_run_validates_paths(tmp_path: Path):
    """--dry-run mode produces a summary without writing the cache db."""
    from lleolydd.cache.build import build

    bounds = tmp_path / "area-bounds.geojson"
    _make_gwynedd_bounds_fixture(bounds)
    data_dir = tmp_path / "data"

    summary = build(
        data_dir=data_dir,
        area_bounds=bounds,
        release="2026-05",
        dry_run=True,
    )

    assert summary["dry_run"] is True
    assert "area_bounds_wkt_length" in summary
    # bbox derived from the synthetic Gwynedd polygon (a 20x15 km
    # square in EPSG:27700 centred on Dolgellau). Used by the spatial
    # loaders as a cheap prefilter before ST_Within / ST_Intersects.
    assert summary["area_bounds_bbox"] == [265000.0, 310000.0, 285000.0, 325000.0]
    # cache.duckdb should NOT exist after dry-run
    assert not (data_dir / "seed" / "lleolydd" / "cache.duckdb").exists()


def test_build_dry_run_rejects_missing_bounds(tmp_path: Path):
    """A missing area-bounds file fails at dry-run time, before any
    download attempt."""
    from lleolydd.cache.build import build

    with pytest.raises(FileNotFoundError):
        build(
            data_dir=tmp_path,
            area_bounds=tmp_path / "no-such.geojson",
            release="2026-05",
            dry_run=True,
        )


def test_build_rejects_unknown_source(tmp_path: Path):
    from lleolydd.cache.build import build

    bounds = tmp_path / "area-bounds.geojson"
    _make_gwynedd_bounds_fixture(bounds)
    with pytest.raises(RuntimeError, match="unknown source"):
        build(
            data_dir=tmp_path,
            area_bounds=bounds,
            release="2026-05",
            sources=["not-a-real-source"],
            dry_run=True,
        )


# --- end-to-end via synthetic fixtures + --skip-download ------------------

def _write_synthetic_uprn_csv(path: Path) -> None:
    """Write a small OS-Open-UPRN-shaped CSV with handful of rows in
    and out of the Gwynedd-synthetic bounds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["UPRN", "X_COORDINATE", "Y_COORDINATE",
                    "LATITUDE", "LONGITUDE"])
        # Inside Gwynedd-synthetic bounds
        w.writerow([1001, 272030, 317900, 52.7415, -3.8870])
        w.writerow([1002, 272200, 317000, 52.7332, -3.8842])
        w.writerow([1003, 272500, 317800, 52.7406, -3.8800])
        # Outside the synthetic bounds (filtered out)
        w.writerow([2001, 600000, 200000, 51.0, -1.0])


def _write_synthetic_toid_csv(path: Path) -> None:
    """OS Open TOID has no header row. Columns:
    TOID, ALT, GEOMETRY, FEATURE_TYPE, VERSION, VERSION_DATE,
    DESCRIPTION_GROUP, DESCRIPTION_TERM, MAKE, PHYSICAL_LEVEL,
    PHYSICAL_PRESENCE."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        # toid, alt, wkt, feature_type, version, version_date,
        #   description_group, description_term, make,
        #   physical_level, physical_presence
        ["osgb-bldg-1001", "1",
         "POLYGON((272020 317890, 272040 317890, 272040 317910, "
         "272020 317910, 272020 317890))",
         "TopographicArea", "1", "2024-01-01",
         "Building", "Building", "Manmade", "Surface Level", "Obstructing"],
        ["osgb-bldg-1003", "1",
         "POLYGON((272490 317790, 272510 317790, 272510 317810, "
         "272490 317810, 272490 317790))",
         "TopographicArea", "1", "2024-01-01",
         "Building", "Building", "Manmade", "Surface Level", "Obstructing"],
        # Non-building feature — should be filtered out at load time
        ["osgb-road-9999", "1",
         "POLYGON((265000 310000, 270000 310000, 270000 311000, "
         "265000 311000, 265000 310000))",
         "TopographicArea", "1", "2024-01-01",
         "Road Or Track", "Road Or Track", "Manmade",
         "Surface Level", "Obstructing"],
    ]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)


def _write_synthetic_lids_csv(path: Path) -> None:
    """LIDS BLPU-UPRN-TopographicArea-TOID file. Header present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["IDENTIFIER_1", "IDENTIFIER_1_TYPE",
                    "IDENTIFIER_2", "IDENTIFIER_2_TYPE",
                    "VERSION_DATE", "CORRELATION_METHOD"])
        w.writerow([1001, "BLPU UPRN", "osgb-bldg-1001",
                    "TopographicArea TOID", "2024-01-01", "1"])
        # UPRN 1002 deliberately ABSENT from LIDS → non-postal
        w.writerow([1003, "BLPU UPRN", "osgb-bldg-1003",
                    "TopographicArea TOID", "2024-01-01", "1"])


def test_build_end_to_end_with_synthetic_fixtures(tmp_path: Path):
    """Run the orchestrator against synthetic CSV inputs via
    --skip-download. Validates: schema applies, sources load + clip,
    bands classify, manifest writes. Skips INSPIRE + Zoomstack (their
    inputs need their own fixture shapes; the band path runs without
    them).
    """
    from lleolydd.cache.build import BuildPaths, build

    bounds = tmp_path / "area-bounds.geojson"
    _make_gwynedd_bounds_fixture(bounds)
    data_dir = tmp_path / "data"

    # Pre-place synthetic fixtures where the orchestrator's
    # --skip-download path will look for them.
    paths = BuildPaths.resolve(data_dir, "2026-05")
    paths.downloads_dir.mkdir(parents=True, exist_ok=True)
    _write_synthetic_uprn_csv(paths.downloads_dir / "osopenuprn_202605.csv")
    _write_synthetic_toid_csv(paths.downloads_dir / "osopentoid_202605_csv_sh.csv")
    _write_synthetic_lids_csv(
        paths.downloads_dir
        / "lids-2026-03_csv_BLPU-UPRN-TopographicArea-TOID-5.csv"
    )

    summary = build(
        data_dir=data_dir,
        area_bounds=bounds,
        release="2026-05",
        sources=["open-uprn", "open-toid", "open-linked-ids"],
        skip_download=True,
        force=True,    # snapshot_dir was pre-created to seed fixtures
    )

    # Cache db exists
    assert paths.cache_db.is_file()

    # Manifest exists
    manifest_path = paths.snapshot_dir / "manifest.json"
    assert manifest_path.is_file()

    # Band stats present and total matches the in-bounds UPRN count (3)
    assert summary["band_stats"]["total"] == 3

    # Per-source counts:
    # - open-uprn: 4 rows in CSV, 3 in bounds (one outside synthetic
    #              Gwynedd polygon is filtered)
    assert summary["per_source"]["open-uprn"]["rows_in"] == 4
    assert summary["per_source"]["open-uprn"]["rows_in_area"] == 3

    # - open-toid: 3 rows in CSV, only 2 are buildings AND in bounds.
    #              The "Road Or Track" row is dropped by the building
    #              filter even though its polygon overlaps bounds.
    assert summary["per_source"]["open-toid"]["rows_in"] == 3
    assert summary["per_source"]["open-toid"]["rows_in_area"] == 2

    # - open-linked-ids: 2 LIDS rows match UPRNs in the cache (1001, 1003)
    assert summary["per_source"]["open-linked-ids"]["rows_in_area"] == 2

    # Spot-check band assignments
    conn = duckdb.connect(str(paths.cache_db), read_only=True)
    bands = dict(conn.execute(
        "SELECT uprn, snap_band FROM uprn ORDER BY uprn"
    ).fetchall())
    conn.close()
    assert bands == {
        1001: "auto-snapped",   # in osgb-bldg-1001, LIDS confirms
        1002: "non-postal",     # not in any building TOID, no LIDS row
        1003: "auto-snapped",   # in osgb-bldg-1003, LIDS confirms
    }


def test_build_bbox_prefilter_keeps_polygon_only_rows(tmp_path: Path):
    """The bbox prefilter is a prefilter, not a replacement for
    ST_Within. A row inside the bbox but outside the (non-rectangular)
    polygon must still be dropped by the polygon test — the bbox check
    only removes the obviously-outside rows cheaply.

    Polygon shape: L-shape carved from the synthetic 20x15 km bbox.
    The bbox covers [265000..285000, 310000..325000]; the L excludes
    the south-west quadrant [265000..275000, 310000..317500]. A
    UPRN placed at (270000, 312000) is inside the bbox but inside the
    excluded notch — bbox passes, ST_Within drops.
    """
    from lleolydd.cache.build import BuildPaths, build

    # L-shaped polygon: full bbox minus the south-west quadrant.
    bounds = tmp_path / "area-bounds.geojson"
    bounds.parent.mkdir(parents=True, exist_ok=True)
    bounds.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Gwynedd-L"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [265000, 317500],  # NW of the notch
                    [275000, 317500],
                    [275000, 310000],
                    [285000, 310000],
                    [285000, 325000],
                    [265000, 325000],
                    [265000, 317500],
                ]],
            },
        }],
    }))

    data_dir = tmp_path / "data"
    paths = BuildPaths.resolve(data_dir, "2026-05")
    paths.downloads_dir.mkdir(parents=True, exist_ok=True)

    # Three UPRNs:
    # - 3001: outside bbox entirely (bbox catches it).
    # - 3002: inside bbox AND inside L (kept).
    # - 3003: inside bbox but inside the excluded notch (bbox passes,
    #         polygon test drops).
    with (paths.downloads_dir / "osopenuprn_202605.csv").open(
        "w", newline=""
    ) as f:
        w = csv.writer(f)
        w.writerow(["UPRN", "X_COORDINATE", "Y_COORDINATE",
                    "LATITUDE", "LONGITUDE"])
        w.writerow([3001, 600000, 200000, 51.0, -1.0])    # outside bbox
        w.writerow([3002, 280000, 320000, 52.8, -3.8])    # in L (NE corner)
        w.writerow([3003, 270000, 312000, 52.7, -3.9])    # in notch

    summary = build(
        data_dir=data_dir,
        area_bounds=bounds,
        release="2026-05",
        sources=["open-uprn"],
        skip_download=True,
        force=True,
    )

    # rows_in is the national total (3); rows_in_area is the polygon
    # survivors (1 — only 3002).
    assert summary["per_source"]["open-uprn"]["rows_in"] == 3
    assert summary["per_source"]["open-uprn"]["rows_in_area"] == 1

    # Spot-check the surviving UPRN.
    conn = duckdb.connect(str(paths.cache_db), read_only=True)
    uprns = [r[0] for r in conn.execute(
        "SELECT uprn FROM uprn ORDER BY uprn"
    ).fetchall()]
    conn.close()
    assert uprns == [3002], (
        "expected only UPRN 3002 (inside L-polygon) to survive; "
        f"got {uprns}. Did the bbox prefilter accidentally replace "
        "the ST_Within polygon test?"
    )


def test_build_refuses_to_overwrite_existing_snapshot(tmp_path: Path):
    """Existing snapshot dir without --force is a hard failure (per
    cli-design.md §5: 'Idempotent against an existing release directory;
    refuses to overwrite without --force')."""
    from lleolydd.cache.build import BuildPaths, build

    bounds = tmp_path / "area-bounds.geojson"
    _make_gwynedd_bounds_fixture(bounds)
    data_dir = tmp_path / "data"

    # Manually create the snapshot dir so the second build hits the
    # "already exists" guard.
    paths = BuildPaths.resolve(data_dir, "2026-05")
    paths.snapshot_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="already exists"):
        build(
            data_dir=data_dir,
            area_bounds=bounds,
            release="2026-05",
            sources=[],
            dry_run=False,
        )
