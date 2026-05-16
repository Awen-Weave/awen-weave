"""
OS BoundaryLine — administrative boundaries for GB.

Used ONCE per project to derive the Gwynedd boundary polygon, saved to
seed/lleolydd/area-bounds.geojson. Subsequent cache builds read the
geojson directly (no BoundaryLine re-download needed).

The 168 MB GML download contains every UK admin boundary from country
down to ward. We extract the unitary-authority polygon for "Gwynedd"
(NAME = "Gwynedd" in district_borough_unitary_region.gml — OS's
standard layer name for unitary authorities).

CLI: `lleolydd-cache derive-bounds --lad Gwynedd --output seed/...`.
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
    """Extract a named LAD polygon from the BoundaryLine GML, save it
    as a single-feature GeoJSON. Used to derive Gwynedd's bounds once.

    Returns metadata dict with the polygon's bounding box + area.
    """
    # The GML layer for unitary authorities is named
    # 'district_borough_unitary_region' in BoundaryLine GML.
    gml_paths = [
        p for p in files
        if p.name.endswith(".gml")
        and "district_borough_unitary_region" in p.name.lower()
    ]
    if not gml_paths:
        # Some BoundaryLine releases use slightly different layer names.
        # Fall back: any GML containing the LAD name as a feature.
        gml_paths = [p for p in files if p.suffix.lower() == ".gml"]
    if not gml_paths:
        raise RuntimeError(
            f"BoundaryLine: no GML files in extracted set: {files}"
        )

    # Use DuckDB spatial via ST_Read to filter for the named LAD.
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")

    # Try each candidate GML until we find one that has the LAD.
    for gml in gml_paths:
        try:
            # The NAME column carries the LAD name. Some BoundaryLine
            # releases use "Name", others "NAME"; ST_Read normalises
            # but case may vary — match case-insensitively.
            rows = conn.execute(
                f"""
                SELECT ST_AsGeoJSON(geom) AS geom_json,
                       ST_AsText(geom) AS geom_wkt,
                       ST_XMin(geom) AS x_min,
                       ST_YMin(geom) AS y_min,
                       ST_XMax(geom) AS x_max,
                       ST_YMax(geom) AS y_max,
                       ST_Area(geom) AS area_m2
                FROM ST_Read(?)
                WHERE NAME ILIKE ?
                LIMIT 1
                """,
                [str(gml), lad_name],
            ).fetchone()
        except duckdb.Error:
            # This GML may not have a NAME column or may not be the
            # unitary-authority file. Try next.
            continue
        if rows is not None:
            geom_json, geom_wkt, xmin, ymin, xmax, ymax, area_m2 = rows
            feature = {
                "type": "Feature",
                "properties": {
                    "name": lad_name,
                    "source": "OS BoundaryLine (GML)",
                    "extracted_from": str(gml),
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
                "source_file": str(gml),
                "source_file_sha256": sha256_file(gml),
                "geojson_path": str(output_geojson),
                "bbox_bng": [xmin, ymin, xmax, ymax],
                "area_m2": area_m2,
            }

    raise RuntimeError(
        f"BoundaryLine: could not find LAD {lad_name!r} in any GML in "
        f"{[str(p) for p in gml_paths]}"
    )
