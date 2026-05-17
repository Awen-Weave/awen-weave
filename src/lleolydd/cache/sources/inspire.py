"""
INSPIRE Index Polygons — HM Land Registry's freehold-parcel boundaries.

NOT on the OS Data Hub — this is an HMLR product, published monthly at
https://use-land-property-data.service.gov.uk/datasets/inspire. The
download surface is one ZIP per local authority district, e.g.:
  https://use-land-property-data.service.gov.uk/datasets/inspire/download/Gwynedd.zip

Each ZIP contains a GML file (`Land_Registry_Cadastral_Parcels.gml`)
with feature INSPIREID + GEOMETRY polygons in EPSG:27700 (BNG).

For Phase 1 we download just the Gwynedd LAD zip (~30-60 MB), unpack
the GML, and load via DuckDB's spatial ST_Read. The HMLR data is
already LAD-scoped so the polygon clip is a belt-and-braces guard
against edge mismatches with the OS BoundaryLine Gwynedd polygon; the
bbox prefilter keeps that guard cheap.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from ._common import (
    download_file,
    sha256_file,
    unzip,
)

PRODUCT_NAME = "inspire-gwynedd"
# HMLR's GML file is Land_Registry_Cadastral_Parcels.gml inside the LAD
# zip. The zip itself uses the LAD name (Gwynedd.zip). Match either.
FILENAME_PATTERN = "Cadastral_Parcels"

# schema-sniff contract — see src/cli/lleolydd_cache.py schema-sniff
# subcommand and _common.sniff_columns. The loader uses INSPIREID
# (the parcel identifier) and geom (the polygon, exposed by OGR as
# `geom` when reading INSPIRE GML); pin those two.
SOURCE_KIND = "gml"
EXPECTED_COLUMNS: tuple[str, ...] = ("INSPIREID", "geom")

# Per HMLR's per-LAD download convention. The exact filename casing
# matches the LAD's official spelling. If a future build wants a
# different LAD (e.g. Anglesey overlap), this is the only line to edit.
HMLR_INSPIRE_LAD = "Gwynedd"
HMLR_INSPIRE_URL = (
    f"https://use-land-property-data.service.gov.uk/datasets/inspire/"
    f"download/{HMLR_INSPIRE_LAD}.zip"
)


def list_remote_files() -> list[dict]:
    """Synthesise a Downloads-API-shaped entry so the orchestrator can
    treat HMLR uniformly with the OS sources. HMLR doesn't publish a
    JSON listing; we hard-code the URL pattern."""
    return [{
        "fileName": f"{HMLR_INSPIRE_LAD}.zip",
        "format": "GML",
        "area": HMLR_INSPIRE_LAD,
        "url": HMLR_INSPIRE_URL,
        # No size / md5 in advance; HMLR doesn't publish them.
        "size": None,
        "md5": None,
    }]


def download(
    target_dir: Path,
    area_bounds_wkt: str | None = None,  # noqa: ARG001
    release: str | None = None,          # noqa: ARG001
    force: bool = False,
) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    entry = list_remote_files()[0]
    zip_path = target_dir / entry["fileName"]
    download_file(entry["url"], zip_path, force=force)
    return unzip(zip_path, target_dir, force=force)


def load_into_duckdb(
    conn: duckdb.DuckDBPyConnection,
    file_paths: list[Path],
    area_bounds_wkt: str,
    area_bounds_bbox: tuple[float, float, float, float],
    snapshot_id: str,
) -> dict:
    """Load Gwynedd INSPIRE parcels into the `inspire_parcel` table.

    The HMLR GML is already LAD-scoped to Gwynedd; in principle no
    further clipping is needed. We still ST_Intersects against
    area_bounds_wkt as a belt-and-braces because:
      - The Gwynedd LAD boundary in HMLR data may differ slightly from
        the OS BoundaryLine Gwynedd polygon (different vintages, +/-
        edge parcels).
      - Future builds may use a tighter bounding polygon (e.g.
        Dolgellau community-level for an extreme zoom).
    Bbox-overlap on the parcel geom's MBR runs first as a cheap
    prefilter — for the LAD-scoped HMLR file almost every parcel
    passes, but the constant is cheap and keeps behaviour uniform
    with the other spatial loaders.
    """
    gml_paths = [p for p in file_paths if p.suffix.lower() == ".gml"]
    if not gml_paths:
        raise RuntimeError(
            f"INSPIRE: no GML in extracted files: {file_paths}"
        )
    gml_path = gml_paths[0]
    xmin, ymin, xmax, ymax = area_bounds_bbox

    # DuckDB spatial's ST_Read reads GML via GDAL/OGR. The layer name
    # varies by HMLR release; we use the first layer.
    # Column names per HMLR docs: INSPIREID, LABEL, NATIONALCADASTRAL-
    # REFERENCE, VALIDFROM, BEGINLIFESPANVERSION.
    print(
        f"[inspire] counting parcels in {gml_path.name} …",
        flush=True,
    )
    rows_in = conn.execute(
        "SELECT COUNT(*) FROM ST_Read(?)", [str(gml_path)]
    ).fetchone()[0]
    print(
        f"[inspire]   {rows_in:,} parcels in source; "
        f"clipping to Gwynedd bbox + polygon …",
        flush=True,
    )

    conn.execute(
        f"""
        INSERT INTO inspire_parcel (inspire_id, polygon_geom, snapshot_id)
        SELECT
            CAST(INSPIREID AS VARCHAR) AS inspire_id,
            geom AS polygon_geom,
            ? AS snapshot_id
        FROM ST_Read(?)
        WHERE ST_XMax(geom) >= ?
          AND ST_XMin(geom) <= ?
          AND ST_YMax(geom) >= ?
          AND ST_YMin(geom) <= ?
          AND ST_Intersects(
              geom,
              ST_GeomFromText('{area_bounds_wkt}')
          )
        ON CONFLICT (inspire_id) DO NOTHING
        """,
        [snapshot_id, str(gml_path), xmin, xmax, ymin, ymax],
    )

    rows_in_area = conn.execute(
        "SELECT COUNT(*) FROM inspire_parcel"
    ).fetchone()[0]
    print(
        f"[inspire]   {rows_in_area:,} parcels in Gwynedd "
        f"(of {rows_in:,} in source)",
        flush=True,
    )

    return {
        "rows_in": rows_in,
        "rows_in_area": rows_in_area,
        "source_file": str(gml_path),
        "source_file_sha256": sha256_file(gml_path),
        "columns": ["inspire_id", "polygon_geom"],
    }
