"""
OS BoundaryLine — administrative boundaries for GB.

Used ONCE per project to derive the Gwynedd boundary polygon, saved to
seed/lleolydd/area-bounds.geojson. Subsequent cache builds read the
geojson directly (no BoundaryLine re-download needed).

CLI: `lleolydd-cache derive-bounds --lad Gwynedd --output seed/...`.

Schema reference: OS BoundaryLine, INSPIRE GML format as of 2026-05-16.
Pre-2026 releases shipped per-tier files (district_borough_unitary_region.gml
etc.) with NAME column; that schema is no longer supported here.
If future releases drift again, both INSPIRE_GML_FILENAME and
LAD_NAME_COLUMN may need updating — the fail-loud RuntimeErrors below
will surface the change clearly with the diagnostic SQL to use.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from ._common import (
    download_file,
    list_product_downloads,
    sha256_file,
    unzip,
)

PRODUCT_NAME = "os-boundary-line"
PRODUCT_ID = "BoundaryLine"
DOWNLOAD_FORMAT = "GML"   # 168 MB; the smallest format for this product

INSPIRE_GML_FILENAME = "INSPIRE_AdministrativeUnit.gml"
LAD_NAME_COLUMN = "text"  # current as of 2026-05-16; was 'NAME' in legacy schema

# schema-sniff contract — see src/cli/lleolydd_cache.py schema-sniff
# subcommand and _common.sniff_columns. INSPIRE_AdministrativeUnit.gml
# exposes many GML attributes via OGR; the loader only depends on
# `text` (the LAD name) and `geometry` (the polygon). EXPECTED_COLUMNS
# pins those two — drift on either is what the loader cares about.
SOURCE_KIND = "gml"
EXPECTED_COLUMNS: tuple[str, ...] = (LAD_NAME_COLUMN, "geometry")
# Sniff probes a specific filename within the extracted set rather
# than the first GML it finds — keeps the contract aligned with the
# loader's own filename check.
SNIFF_FILENAME = INSPIRE_GML_FILENAME


def list_remote_files() -> list[dict]:
    entries = list_product_downloads(PRODUCT_ID)
    return [e for e in entries if e.get("format") == DOWNLOAD_FORMAT]


def download(
    target_dir: Path,
    area_bounds_wkt: str | None = None,  # noqa: ARG001
    release: str | None = None,          # noqa: ARG001
    force: bool = False,
) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    entries = list_remote_files()
    if not entries:
        raise RuntimeError(
            "OS BoundaryLine: no GML entry from Downloads API"
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


def extract_lad_polygon(
    files: list[Path],
    lad_name: str,
    output_geojson: Path,
) -> dict:
    """Extract a named LAD polygon from the BoundaryLine INSPIRE GML,
    save it as a single-feature GeoJSON. Used to derive Gwynedd's
    bounds once.

    Targets INSPIRE_AdministrativeUnit.gml (the current OS BoundaryLine
    layout — one file, not the legacy per-tier set) and queries the
    `text` column (replaces the legacy `NAME`). Fails loud with a
    diagnostic message if either is missing — so the next OGL format
    drift surfaces fast rather than being silently swallowed.

    Returns metadata dict with the polygon's bounding box + area.
    """
    inspire_gml = next(
        (p for p in files if p.name == INSPIRE_GML_FILENAME),
        None,
    )
    if inspire_gml is None:
        raise RuntimeError(
            f"OS BoundaryLine schema appears to have changed: expected "
            f"{INSPIRE_GML_FILENAME} in the extracted file set but it "
            f"is not present. Found: "
            f"{[p.name for p in files if p.suffix.lower() == '.gml']}. "
            f"Review the live release structure at "
            f"https://osdatahub.os.uk/downloads/open/BoundaryLine and "
            f"update INSPIRE_GML_FILENAME / LAD_NAME_COLUMN in "
            f"src/lleolydd/cache/sources/boundary_line.py."
        )

    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")

    try:
        row = conn.execute(
            f'''
            SELECT ST_AsGeoJSON(geometry) AS geom_json,
                   ST_AsText(geometry) AS geom_wkt,
                   ST_XMin(geometry) AS x_min,
                   ST_YMin(geometry) AS y_min,
                   ST_XMax(geometry) AS x_max,
                   ST_YMax(geometry) AS y_max,
                   ST_Area(geometry) AS area_m2
            FROM ST_Read(?)
            WHERE "{LAD_NAME_COLUMN}" ILIKE ?
            LIMIT 1
            ''',
            [str(inspire_gml), lad_name],
        ).fetchone()
    except duckdb.BinderException as e:
        raise RuntimeError(
            f"OS BoundaryLine INSPIRE GML missing expected column "
            f"{LAD_NAME_COLUMN!r}: {e}. Live release schema may have "
            f"changed; verify with `SELECT * FROM ST_Read("
            f"'{inspire_gml}') LIMIT 1` and update LAD_NAME_COLUMN in "
            f"src/lleolydd/cache/sources/boundary_line.py."
        ) from e

    if row is None:
        raise RuntimeError(
            f"No row in {INSPIRE_GML_FILENAME} matches LAD name "
            f"{lad_name!r}. Check spelling against the live data: "
            f"`SELECT DISTINCT \"{LAD_NAME_COLUMN}\" FROM ST_Read("
            f"'{inspire_gml}') WHERE \"{LAD_NAME_COLUMN}\" ILIKE "
            f"'%{lad_name[:3]}%'`."
        )

    geom_json, _geom_wkt, xmin, ymin, xmax, ymax, area_m2 = row
    feature = {
        "type": "Feature",
        "properties": {
            "name": lad_name,
            "source": "OS BoundaryLine (INSPIRE GML)",
            "extracted_from": str(inspire_gml),
        },
        "geometry": json.loads(geom_json),
    }
    feature_collection = {
        "type": "FeatureCollection",
        "features": [feature],
    }
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.write_text(
        json.dumps(feature_collection, indent=2)
    )
    return {
        "lad": lad_name,
        "source_file": str(inspire_gml),
        "source_file_sha256": sha256_file(inspire_gml),
        "geojson_path": str(output_geojson),
        "bbox_bng": [xmin, ymin, xmax, ymax],
        "area_m2": area_m2,
    }
