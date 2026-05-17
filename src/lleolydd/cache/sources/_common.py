"""
Shared download / hashing / OS Data Hub helpers for the source modules.

The OS Data Hub OpenData products all expose the same Downloads API
shape (`/downloads/v1/products/<id>/downloads` → list[file]) and serve
files without an API key. Each per-source module pins its product id +
which files within that product it wants for Gwynedd; the heavy lifting
of "fetch the listing, GET the file, verify md5, cache locally" lives
here.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import requests

OS_DOWNLOADS_API = "https://api.os.uk/downloads/v1/products"

# Default HTTP timeout — long enough for the slow Pi-side downloads,
# short enough that a hung host doesn't stall the build forever.
DEFAULT_TIMEOUT = 60.0

# Default User-Agent so OS sees identifiable client traffic. Helps if
# they ever want to talk to us about rate-limit issues.
USER_AGENT = "lleolydd/0.1 (+https://github.com/arloesidolgellau/town-dataset)"


def list_product_downloads(product_id: str) -> list[dict[str, Any]]:
    """GET /downloads/v1/products/<id>/downloads. Returns the raw list
    of file entries (keys: url, fileName, format, area, size, md5)."""
    url = f"{OS_DOWNLOADS_API}/{product_id}/downloads"
    r = requests.get(url, timeout=DEFAULT_TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.json()


def md5_file(path: Path, chunk: int = 1 << 20) -> str:
    """SHA-256 would be tidier but OS publishes md5 hashes for these files."""
    h = hashlib.md5()  # noqa: S324 — matching the upstream-published checksum
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def download_file(
    url: str,
    target: Path,
    expected_md5: str | None = None,
    expected_size: int | None = None,
    force: bool = False,
    progress: bool = True,
) -> Path:
    """Download `url` to `target`. Idempotent: skips if a file with
    matching size + md5 already exists (unless force=True).

    Streams the download in chunks, writes to a `.partial` sibling, then
    renames into place. A mid-download interruption leaves the .partial
    file but does NOT clobber the final target.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        if expected_size is not None and target.stat().st_size != expected_size:
            # Size mismatch — re-download.
            pass
        elif expected_md5 is not None and md5_file(target) != expected_md5:
            # Hash mismatch — re-download.
            pass
        else:
            return target

    partial = target.with_suffix(target.suffix + ".partial")
    with requests.get(
        url,
        stream=True,
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        written = 0
        with partial.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if progress and total > 0:
                    pct = 100 * written / total
                    sys.stderr.write(
                        f"\r  {target.name}: {written/1e6:7.1f} / "
                        f"{total/1e6:7.1f} MB  ({pct:5.1f}%)"
                    )
                    sys.stderr.flush()
        if progress and total > 0:
            sys.stderr.write("\n")
            sys.stderr.flush()

    # Verify before atomic-rename into place.
    if expected_size is not None and partial.stat().st_size != expected_size:
        raise OSError(
            f"download of {url}: size mismatch — got "
            f"{partial.stat().st_size}, expected {expected_size}"
        )
    if expected_md5 is not None:
        actual = md5_file(partial)
        if actual != expected_md5:
            raise OSError(
                f"download of {url}: md5 mismatch — got {actual}, "
                f"expected {expected_md5}"
            )

    os.replace(partial, target)
    return target


def sniff_csv_columns(csv_path: Path) -> tuple[str, ...]:
    """Read the header row of a CSV-shaped source file and return its
    column names as a tuple of strings.

    Handles UTF-8 BOM transparently (`encoding="utf-8-sig"`) — both
    OS Open TOID's 2026-04 and OS Open Linked Identifiers' 2026-03
    releases ship CSVs with a BOM, which would otherwise show up as
    a `\\ufeff` prefix on the first column name.

    Used by the schema-sniff CLI to detect column drift cheaply
    (reads ~1 KB regardless of file size).
    """
    import csv as _csv  # noqa: PLC0415 — lazy
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = _csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as e:
            raise RuntimeError(
                f"sniff_csv_columns: empty file {csv_path}"
            ) from e
    return tuple(c.strip() for c in header)


def sniff_gml_columns(gml_path: Path) -> tuple[str, ...]:
    """Return the columns OGR/ST_Read exposes for a GML file, as
    detected by DuckDB spatial's first-row scan. Heavier than
    sniff_csv_columns (parses the GML header / generates a `.gfs`
    sidecar if absent) but still cheap relative to a full load."""
    import duckdb as _duckdb  # noqa: PLC0415 — lazy
    conn = _duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    try:
        rows = conn.execute(
            "DESCRIBE SELECT * FROM ST_Read(?) LIMIT 0",
            [str(gml_path)],
        ).fetchall()
    except _duckdb.Error as e:
        raise RuntimeError(
            f"sniff_gml_columns: ST_Read failed on {gml_path}: {e}"
        ) from e
    return tuple(r[0] for r in rows)


def diff_columns(
    expected: tuple[str, ...],
    actual: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Compare expected vs actual column tuples. Returns (added, removed)
    where added = in actual but not expected, removed = in expected but
    not actual. Order of returned tuples matches the source order
    (preserves the human-readable diff)."""
    expected_set = set(expected)
    actual_set = set(actual)
    added = tuple(c for c in actual if c not in expected_set)
    removed = tuple(c for c in expected if c not in actual_set)
    return added, removed


def unzip(zip_path: Path, target_dir: Path, force: bool = False) -> list[Path]:
    """Extract a zip into target_dir. Returns the list of extracted
    file paths. Idempotent: if the expected outputs already exist (by
    name match) and force is False, skip extraction."""
    import zipfile  # noqa: PLC0415 — lazy import

    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        outputs = [target_dir / n for n in names if not n.endswith("/")]
        if not force and all(p.exists() and p.stat().st_size > 0 for p in outputs):
            return outputs
        zf.extractall(target_dir)
    return outputs
