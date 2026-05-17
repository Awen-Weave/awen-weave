"""
OS Open TOID — TopographicArea polygons for every OS MasterMap feature
in GB, tiled by 100km National Grid square.

Gwynedd sits in two 100km squares: SH (Snowdonia / coastal Gwynedd /
Anglesey / north-west) and SJ (eastern Gwynedd / Wrexham / Cheshire).
We download both tiles, clip to Gwynedd at load time.

CSV columns per OS docs: TOID, ALT, GEOMETRY (a WKT polygon in
EPSG:27700), FEATURE_TYPE (TopographicArea / Boundary / Symbol /
Cartographic / Generic / Land / Structuring), VERSION, VERSION_DATE,
DESCRIPTION_GROUP, DESCRIPTION_TERM, MAKE, PHYSICAL_LEVEL,
PHYSICAL_PRESENCE.

For Lleolydd we keep only Building / Structure-typed features —
buildings are what we snap UPRNs to. The other feature types (roads,
boundaries, water) live in OS data but aren't relevant for UPRN
verification at v1.

The polygon clip uses a bbox prefilter on the parsed geometry's
ST_XMin/XMax/YMin/YMax (a rectangle-overlap test, cheap) before the
expensive ST_Intersects against Gwynedd's full multi-polygon.
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


# DESCRIPTION_GROUP values that indicate a building-shaped feature.
# OS uses these in the TopographicArea layer; non-building features
# (roads, water, land cover) carry other values and we drop them.
BUILDING_DESCRIPTION_GROUPS: tuple[str, ...] = (
    "Building",
    "Built Environment",  # belt-and-braces; OS sometimes uses this
    "Glasshouse",
)


def load_into_duckdb(
    conn: duckdb.DuckDBPyConnection,
    file_paths: list[Path],
    area_bounds_wkt: str,
    area_bounds_bbox: tuple[float, float, float, float],
    snapshot_id: str,
) -> dict:
    """Load OS Open TOID into the cache `toid` table, clipped to
    area_bounds_wkt AND filtered to building-shaped feature types.

    The CSV's GEOMETRY column is WKT in EPSG:27700. The load is one
    INSERT per tile, with the WKT-parsed geometry materialised once
    in an inner subquery so each row's geometry is parsed exactly
    twice (once for the polygon/centroid projection, once for the
    bbox + ST_Intersects clip). The bbox-overlap test is four
    cheap comparisons on the parsed geom's MBR; ST_Intersects against
    the full Gwynedd polygon only runs on bbox survivors.
    """
    csv_paths = [p for p in file_paths if p.suffix.lower() == ".csv"]
    if not csv_paths:
        raise RuntimeError(
            f"OS Open TOID: no CSV in extracted files: {file_paths}"
        )

    xmin, ymin, xmax, ymax = area_bounds_bbox

    total_in = 0
    total_buildings = 0
    source_hashes: dict[str, str] = {}

    # OS Open TOID CSV doesn't carry a header row — column order is
    # documented as TOID, ALT, GEOMETRY, FEATURE_TYPE, VERSION,
    # VERSION_DATE, DESCRIPTION_GROUP, DESCRIPTION_TERM, MAKE,
    # PHYSICAL_LEVEL, PHYSICAL_PRESENCE. We specify columns explicitly.
    column_spec = {
        "toid": "VARCHAR",
        "alt": "VARCHAR",
        "geometry_wkt": "VARCHAR",
        "feature_type": "VARCHAR",
        "version": "VARCHAR",
        "version_date": "VARCHAR",
        "description_group": "VARCHAR",
        "description_term": "VARCHAR",
        "make": "VARCHAR",
        "physical_level": "VARCHAR",
        "physical_presence": "VARCHAR",
    }
    columns_arg = ", ".join(f"'{k}': '{v}'" for k, v in column_spec.items())

    # Build the building-filter predicate. We accept rows whose
    # DESCRIPTION_GROUP starts with any of the building groups (OS
    # sometimes ends them with "(secondary)" / "(under construction)".
    group_predicate = " OR ".join(
        f"description_group ILIKE '{g}%'" for g in BUILDING_DESCRIPTION_GROUPS
    )

    for csv_path in csv_paths:
        source_hashes[csv_path.name] = sha256_file(csv_path)
        print(
            f"[open_toid] counting rows in {csv_path.name} …",
            flush=True,
        )
        n_tile = conn.execute(
            "SELECT COUNT(*) FROM read_csv_auto(?, header=false, columns={"
            + columns_arg + "})",
            [str(csv_path)],
        ).fetchone()[0]
        total_in += n_tile
        print(
            f"[open_toid]   {n_tile:,} rows in tile; "
            f"filtering to buildings inside Gwynedd bbox + polygon …",
            flush=True,
        )

        # Insert building polygons that intersect area_bounds.
        # Inner subquery: building filter + materialise WKT geom once.
        # Outer WHERE: bbox-overlap on the geom's MBR + ST_Intersects.
        before = conn.execute("SELECT COUNT(*) FROM toid").fetchone()[0]
        conn.execute(
            f"""
            INSERT INTO toid
                (toid, polygon_geom, feature_type, description_group,
                 description_term, centroid_geom, snapshot_id)
            SELECT
                t.toid,
                t.geom AS polygon_geom,
                t.feature_type,
                t.description_group,
                t.description_term,
                ST_Centroid(t.geom) AS centroid_geom,
                ? AS snapshot_id
            FROM (
                SELECT
                    toid,
                    feature_type,
                    description_group,
                    description_term,
                    ST_GeomFromText(geometry_wkt) AS geom
                FROM read_csv_auto(?, header=false, columns={{{columns_arg}}})
                WHERE ({group_predicate})
            ) AS t
            WHERE ST_XMax(t.geom) >= ?
              AND ST_XMin(t.geom) <= ?
              AND ST_YMax(t.geom) >= ?
              AND ST_YMin(t.geom) <= ?
              AND ST_Intersects(
                  t.geom,
                  ST_GeomFromText('{area_bounds_wkt}')
              )
            ON CONFLICT (toid) DO NOTHING
            """,
            [snapshot_id, str(csv_path), xmin, xmax, ymin, ymax],
        )
        after = conn.execute("SELECT COUNT(*) FROM toid").fetchone()[0]
        added = after - before
        total_buildings += added
        print(
            f"[open_toid]   +{added:,} building polygons "
            f"(total in toid table: {after:,})",
            flush=True,
        )

    return {
        "rows_in": total_in,
        "rows_in_area": total_buildings,
        "tiles": list(GWYNEDD_GRID_TILES),
        "source_files": {str(p): source_hashes[p.name] for p in csv_paths},
        "columns": [
            "toid", "polygon_geom", "feature_type", "description_group",
            "description_term", "centroid_geom",
        ],
    }
