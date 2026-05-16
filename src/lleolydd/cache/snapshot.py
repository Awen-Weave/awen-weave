"""
Snapshot manifest writer.

Each cache build produces a manifest at:
  <data-dir>/seed/lleolydd/snapshots/<release>/manifest.json

The manifest records what data went into this build — per-source file
paths, sizes, sha256s, source URLs — so a curator verification today
is reproducible against the exact OGL data state it was made against
even after OS pushes a new release.

The cache.duckdb itself carries a `snapshot` table that mirrors the
JSON manifest, so `lleolydd-cache snapshot show <release>` can query
either source (preferring the DB for speed; falling back to the JSON
file if the DB is stale).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SnapshotManifest:
    """In-memory accumulator. build.py creates one of these at the
    start of a build, appends per-source entries as each source loads,
    then write() at the end."""
    snapshot_id: str
    release: str
    area_bounds_path: Path
    area_bounds_sha256: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    sources: list[dict[str, Any]] = field(default_factory=list)
    band_stats: dict[str, int] | None = None

    def add_source(
        self,
        name: str,
        product_id: str,
        files: list[Path],
        load_stats: dict[str, Any],
    ) -> None:
        """Record one source's load. files = the actual downloaded /
        extracted files (post-clip); load_stats = whatever the source's
        load_into_duckdb() returned."""
        self.sources.append({
            "name": name,
            "product_id": product_id,
            "downloaded_at": self.created_at,
            "file_paths": [str(p) for p in files],
            "file_count": len(files),
            "load_stats": load_stats,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "release": self.release,
            "created_at": self.created_at,
            "area_bounds_path": str(self.area_bounds_path),
            "area_bounds_sha256": self.area_bounds_sha256,
            "sources": list(self.sources),
            "band_stats": self.band_stats,
        }

    def write(self, snapshot_dir: Path) -> Path:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / "manifest.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def open_manifest(
    snapshot_id: str,
    release: str,
    area_bounds_path: Path,
) -> SnapshotManifest:
    """Construct a fresh manifest. Hashes the area-bounds geojson at
    open-time so the boundary version used for the build is recorded."""
    return SnapshotManifest(
        snapshot_id=snapshot_id,
        release=release,
        area_bounds_path=area_bounds_path,
        area_bounds_sha256=_sha256_path(area_bounds_path),
    )


def load_manifest(snapshot_dir: Path) -> dict[str, Any]:
    """Read an existing manifest.json back. Used by
    `lleolydd-cache snapshot show / diff`."""
    return json.loads((snapshot_dir / "manifest.json").read_text())


def list_snapshots(snapshots_root: Path) -> list[str]:
    """Returns the sorted list of release directories under
    snapshots/."""
    if not snapshots_root.is_dir():
        return []
    return sorted(
        d.name for d in snapshots_root.iterdir()
        if d.is_dir() and (d / "manifest.json").is_file()
    )
