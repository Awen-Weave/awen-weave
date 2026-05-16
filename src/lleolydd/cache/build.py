"""
Cache build orchestrator.

Sequences the work of a Lleolydd cache build:

  1. Resolve paths (data-dir → seed/lleolydd/snapshots/<release>/).
  2. Load the area-bounds polygon (seed/lleolydd/area-bounds.geojson).
  3. Open cache.duckdb, apply schema if absent, install spatial extn.
  4. For each enabled source:
     a. download() → list[Path]
     b. load_into_duckdb(conn, files, area_bounds_wkt, snapshot_id)
     c. record stats in the manifest
  5. Run bands.classify_bands(conn, snapshot_id) — populates uprn.band.
  6. Write the manifest to <snapshot_dir>/manifest.json.
  7. INSERT INTO snapshot DuckDB table (so SQL queries can find it).

Source ordering: uprn first, then toid + inspire + zoomstack +
boundary-line in any order, then linked_ids LAST. LIDS load joins
against the uprn table to filter to Gwynedd UPRNs, so uprn must
already be loaded.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from .snapshot import open_manifest
from .sources import (
    inspire,
    open_linked_ids,
    open_toid,
    open_uprn,
    zoomstack,
)


# Default base under data-dir for everything Lleolydd produces.
SEED_SUBDIR = Path("seed") / "lleolydd"

# Source registry — name → module. Build phases per source go through
# the same `download` + `load_into_duckdb` contract. Order matters at
# load time (see module docstring) — the orchestrator sorts.
ALL_SOURCES: dict[str, Any] = {
    "open-uprn": open_uprn,
    "open-toid": open_toid,
    "inspire": inspire,
    "zoomstack": zoomstack,
    "open-linked-ids": open_linked_ids,
}

# Load order — uprn first (other sources may reference it), linked-ids
# last (filters against the loaded uprn set).
LOAD_ORDER: list[str] = [
    "open-uprn",
    "open-toid",
    "inspire",
    "zoomstack",
    "open-linked-ids",
]


CACHE_DDL = """
-- Lleolydd cache schema.
--
-- Separate from craidd.duckdb; this is the OGL-derived data layer.
-- Cross-references to Craidd happen at Phase 2 viewer time (read-only
-- joins against the Craidd Read API).
--
-- All polygon / point columns use EPSG:27700 (British National Grid)
-- to match OS Open data's native CRS. Lat/lon (WGS84) is kept on the
-- uprn table for map-rendering convenience but isn't used by band
-- computation.

INSTALL spatial;
LOAD spatial;

CREATE TABLE IF NOT EXISTS uprn (
    uprn BIGINT PRIMARY KEY,
    point_geom GEOMETRY,
    snapped_toid VARCHAR,
    snap_band VARCHAR
        CHECK (snap_band IS NULL OR snap_band IN
            ('verified','auto-snapped','unsnapped','contested','non-postal')),
    snap_confidence DOUBLE,
    latitude DOUBLE,
    longitude DOUBLE,
    snapshot_id VARCHAR
);

CREATE TABLE IF NOT EXISTS toid (
    toid VARCHAR PRIMARY KEY,
    polygon_geom GEOMETRY,
    feature_type VARCHAR,
    description_group VARCHAR,
    description_term VARCHAR,
    centroid_geom GEOMETRY,
    snapshot_id VARCHAR
);

CREATE TABLE IF NOT EXISTS linked_id (
    uprn BIGINT,
    toid VARCHAR,
    correlation_method VARCHAR,
    snapshot_id VARCHAR,
    PRIMARY KEY (uprn, toid)
);

CREATE TABLE IF NOT EXISTS inspire_parcel (
    inspire_id VARCHAR PRIMARY KEY,
    polygon_geom GEOMETRY,
    snapshot_id VARCHAR
);

CREATE TABLE IF NOT EXISTS zoomstack_manifest (
    snapshot_id VARCHAR PRIMARY KEY,
    file_path VARCHAR NOT NULL,
    file_sha256 VARCHAR NOT NULL,
    size_bytes BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot (
    snapshot_id VARCHAR PRIMARY KEY,
    release VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    area_bounds_path VARCHAR,
    area_bounds_sha256 VARCHAR,
    sources_json VARCHAR,
    band_stats_json VARCHAR
);
"""


@dataclass
class BuildPaths:
    data_dir: Path
    seed_dir: Path
    cache_db: Path
    snapshots_root: Path
    snapshot_dir: Path
    downloads_dir: Path

    @classmethod
    def resolve(cls, data_dir: Path, release: str) -> "BuildPaths":
        seed = data_dir / SEED_SUBDIR
        snapshots = seed / "snapshots"
        snapshot = snapshots / f"lleolydd-cache-{release}"
        downloads = snapshot / "downloads"
        return cls(
            data_dir=data_dir,
            seed_dir=seed,
            cache_db=seed / "cache.duckdb",
            snapshots_root=snapshots,
            snapshot_dir=snapshot,
            downloads_dir=downloads,
        )


def _read_area_bounds_wkt(geojson_path: Path) -> str:
    """Read the area-bounds GeoJSON, return WKT in EPSG:27700.

    The geojson is expected to carry the Gwynedd boundary in BNG
    (matching how OS BoundaryLine encodes admin polygons). We parse it
    via DuckDB spatial (the same parser the source modules use) to
    avoid a hard geopandas dependency."""
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    rows = conn.execute(
        "SELECT ST_AsText(geom) FROM ST_Read(?)",
        [str(geojson_path)],
    ).fetchall()
    if not rows:
        raise RuntimeError(
            f"area-bounds: no features in {geojson_path}"
        )
    # Unify multi-feature inputs into a single polygon (rare for LAD
    # data but defensive).
    if len(rows) > 1:
        union = conn.execute(
            "SELECT ST_AsText(ST_Union_Agg(geom)) FROM ST_Read(?)",
            [str(geojson_path)],
        ).fetchone()[0]
        return union
    return rows[0][0]


def _release_default() -> str:
    """e.g. '2026-05'. Used when --release isn't passed."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def build(
    data_dir: Path,
    area_bounds: Path,
    *,
    release: str | None = None,
    sources: list[str] | None = None,
    force: bool = False,
    skip_download: bool = False,
    dry_run: bool = False,
    progress: bool = True,   # noqa: ARG001 — passed through if/when we wire it
) -> dict:
    """Run a full Lleolydd cache build.

    Returns a summary dict carrying snapshot_id, paths, per-source
    stats, and band counts. Suitable for CLI --json output.
    """
    release = release or _release_default()
    snapshot_id = f"lleolydd-cache-{release}"
    paths = BuildPaths.resolve(data_dir, release)

    enabled = list(sources) if sources else list(LOAD_ORDER)
    unknown = [s for s in enabled if s not in ALL_SOURCES]
    if unknown:
        raise RuntimeError(
            f"unknown source(s): {unknown}. Known: {sorted(ALL_SOURCES)}"
        )
    # Always run in dependency order, regardless of the order the
    # caller passed.
    enabled = [s for s in LOAD_ORDER if s in enabled]

    summary = {
        "snapshot_id": snapshot_id,
        "release": release,
        "data_dir": str(data_dir),
        "cache_db": str(paths.cache_db),
        "snapshot_dir": str(paths.snapshot_dir),
        "sources": enabled,
        "dry_run": dry_run,
        "skip_download": skip_download,
    }

    if dry_run:
        # Validate inputs without writing anything. Useful for CI.
        if not area_bounds.is_file():
            raise FileNotFoundError(f"area-bounds: {area_bounds}")
        area_bounds_wkt = _read_area_bounds_wkt(area_bounds)
        summary["area_bounds_wkt_length"] = len(area_bounds_wkt)
        summary["plan"] = "dry-run — paths + sources validated, no writes"
        return summary

    if paths.snapshot_dir.exists() and not force:
        raise RuntimeError(
            f"snapshot dir already exists: {paths.snapshot_dir} — pass "
            f"--force to overwrite or --release to a different label"
        )

    paths.seed_dir.mkdir(parents=True, exist_ok=True)
    paths.snapshot_dir.mkdir(parents=True, exist_ok=True)
    paths.downloads_dir.mkdir(parents=True, exist_ok=True)

    # --- Load area bounds.
    area_bounds_wkt = _read_area_bounds_wkt(area_bounds)
    manifest = open_manifest(snapshot_id, release, area_bounds)

    # --- Open / initialise the cache DB.
    conn = duckdb.connect(str(paths.cache_db))
    conn.execute(CACHE_DDL)

    # --- Download + load each source, in dependency order.
    per_source_summary = {}
    for name in enabled:
        module = ALL_SOURCES[name]
        module_name = getattr(module, "PRODUCT_NAME", name)
        product_id = getattr(module, "PRODUCT_ID", None)

        if skip_download:
            # Match files in the downloads dir against the source's
            # FILENAME_PATTERN — each source's pattern is specific
            # enough to avoid cross-source collisions (LIDS filenames
            # contain "UPRN", so a generic substring match on "uprn"
            # would falsely pick up the LIDS file when loading
            # OpenUPRN). Patterns are case-insensitive.
            pattern = getattr(module, "FILENAME_PATTERN", None)
            if pattern:
                pat_lower = pattern.lower()
                files = sorted(
                    f for f in paths.downloads_dir.iterdir()
                    if f.is_file() and pat_lower in f.name.lower()
                )
            else:
                # Fall back to the source name as a tag — last-resort
                # behaviour for sources without an explicit pattern.
                files = sorted(
                    f for f in paths.downloads_dir.iterdir()
                    if f.is_file() and name.replace("-", "") in f.name.lower()
                )
            if not files:
                raise RuntimeError(
                    f"--skip-download: no files matching pattern "
                    f"{pattern!r} for source {name!r} in "
                    f"{paths.downloads_dir}"
                )
        else:
            files = module.download(
                paths.downloads_dir,
                area_bounds_wkt=area_bounds_wkt,
                release=release,
                force=force,
            )

        load_stats = module.load_into_duckdb(
            conn, files, area_bounds_wkt, snapshot_id
        )
        per_source_summary[name] = load_stats
        manifest.add_source(
            name=module_name,
            product_id=product_id or "",
            files=files,
            load_stats=load_stats,
        )

    # --- Band classification.
    from .bands import classify_bands  # noqa: PLC0415 — lazy to avoid cycles
    band_stats = classify_bands(conn, snapshot_id)
    manifest.band_stats = band_stats.as_dict()
    per_source_summary["band_stats"] = manifest.band_stats

    # --- Write manifest + record snapshot row in DB.
    manifest_path = manifest.write(paths.snapshot_dir)
    conn.execute(
        """
        INSERT OR REPLACE INTO snapshot
            (snapshot_id, release, created_at, area_bounds_path,
             area_bounds_sha256, sources_json, band_stats_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_id,
            release,
            datetime.now(timezone.utc),
            str(area_bounds),
            manifest.area_bounds_sha256,
            json.dumps(manifest.sources),
            json.dumps(manifest.band_stats),
        ],
    )

    conn.close()

    summary["manifest_path"] = str(manifest_path)
    summary["per_source"] = per_source_summary
    summary["band_stats"] = manifest.band_stats
    return summary
