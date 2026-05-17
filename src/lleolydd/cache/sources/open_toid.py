"""
OS Open TOID — TOID identifiers + representative points for every OS
feature in GB, tiled by 100km National Grid square.

Gwynedd sits in two 100km squares: SH (Snowdonia / coastal Gwynedd /
Anglesey / north-west) and SJ (eastern Gwynedd / Wrexham / Cheshire).
We download both tiles, clip to Gwynedd at load time.

Schema reference: OS Open TOID, 6-column file as of the 2026-04
release. Pre-2026 releases shipped 11 columns with WKT GEOMETRY +
DESCRIPTION_GROUP — that polygon data has moved to OS NGD (different
access pattern, deferred to Lleolydd Phase 1.x). For v1, we load TOID
representative points (EASTING/NORTHING) and bands.py uses point-
proximity rather than point-in-polygon. The `toid.polygon_geom`
column kept nullable for the eventual NGD upgrade.

CSV columns as of 2026-04 release:
  TOID            unique TopographicArea identifier
  VERSION_NUMBER  feature version
  VERSION_DATE    when this version landed
  SOURCE_PRODUCT  always "OS MasterMap Topography Layer"
  EASTING         BNG easting of feature's representative point
  NORTHING        BNG northing of feature's representative point

The 2026-04 file has a UTF-8 BOM on the header row. DuckDB's CSV
sniffer handles it; we never reference the column by name from the
BOM-prefixed `TOID` so the sniff is what does the work.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from ._common import (
    download_file,
    list_product_downloads,
    sha256_file,
    unzip,
)

PRODUCT_NAME = "os-open-toid"
PRODUCT_ID = "OpenTOID"
DOWNLOAD_FORMAT = "CSV"
FILENAME_PATTERN = "osopentoid"

# 100km National Grid squares that cover Gwynedd. SH is the bulk of
# Gwynedd (Snowdonia, Llŷn, Anglesey, north coast). SJ catches the
# south-eastern slivers (around Bala, Corwen).
GWYNEDD_GRID_TILES: tuple[str, ...] = ("SH", "SJ")

# schema-sniff contract — see src/cli/lleolydd_cache.py schema-sniff
# subcommand and _common.sniff_columns. EXPECTED_COLUMNS is the
# 2026-04 schema, surfaced as a constant so the schema-sniff CLI can
# diff it against the live file. If OS changes the schema again,
# update this tuple and the INSERT below.
SOURCE_KIND = "csv"
EXPECTED_COLUMNS: tuple[str, ...] = (
    "TOID", "VERSION_NUMBER", "VERSION_DATE",
    "SOURCE_PRODUCT", "EASTING", "NORTHING",
)
# Date-tagged alias kept for diagnostic readability — when OS publishes
# yet another schema, leaving the *_AS_OF_2026_04 here makes the prior
# spec auditable next to the new one.
OPEN_TOID_COLUMNS_AS_OF_2026_04: tuple[str, ...] = EXPECTED_COLUMNS


def list_remote_files() -> list[dict]:
    """Return all CSV-format entries for the SH + SJ tiles."""
    entries = list_product_downloads(PRODUCT_ID)
    return [
        e for e in entries
        if e.get("format") == DOWNLOAD_FORMAT
        and e.get("area") in GWYNEDD_GRID_TILES
    ]


def download(
    target_dir: Path,
    area_bounds_wkt: str | None = None,  # noqa: ARG001
    release: str | None = None,          # noqa: ARG001
    force: bool = False,
) -> list[Path]:
    """Download both SH and SJ TOID CSV zips, extract each. Returns the
    list of extracted CSV paths."""
    target_dir.mkdir(parents=True, exist_ok=True)
    entries = list_remote_files()
    if len(entries) != len(GWYNEDD_GRID_TILES):
        # Note in case OS removes one of the tiles (very unlikely) —
        # surface clearly rather than silently producing an incomplete
        # cache.
        got = {e.get("area") for e in entries}
        missing = set(GWYNEDD_GRID_TILES) - got
        if missing:
            raise RuntimeError(
                f"OS Open TOID: missing tiles for Gwynedd: {sorted(missing)}. "
                f"Got: {sorted(got)}."
            )

    extracted: list[Path] = []
    for entry in entries:
        zip_path = target_dir / entry["fileName"]
        download_file(
            entry["url"],
            zip_path,
            expected_md5=entry.get("md5"),
            expected_size=entry.get("size"),
            force=force,
        )
        extracted.extend(unzip(zip_path, target_dir, force=force))
    return extracted


def load_into_duckdb(
    conn: duckdb.DuckDBPyConnection,
    file_paths: list[Path],
    area_bounds_wkt: str,    # noqa: ARG001 — v1 uses bbox-only clip
    area_bounds_bbox: tuple[float, float, float, float],
    snapshot_id: str,
) -> dict:
    """Load OS Open TOID's 6-column shape into the cache `toid` table,
    populating `point_geom` from EASTING/NORTHING. `polygon_geom`
    remains NULL — Phase 1.x will fill it from OS NGD.

    For v1 the clip is bbox-only on EASTING/NORTHING. Gwynedd's bbox
    is mostly Gwynedd-polygon (within a coastline tolerance); using
    bbox-only here is cheap and accepted by the degraded-semantic
    decision. bands.py's ST_DWithin then does the per-UPRN proximity
    work.
    """
    csv_paths = [p for p in file_paths if p.suffix.lower() == ".csv"]
    if not csv_paths:
        raise RuntimeError(
            f"OS Open TOID: no CSV in extracted files: {file_paths}"
        )

    xmin, ymin, xmax, ymax = area_bounds_bbox

    total_in = 0
    total_in_area = 0
    source_hashes: dict[str, str] = {}

    for csv_path in csv_paths:
        source_hashes[csv_path.name] = sha256_file(csv_path)
        print(
            f"[open_toid] counting rows in {csv_path.name} …",
            flush=True,
        )
        n_tile = conn.execute(
            "SELECT COUNT(*) FROM read_csv_auto(?, header=true)",
            [str(csv_path)],
        ).fetchone()[0]
        total_in += n_tile
        print(
            f"[open_toid]   {n_tile:,} rows in tile; "
            f"clipping to Gwynedd bbox …",
            flush=True,
        )

        before = conn.execute("SELECT COUNT(*) FROM toid").fetchone()[0]
        # INSERT-from-subquery. Inner SELECT renames CSV columns away
        # from the case-insensitive collision and applies the bbox
        # prefilter on EASTING / NORTHING (cheap). No outer ST_Within
        # needed at v1 — bands.py does the per-UPRN proximity work.
        conn.execute(
            """
            INSERT INTO toid
                (toid, point_geom, polygon_geom, feature_type,
                 description_group, description_term,
                 centroid_geom, snapshot_id)
            SELECT
                t.toid_id AS toid,
                ST_Point(t.easting, t.northing) AS point_geom,
                NULL AS polygon_geom,         -- v1.x via OS NGD
                NULL AS feature_type,         -- v1.x via OS NGD
                NULL AS description_group,    -- v1.x via OS NGD
                NULL AS description_term,     -- v1.x via OS NGD
                NULL AS centroid_geom,        -- v1.x derived from polygon
                ? AS snapshot_id
            FROM (
                SELECT
                    CAST(src."TOID" AS VARCHAR) AS toid_id,
                    CAST(src."EASTING" AS DOUBLE) AS easting,
                    CAST(src."NORTHING" AS DOUBLE) AS northing
                FROM read_csv_auto(?, header=true) AS src
                WHERE CAST(src."EASTING" AS DOUBLE) BETWEEN ? AND ?
                  AND CAST(src."NORTHING" AS DOUBLE) BETWEEN ? AND ?
            ) AS t
            ON CONFLICT (toid) DO NOTHING
            """,
            [snapshot_id, str(csv_path), xmin, xmax, ymin, ymax],
        )
        after = conn.execute("SELECT COUNT(*) FROM toid").fetchone()[0]
        added = after - before
        total_in_area += added
        print(
            f"[open_toid]   +{added:,} TOID points in Gwynedd bbox "
            f"(total in toid table: {after:,})",
            flush=True,
        )

    return {
        "rows_in": total_in,
        "rows_in_area": total_in_area,
        "tiles": list(GWYNEDD_GRID_TILES),
        "source_files": {str(p): source_hashes[p.name] for p in csv_paths},
        "columns": ["toid", "point_geom"],
        "schema_note": (
            "v1: 6-column OS Open TOID (2026-04 release) — point_geom "
            "from EASTING/NORTHING. polygon_geom NULL until v1.x NGD "
            "integration."
        ),
    }
