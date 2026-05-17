"""
OS Open Zoomstack — vector basemap tiles for the whole of GB.

Per Huw's decision 2026-05-16, Phase 1 includes Zoomstack in the
cache rather than deferring to Phase 2. The MBTiles format is a SQLite
file containing pre-rendered vector tiles indexed by (zoom, x, y); we
DON'T clip it (the brief said clip, but MBTiles doesn't slice cleanly
into geographic subsets — tiles overlap area bounds, and partial tiles
are useless to a renderer). Instead, we copy the full MBTiles file
into the snapshot directory and record its hash + size in the manifest.

The cache.duckdb gets a `zoomstack_manifest` row pointing at the
MBTiles file. Phase 2's MapLibre viewer reads MBTiles directly via a
small static server — it doesn't query DuckDB for tiles.

Download size: 2.85 GB MBTiles. The 4.3 GB GeoPackage variant is for
GIS desktop use; we want MBTiles for the web viewer.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from ._common import (
    download_file,
    list_product_downloads,
    sha256_file,
)

PRODUCT_NAME = "os-open-zoomstack"
PRODUCT_ID = "OpenZoomstack"
DOWNLOAD_FORMAT = "Vector Tiles"  # MBTiles
FILENAME_PATTERN = "Zoomstack"


def list_remote_files() -> list[dict]:
    entries = list_product_downloads(PRODUCT_ID)
    return [e for e in entries if e.get("format") == DOWNLOAD_FORMAT]


def download(
    target_dir: Path,
    area_bounds_wkt: str | None = None,  # noqa: ARG001
    release: str | None = None,          # noqa: ARG001
    force: bool = False,
) -> list[Path]:
    """Download the MBTiles file directly (no zip wrapper — OS publishes
    Zoomstack as bare .mbtiles)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    entries = list_remote_files()
    if not entries:
        raise RuntimeError(
            "OS Open Zoomstack: no Vector Tiles entry from Downloads API"
        )
    entry = entries[0]
    target = target_dir / entry["fileName"]
    download_file(
        entry["url"],
        target,
        expected_md5=entry.get("md5"),
        expected_size=entry.get("size"),
        force=force,
    )
    return [target]


def load_into_duckdb(
    conn: duckdb.DuckDBPyConnection,
    file_paths: list[Path],
    area_bounds_wkt: str,    # noqa: ARG001 — MBTiles isn't clip-able
    area_bounds_bbox: tuple[float, float, float, float],  # noqa: ARG001
    snapshot_id: str,
) -> dict:
    """Record the Zoomstack MBTiles location + hash. Doesn't load tile
    bytes into DuckDB — MBTiles is queried directly by the viewer."""
    mbtiles = [p for p in file_paths if p.suffix.lower() == ".mbtiles"]
    if not mbtiles:
        raise RuntimeError(
            f"OS Open Zoomstack: no .mbtiles in downloaded files: "
            f"{file_paths}"
        )
    target = mbtiles[0]
    print(
        f"[zoomstack] hashing {target.name} "
        f"({target.stat().st_size / (1024**3):.2f} GB) …",
        flush=True,
    )
    file_hash = sha256_file(target)
    size = target.stat().st_size

    conn.execute(
        """
        INSERT INTO zoomstack_manifest
            (snapshot_id, file_path, file_sha256, size_bytes)
        VALUES (?, ?, ?, ?)
        """,
        [snapshot_id, str(target), file_hash, size],
    )
    print(
        f"[zoomstack]   recorded MBTiles manifest "
        f"({file_hash[:16]}…)",
        flush=True,
    )

    return {
        "rows_in": 1,
        "rows_in_area": 1,
        "source_file": str(target),
        "source_file_sha256": file_hash,
        "size_bytes": size,
        "columns": ["file_path", "file_sha256", "size_bytes"],
    }
