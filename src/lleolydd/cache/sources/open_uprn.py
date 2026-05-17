"""
OS Open UPRN — every UPRN in GB with its OS Open coordinate.

Ships as a single national CSV (no Wales-only cut available on OS
Data Hub). ~617 MB compressed → ~3.5 GB uncompressed CSV with columns
UPRN, X_COORDINATE, Y_COORDINATE, LATITUDE, LONGITUDE.

We load the whole national CSV through a streaming INSERT, clipping to
`area_bounds`. To keep the spatial-clip tractable on a Pi, a cheap BNG
bbox prefilter runs first (5 BETWEEN tests in EPSG:27700); ST_Within
against the full polygon only evaluates on bbox survivors.

Worked out 2026-05-16: ~50k Gwynedd UPRNs out of ~37M GB UPRNs total.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from ._common import (
    download_file,
    list_product_downloads,
    md5_file,
    sha256_file,
    unzip,
)

PRODUCT_NAME = "os-open-uprn"
PRODUCT_ID = "OpenUPRN"
DOWNLOAD_FORMAT = "CSV"   # tighter than GeoPackage for this product
# Filenames look like "osopenuprn_<YYYYMM>.csv" — used by build.py's
# --skip-download path to pick the right file out of a mixed pool.
# Match by prefix; this is distinct from LIDS files (which have
# "lids-" prefix) and TOID files ("osopentoid_" prefix).
FILENAME_PATTERN = "osopenuprn"
# schema-sniff contract — see src/cli/lleolydd_cache.py schema-sniff
# subcommand and _common.sniff_columns. Per-source CSV/GML kind tells
# the sniffer how to read the header; EXPECTED_COLUMNS is the tuple
# the loader assumes is present. Drift = any diff vs the live file.
SOURCE_KIND = "csv"
EXPECTED_COLUMNS: tuple[str, ...] = (
    "UPRN", "X_COORDINATE", "Y_COORDINATE", "LATITUDE", "LONGITUDE",
)


def list_remote_files() -> list[dict]:
    """OS Open UPRN ships as one national-GB CSV zip. Return that entry."""
    entries = list_product_downloads(PRODUCT_ID)
    return [e for e in entries if e.get("format") == DOWNLOAD_FORMAT]


def download(
    target_dir: Path,
    area_bounds_wkt: str | None = None,  # noqa: ARG001 — informational
    release: str | None = None,          # noqa: ARG001 — informational
    force: bool = False,
) -> list[Path]:
    """Download the national OS Open UPRN zip + extract. Returns the
    list of extracted file paths (one CSV)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    entries = list_remote_files()
    if not entries:
        raise RuntimeError(
            "OS Open UPRN: no CSV entry returned by Downloads API"
        )
    entry = entries[0]
    zip_path = target_dir / entry["fileName"]
    download_file(
        entry["url"],
        zip_path,
        expected_md5=entry.get("md5"),
        expected_size=entry.get("size"),
        force=force,
    )
    return unzip(zip_path, target_dir, force=force)


def load_into_duckdb(
    conn: duckdb.DuckDBPyConnection,
    file_paths: list[Path],
    area_bounds_wkt: str,
    area_bounds_bbox: tuple[float, float, float, float],
    snapshot_id: str,
) -> dict:
    """Load OS Open UPRN into the cache `uprn` table, clipped to
    area_bounds_wkt. Coordinates are OSGB36 (EPSG:27700); we keep them
    in BNG for spatial lookups against TOID polygons (same CRS), and
    derive a WGS84 point for map rendering.

    The CSV columns are UPRN, X_COORDINATE, Y_COORDINATE, LATITUDE,
    LONGITUDE. Phase 1 doesn't yet use LATITUDE/LONGITUDE — Phase 2
    viewer rendering does.

    Two passes over the CSV:
      1. COUNT(*) — manifest semantic for `rows_in` is "rows in the
         national source file". Cheap CSV scan; DuckDB doesn't
         materialise per-row state for a bare COUNT.
      2. INSERT — streaming pass with bbox prefilter inside the
         subquery (cheap, 4 BETWEEN comparisons in BNG) and ST_Within
         against the full polygon as the outer WHERE (expensive,
         scales with polygon-vertex count). With Gwynedd's
         72k-vertex multipolygon the bbox prefilter discards ~99% of
         national rows before any spatial test runs, so the previous
         OOM-grade RSS + multi-hour runtime is gone.
    """
    csv_paths = [p for p in file_paths if p.suffix.lower() == ".csv"]
    if not csv_paths:
        raise RuntimeError(
            f"OS Open UPRN: no CSV in extracted files: {file_paths}"
        )
    csv_path = csv_paths[0]
    xmin, ymin, xmax, ymax = area_bounds_bbox

    print(
        f"[open_uprn] counting national rows in {csv_path.name} …",
        flush=True,
    )
    total_in = conn.execute(
        "SELECT COUNT(*) FROM read_csv_auto(?, header=true)",
        [str(csv_path)],
    ).fetchone()[0]
    print(
        f"[open_uprn]   {total_in:,} national rows; "
        f"clipping to Gwynedd bbox + polygon …",
        flush=True,
    )

    # INSERT-from-subquery. The inner SELECT renames columns away from
    # the case-insensitive collision (CSV "UPRN" vs. INSERT alias
    # "uprn"), applies the cheap bbox prefilter, and casts coords once.
    # The outer SELECT then runs ST_Within on bbox survivors only.
    # Streaming end-to-end — no national staging table.
    conn.execute(
        f"""
        INSERT INTO uprn
            (uprn, point_geom, snapped_toid, snap_band, snap_confidence,
             latitude, longitude, snapshot_id)
        SELECT
            t.uprn,
            ST_Point(t.x_bng, t.y_bng) AS point_geom,
            NULL,        -- snapped_toid: filled later by bands.py
            NULL,        -- snap_band: ditto
            NULL,        -- snap_confidence: ditto
            t.latitude,
            t.longitude,
            ?
        FROM (
            SELECT
                CAST(src."UPRN" AS BIGINT) AS uprn,
                CAST(src."X_COORDINATE" AS DOUBLE) AS x_bng,
                CAST(src."Y_COORDINATE" AS DOUBLE) AS y_bng,
                CAST(src."LATITUDE" AS DOUBLE) AS latitude,
                CAST(src."LONGITUDE" AS DOUBLE) AS longitude
            FROM read_csv_auto(?, header=true) AS src
            WHERE CAST(src."X_COORDINATE" AS DOUBLE) BETWEEN ? AND ?
              AND CAST(src."Y_COORDINATE" AS DOUBLE) BETWEEN ? AND ?
        ) AS t
        WHERE ST_Within(
            ST_Point(t.x_bng, t.y_bng),
            ST_GeomFromText('{area_bounds_wkt}')
        )
        """,
        [snapshot_id, str(csv_path), xmin, xmax, ymin, ymax],
    )

    rows_in_area = conn.execute("SELECT COUNT(*) FROM uprn").fetchone()[0]
    print(
        f"[open_uprn]   {rows_in_area:,} rows in Gwynedd "
        f"(of {total_in:,} national)",
        flush=True,
    )

    return {
        "rows_in": total_in,
        "rows_in_area": rows_in_area,
        "columns": ["uprn", "point_geom", "latitude", "longitude"],
        "source_file": str(csv_path),
        "source_file_sha256": sha256_file(csv_path),
    }
