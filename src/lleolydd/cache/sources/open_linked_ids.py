"""
OS Open Linked Identifiers (product id: `LIDS`) — relationship tables
between OS identifier types.

LIDS publishes 11 separate files, one per relationship type. For
Lleolydd's UPRN-to-building-TOID band logic we need exactly one:
`lids-<release>_csv_BLPU-UPRN-TopographicArea-TOID-5.zip`. This file
gives the canonical OS-Linked-Identifiers answer to "which TOID does
this UPRN belong to?" — the auth source we cross-check the spatial
auto-snap against.

The other 10 files (Street-USRN, RoadLink-TOID variations, etc.) are
relevant to USRN / road work but not to UPRN-to-building verification.
Skipping them keeps the download budget down by ~3 GB.
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

PRODUCT_NAME = "os-open-linked-identifiers"
PRODUCT_ID = "LIDS"
DOWNLOAD_FORMAT = "CSV"
# Matches lids-<YYYY-MM>_csv_BLPU-UPRN-TopographicArea-TOID-5.{zip,csv}
FILENAME_PATTERN = "lids-"

# Substring match for the file we want. OS releases bump the date
# prefix (e.g. lids-2026-03_csv_...) so we match on the constant suffix
# only — "BLPU-UPRN-TopographicArea-TOID-5".
TARGET_FILE_SUBSTRING = "BLPU-UPRN-TopographicArea-TOID-5"


def list_remote_files() -> list[dict]:
    """Return only the BLPU-UPRN-TopographicArea-TOID entry."""
    entries = list_product_downloads(PRODUCT_ID)
    return [
        e for e in entries
        if e.get("format") == DOWNLOAD_FORMAT
        and TARGET_FILE_SUBSTRING in e.get("fileName", "")
    ]


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
            f"OS Open Linked Identifiers: no file matching "
            f"{TARGET_FILE_SUBSTRING!r} returned by Downloads API"
        )
    if len(entries) > 1:
        raise RuntimeError(
            f"OS Open Linked Identifiers: multiple files match "
            f"{TARGET_FILE_SUBSTRING!r}: "
            f"{[e['fileName'] for e in entries]}"
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
    area_bounds_wkt: str,    # noqa: ARG001
    area_bounds_bbox: tuple[float, float, float, float],  # noqa: ARG001
    snapshot_id: str,
) -> dict:
    """Load LIDS BLPU-UPRN-TopographicArea-TOID into the `linked_id`
    table. Filtering happens via the `uprn` table — we only insert
    rows whose UPRN is already in the Gwynedd-clipped UPRN table, so
    `uprn.load_into_duckdb` must run BEFORE this. The build orchestrator
    enforces that ordering.

    Per OS docs, the CSV has columns:
      IDENTIFIER_1   the source identifier (BLPU UPRN)
      IDENTIFIER_1_TYPE  always "BLPU UPRN"
      IDENTIFIER_2   the target identifier (TopographicArea TOID)
      IDENTIFIER_2_TYPE  always "TopographicArea TOID"
      VERSION_DATE   when the linkage was published
      CORRELATION_METHOD  internal OS confidence indicator

    For the cache we keep uprn + toid + correlation_method.
    """
    csv_paths = [p for p in file_paths if p.suffix.lower() == ".csv"]
    if not csv_paths:
        raise RuntimeError(
            f"OS Open Linked Identifiers: no CSV in extracted files: "
            f"{file_paths}"
        )
    csv_path = csv_paths[0]

    print(
        f"[open_linked_ids] counting rows in {csv_path.name} …",
        flush=True,
    )
    total_in = conn.execute(
        "SELECT COUNT(*) FROM read_csv_auto(?, header=true)",
        [str(csv_path)],
    ).fetchone()[0]
    print(
        f"[open_linked_ids]   {total_in:,} BLPU-UPRN-TOID links; "
        f"filtering to UPRNs already in cache …",
        flush=True,
    )

    # INSERT … WHERE uprn IN (SELECT uprn FROM uprn) is the area-clip.
    # The Gwynedd `uprn` table is small (~50k rows), so DuckDB hashes
    # it into a build-side and probes per LIDS row. PK is (uprn, toid)
    # — ON CONFLICT DO NOTHING tolerates any exact-duplicate rows OS
    # might emit. Subquery alias avoids the binder error described in
    # open_uprn.py (DuckDB case-insensitive column refs).
    conn.execute(
        """
        INSERT INTO linked_id (uprn, toid, correlation_method, snapshot_id)
        SELECT
            s.uprn,
            s.toid,
            s.correlation_method,
            ? AS snapshot_id
        FROM (
            SELECT
                CAST(src."IDENTIFIER_1" AS BIGINT) AS uprn,
                CAST(src."IDENTIFIER_2" AS VARCHAR) AS toid,
                CAST(src."CORRELATION_METHOD" AS VARCHAR) AS correlation_method
            FROM read_csv_auto(?, header=true) AS src
        ) AS s
        WHERE s.uprn IN (SELECT uprn FROM uprn)
        ON CONFLICT (uprn, toid) DO NOTHING
        """,
        [snapshot_id, str(csv_path)],
    )

    rows_in_area = conn.execute(
        "SELECT COUNT(*) FROM linked_id"
    ).fetchone()[0]
    print(
        f"[open_linked_ids]   {rows_in_area:,} links for Gwynedd UPRNs",
        flush=True,
    )

    return {
        "rows_in": total_in,
        "rows_in_area": rows_in_area,
        "source_file": str(csv_path),
        "source_file_sha256": sha256_file(csv_path),
        "columns": ["uprn", "toid", "correlation_method"],
    }
