"""
OS Open UPRN — every UPRN in GB with its OS Open coordinate.

Ships as a single national CSV (no Wales-only cut available on OS
Data Hub). ~617 MB compressed → ~3.5 GB uncompressed CSV with columns
UPRN, X_COORDINATE, Y_COORDINATE, LATITUDE, LONGITUDE.

We load the whole national CSV into a temporary DuckDB table, then
INSERT … WHERE ST_Within(point, area_bounds) into the final `uprn`
table. The national file disappears from cache.duckdb after the clip;
only the Gwynedd subset persists.

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
    snapshot_id: str,
) -> dict:
    """Load OS Open UPRN into the cache `uprn` table, clipped to
    area_bounds_wkt. Coordinates are OSGB36 (EPSG:27700); we keep them
    in BNG for spatial lookups against TOID polygons (same CRS), and
    derive a WGS84 point for map rendering.

    The CSV columns are UPRN, X_COORDINATE, Y_COORDINATE, LATITUDE,
    LONGITUDE. Phase 1 doesn't yet use LATITUDE/LONGITUDE — Phase 2
    viewer rendering does.
    """
    csv_paths = [p for p in file_paths if p.suffix.lower() == ".csv"]
    if not csv_paths:
        raise RuntimeError(
            f"OS Open UPRN: no CSV in extracted files: {file_paths}"
        )
    csv_path = csv_paths[0]

    # Use a temp table for the national load, then INSERT-with-clip into
    # the final `uprn` table. The temp goes away with the connection
    # (or could be explicitly dropped); the national data never lands
    # in the persistent cache.
    # DuckDB treats column names case-insensitively, so a literal
    # `CAST(UPRN AS BIGINT) AS uprn` triggers a "column UPRN exists
    # in SELECT clause - but cannot be referenced before defined"
    # binder error (it reads the alias as a self-reference). Read via
    # subquery first, then transform — keeps the original column names
    # from the CSV separate from our aliases.
    conn.execute("DROP TABLE IF EXISTS _staging_uprn")
    conn.execute(
        """
        CREATE TEMP TABLE _staging_uprn AS
        SELECT
            CAST(src."UPRN" AS BIGINT) AS uprn,
            CAST(src."X_COORDINATE" AS DOUBLE) AS x_bng,
            CAST(src."Y_COORDINATE" AS DOUBLE) AS y_bng,
            CAST(src."LATITUDE" AS DOUBLE) AS latitude,
            CAST(src."LONGITUDE" AS DOUBLE) AS longitude
        FROM read_csv_auto(?, header=true) AS src
        """,
        [str(csv_path)],
    )

    total_in = conn.execute(
        "SELECT COUNT(*) FROM _staging_uprn"
    ).fetchone()[0]

    # Insert clipped rows. ST_Within on BNG point against the bounds
    # polygon (also in BNG). Point geometry is ST_Point(x, y).
    conn.execute(
        f"""
        INSERT INTO uprn
            (uprn, point_geom, snapped_toid, snap_band, snap_confidence,
             latitude, longitude, snapshot_id)
        SELECT
            uprn,
            ST_Point(x_bng, y_bng) AS point_geom,
            NULL,        -- snapped_toid: filled later by bands.py
            NULL,        -- snap_band: ditto
            NULL,        -- snap_confidence: ditto
            latitude,
            longitude,
            ?
        FROM _staging_uprn
        WHERE ST_Within(
            ST_Point(x_bng, y_bng),
            ST_GeomFromText('{area_bounds_wkt}')
        )
        """,
        [snapshot_id],
    )

    rows_in_area = conn.execute("SELECT COUNT(*) FROM uprn").fetchone()[0]
    conn.execute("DROP TABLE _staging_uprn")

    return {
        "rows_in": total_in,
        "rows_in_area": rows_in_area,
        "columns": ["uprn", "point_geom", "latitude", "longitude"],
        "source_file": str(csv_path),
        "source_file_sha256": sha256_file(csv_path),
    }
