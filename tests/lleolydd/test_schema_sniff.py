"""
Tests for `lleolydd-cache schema-sniff`.

Synthetic fixtures only — no live OS / HMLR downloads. Each test stages
a fake-but-plausible source file under the orchestrator's snapshots/
layout, then invokes the CLI's `cmd_schema_sniff` directly to exercise
the file-finding + column-diff path.

What we pin here:
  - happy path (file matches expected) → status "ok", exit 0
  - column added (extra in actual) → status "drift", exit 1
  - column removed (missing in actual) → status "drift", exit 1
  - column renamed (one added + one removed) → status "drift", exit 1
  - file missing without --download-if-missing → status "missing", exit 2
  - --json output is parseable + has the right shape
  - --source NAME scopes correctly + rejects unknown names with exit 2
  - zoomstack is reported as "skip", not counted as drift or error
  - boundary_line's GML schema-sniff (covers the GML code path)
"""
from __future__ import annotations

import csv as _csv
import io
import json
import sys
from pathlib import Path

import pytest

# Put src/ on the path so `from lleolydd...` and the CLI import resolve.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))


# --- fixtures -------------------------------------------------------------


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _stage_uprn(downloads: Path, columns: list[str] | None = None) -> Path:
    """Stage a synthetic UPRN CSV under downloads/. Default columns
    match the EXPECTED_COLUMNS contract."""
    from lleolydd.cache.sources import open_uprn
    cols = columns if columns is not None else list(open_uprn.EXPECTED_COLUMNS)
    path = downloads / "osopenuprn_202605.csv"
    _write_csv(path, cols, [["1", "272030", "317900", "52.7", "-3.8"]])
    return path


def _make_data_dir(tmp_path: Path, release: str = "2026-05") -> Path:
    """Set up the data-dir + snapshots/<release>/downloads/ layout the
    sniff CLI expects."""
    data_dir = tmp_path / "data"
    (data_dir / "seed" / "lleolydd" / "snapshots" / f"lleolydd-cache-{release}"
     / "downloads").mkdir(parents=True, exist_ok=True)
    return data_dir


def _downloads_dir(data_dir: Path, release: str = "2026-05") -> Path:
    return (data_dir / "seed" / "lleolydd" / "snapshots"
            / f"lleolydd-cache-{release}" / "downloads")


def _args(**kwargs) -> object:
    """Mimic an argparse.Namespace with the fields cmd_schema_sniff reads."""
    import argparse
    ns = argparse.Namespace(
        data_dir=str(kwargs.pop("data_dir", "/srv/town-dataset")),
        source=kwargs.pop("source", None),
        download_if_missing=kwargs.pop("download_if_missing", False),
        as_json=kwargs.pop("as_json", False),
    )
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _capture_stdout(callable_, *args, **kwargs):
    """Run a CLI function and return (exit_code, stdout_text)."""
    buf = io.StringIO()
    saved = sys.stdout
    sys.stdout = buf
    try:
        rc = callable_(*args, **kwargs)
    finally:
        sys.stdout = saved
    return rc, buf.getvalue()


# --- happy path -----------------------------------------------------------


def test_sniff_ok_when_columns_match(tmp_path: Path):
    """All expected UPRN columns present → exit 0, 'ok' status."""
    from cli.lleolydd_cache import cmd_schema_sniff

    data_dir = _make_data_dir(tmp_path)
    _stage_uprn(_downloads_dir(data_dir))

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="open-uprn"),
    )
    assert rc == 0
    assert "[ok]" in out
    assert "open-uprn" in out


# --- drift paths ----------------------------------------------------------


def test_sniff_detects_added_column(tmp_path: Path):
    """An unexpected new column → exit 1, 'drift' status with the new
    column listed under 'added'."""
    from cli.lleolydd_cache import cmd_schema_sniff
    from lleolydd.cache.sources import open_uprn

    data_dir = _make_data_dir(tmp_path)
    extra = list(open_uprn.EXPECTED_COLUMNS) + ["NEW_OS_COLUMN"]
    _stage_uprn(_downloads_dir(data_dir), columns=extra)

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="open-uprn"),
    )
    assert rc == 1
    assert "[drift]" in out
    assert "NEW_OS_COLUMN" in out
    assert "added:" in out


def test_sniff_detects_removed_column(tmp_path: Path):
    """An expected column missing from the live file → exit 1, 'drift'
    with the missing column listed under 'removed'."""
    from cli.lleolydd_cache import cmd_schema_sniff
    from lleolydd.cache.sources import open_uprn

    data_dir = _make_data_dir(tmp_path)
    short = list(open_uprn.EXPECTED_COLUMNS)
    short.remove("LATITUDE")
    _stage_uprn(_downloads_dir(data_dir), columns=short)

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="open-uprn"),
    )
    assert rc == 1
    assert "[drift]" in out
    assert "LATITUDE" in out
    assert "removed:" in out


def test_sniff_detects_rename(tmp_path: Path):
    """Column renamed (e.g. LATITUDE → LAT) → exit 1 with both 'added'
    and 'removed' populated. Mirrors the real-world drifts this CLI
    was built to catch (CORRELATION_METHOD → CONFIDENCE, etc.)."""
    from cli.lleolydd_cache import cmd_schema_sniff
    from lleolydd.cache.sources import open_uprn

    data_dir = _make_data_dir(tmp_path)
    renamed = ["LAT" if c == "LATITUDE" else c for c in open_uprn.EXPECTED_COLUMNS]
    _stage_uprn(_downloads_dir(data_dir), columns=renamed)

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="open-uprn"),
    )
    assert rc == 1
    assert "[drift]" in out
    # Both directions of the diff are surfaced
    assert "LAT" in out
    assert "LATITUDE" in out


# --- missing / scope / format paths --------------------------------------


def test_sniff_reports_missing_without_download_flag(tmp_path: Path):
    """No live file on disk + no --download-if-missing → exit 2, 'missing'."""
    from cli.lleolydd_cache import cmd_schema_sniff

    data_dir = _make_data_dir(tmp_path)  # downloads dir exists but is empty

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="open-uprn"),
    )
    assert rc == 2
    assert "[miss]" in out
    assert "open-uprn" in out


def test_sniff_zoomstack_is_skipped_not_drift(tmp_path: Path):
    """zoomstack's SOURCE_KIND == 'mbtiles' → 'skip', neither drift nor
    error; doesn't push exit code past 0 even when other sources are ok."""
    from cli.lleolydd_cache import cmd_schema_sniff

    data_dir = _make_data_dir(tmp_path)

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="zoomstack"),
    )
    # zoomstack is the only source scoped — no drift, no errors,
    # only a skip. Exit code = 0.
    assert rc == 0
    assert "[skip]" in out
    assert "zoomstack" in out


def test_sniff_rejects_unknown_source(tmp_path: Path, capsys):
    """--source NAME with no matching module → exit 2, stderr names
    the known sources."""
    from cli.lleolydd_cache import cmd_schema_sniff

    data_dir = _make_data_dir(tmp_path)
    rc = cmd_schema_sniff(
        _args(data_dir=data_dir, source="not-a-real-source"),
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown source" in err
    assert "open-uprn" in err  # listed as a known name


def test_sniff_json_output_shape(tmp_path: Path):
    """--json emits valid JSON with sources / drift_count / exit_code
    keys; status strings match the text-mode tags."""
    from cli.lleolydd_cache import cmd_schema_sniff
    from lleolydd.cache.sources import open_uprn

    data_dir = _make_data_dir(tmp_path)
    extra = list(open_uprn.EXPECTED_COLUMNS) + ["NEW_COL"]
    _stage_uprn(_downloads_dir(data_dir), columns=extra)

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="open-uprn", as_json=True),
    )
    assert rc == 1
    payload = json.loads(out)
    assert payload["exit_code"] == 1
    assert payload["drift_count"] == 1
    assert len(payload["sources"]) == 1
    src = payload["sources"][0]
    assert src["name"] == "open-uprn"
    assert src["status"] == "drift"
    assert src["added"] == ["NEW_COL"]
    assert src["removed"] == []


# --- GML code path -------------------------------------------------------


def test_sniff_boundary_line_against_synthetic_inspire_gml(tmp_path: Path):
    """The GML sniff path uses DuckDB ST_Read. Stage a minimal INSPIRE-
    shaped GML (re-using test_boundary_line's synthetic-fixture pattern)
    and confirm schema-sniff reports 'ok' against boundary_line's
    EXPECTED_COLUMNS ('text', 'geometry')."""
    from cli.lleolydd_cache import cmd_schema_sniff

    data_dir = _make_data_dir(tmp_path)
    downloads = _downloads_dir(data_dir)
    gml = downloads / "INSPIRE_AdministrativeUnit.gml"
    gml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection
    xmlns:wfs="http://www.opengis.net/wfs"
    xmlns:gml="http://www.opengis.net/gml"
    xmlns:ogr="http://ogr.maptools.org/">
  <gml:featureMember>
    <ogr:AdministrativeUnit fid="1">
      <ogr:geometry>
        <gml:Polygon srsName="EPSG:27700">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>270000 315000 280000 315000 280000 325000 270000 325000 270000 315000</gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </ogr:geometry>
      <ogr:text>Gwynedd</ogr:text>
    </ogr:AdministrativeUnit>
  </gml:featureMember>
</wfs:FeatureCollection>
""",
    )

    rc, out = _capture_stdout(
        cmd_schema_sniff,
        _args(data_dir=data_dir, source="boundary-line"),
    )
    # boundary_line's EXPECTED_COLUMNS is ('text', 'geometry'); both are
    # in the synthetic GML — should be a clean 'ok'.
    assert rc == 0
    assert "[ok]" in out
    assert "boundary-line" in out
