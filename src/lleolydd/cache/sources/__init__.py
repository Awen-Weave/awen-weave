"""
OGL data sources — one module per upstream product.

Each source module exposes:

  PRODUCT_NAME : str
      Stable identifier (e.g. "os-open-uprn"). Goes into the snapshot
      manifest and the snapshot subdirectory name.

  def list_remote_files() -> list[dict]
      Query the upstream API (or hardcoded listing for non-API sources)
      and return per-file metadata: {url, fileName, format, area,
      size_bytes, md5_or_sha256?}.

  def download(
      target_dir: pathlib.Path,
      area_bounds_wkt: str | None = None,
      release: str | None = None,
      force: bool = False,
  ) -> list[pathlib.Path]
      Download the file(s) needed for this build. Returns the list of
      local paths. Idempotent against existing files (skips if size +
      hash match unless force=True). area_bounds_wkt is informational —
      the OS Data Hub doesn't honour bbox queries on OpenData products,
      so all downloads are national / 100km-tile, and the orchestrator
      handles clipping after load.

  def load_into_duckdb(
      conn: duckdb.DuckDBPyConnection,
      file_paths: list[pathlib.Path],
      area_bounds_wkt: str,
      snapshot_id: str,
  ) -> dict
      Load the source's data into the cache database, CLIPPED to
      area_bounds_wkt. Returns a small stats dict {rows_in,
      rows_in_area, columns} that build.py logs and feeds into the
      snapshot manifest.

The split keeps each source's quirks (file format, column names,
re-projection requirements) isolated from the orchestrator. Adding a
new source (Defra LIDAR, aerial imagery, etc.) means adding one new
module here.
"""
from __future__ import annotations
