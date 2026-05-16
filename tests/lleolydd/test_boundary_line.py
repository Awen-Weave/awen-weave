"""
Tests for the OS BoundaryLine source module.

Exercise the INSPIRE-schema-targeted derive-bounds path:
  * happy path — find a LAD polygon in an INSPIRE-shaped GML and write
    a single-feature GeoJSON.
  * fail-loud when INSPIRE_AdministrativeUnit.gml is missing from the
    extracted file set (OS layout drift).
  * fail-loud when the LAD-name column is missing (OS schema drift).
  * fail-loud when the LAD name isn't in the file (typo, wrong region).

Background — pre-2026 OS BoundaryLine releases shipped per-tier GML
files (district_borough_unitary_region.gml etc.) with a NAME column;
that schema is no longer supported. The 2026-05 release ships a single
INSPIRE_AdministrativeUnit.gml with the `text` column. See the schema-
reference comment at the top of src/lleolydd/cache/sources/boundary_line.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Put src/ on the path so `from lleolydd...` resolves.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))


# Minimal INSPIRE-shaped GML. OGR detects the schema by scanning the
# XML; the `text` element becomes the `text` column and <ogr:geometry>
# becomes the `geometry` column.
_GML_INSPIRE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection
    xmlns:wfs="http://www.opengis.net/wfs"
    xmlns:gml="http://www.opengis.net/gml"
    xmlns:ogr="http://ogr.maptools.org/">
{features}
</wfs:FeatureCollection>
"""

_GML_FEATURE_TEMPLATE = """  <gml:featureMember>
    <ogr:AdministrativeUnit fid="{fid}">
      <ogr:geometry>
        <gml:Polygon srsName="EPSG:27700">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>{coords}</gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </ogr:geometry>
      <ogr:{name_col}>{name}</ogr:{name_col}>
    </ogr:AdministrativeUnit>
  </gml:featureMember>
"""


def _write_inspire_gml(
    path: Path,
    features: list[tuple[str, str]],
    name_col: str = "text",
) -> None:
    """Write a minimal INSPIRE-shaped GML at `path`.

    features: list of (name, coords_str) tuples — coords_str is the
              GML posList for the polygon ring.
    name_col: which XML element to use for the LAD name. Default is
              the current `text` column; tests pass `NAME` to simulate
              the legacy schema.
    """
    blocks = [
        _GML_FEATURE_TEMPLATE.format(
            fid=i + 1, coords=coords, name_col=name_col, name=name,
        )
        for i, (name, coords) in enumerate(features)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_GML_INSPIRE_TEMPLATE.format(features="".join(blocks)))


# A small Gwynedd-ish square in BNG, big enough to round-trip cleanly
_GWYNEDD_COORDS = (
    "270000 315000 280000 315000 280000 325000 270000 325000 270000 315000"
)


# --- happy path -----------------------------------------------------------

def test_extract_lad_polygon_writes_single_feature_geojson(tmp_path: Path):
    """Given a current-schema INSPIRE GML containing 'Gwynedd' in the
    `text` column, extract_lad_polygon writes a single-feature GeoJSON
    and returns metadata pointing at the source file."""
    from lleolydd.cache.sources import boundary_line as bl

    gml = tmp_path / "INSPIRE_AdministrativeUnit.gml"
    _write_inspire_gml(gml, [("Gwynedd", _GWYNEDD_COORDS)])
    out = tmp_path / "area-bounds.geojson"

    result = bl.extract_lad_polygon([gml], "Gwynedd", out)

    assert out.is_file()
    payload = json.loads(out.read_text())
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    feature = payload["features"][0]
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["name"] == "Gwynedd"
    assert feature["properties"]["source"] == "OS BoundaryLine (INSPIRE GML)"

    assert result["lad"] == "Gwynedd"
    assert result["source_file"] == str(gml)
    # bbox is in BNG and matches the synthetic square
    xmin, ymin, xmax, ymax = result["bbox_bng"]
    assert xmin == pytest.approx(270000)
    assert ymin == pytest.approx(315000)
    assert xmax == pytest.approx(280000)
    assert ymax == pytest.approx(325000)


def test_extract_lad_polygon_case_insensitive_name_match(tmp_path: Path):
    """Name matching is ILIKE — accept user-typed casing variations."""
    from lleolydd.cache.sources import boundary_line as bl

    gml = tmp_path / "INSPIRE_AdministrativeUnit.gml"
    _write_inspire_gml(gml, [("Gwynedd", _GWYNEDD_COORDS)])
    out = tmp_path / "area-bounds.geojson"

    result = bl.extract_lad_polygon([gml], "gwynedd", out)
    assert result["lad"] == "gwynedd"
    assert out.is_file()


# --- fail-loud error paths ------------------------------------------------

def test_extract_raises_when_inspire_file_missing(tmp_path: Path):
    """If INSPIRE_AdministrativeUnit.gml is not in the extracted set
    (OS BoundaryLine layout drift), surface a clear RuntimeError that
    points at the constant to update."""
    from lleolydd.cache.sources import boundary_line as bl

    # Extracted set has GML, but not the INSPIRE one we expect.
    other_gml = tmp_path / "district_borough_unitary_region.gml"
    other_gml.write_text("<wfs:FeatureCollection/>")
    out = tmp_path / "area-bounds.geojson"

    with pytest.raises(RuntimeError) as exc_info:
        bl.extract_lad_polygon([other_gml], "Gwynedd", out)

    msg = str(exc_info.value)
    assert "INSPIRE_AdministrativeUnit.gml" in msg
    assert "INSPIRE_GML_FILENAME" in msg
    assert "district_borough_unitary_region.gml" in msg
    assert not out.exists()


def test_extract_raises_when_extracted_set_is_empty(tmp_path: Path):
    """Empty file list — same error path as missing-file."""
    from lleolydd.cache.sources import boundary_line as bl

    out = tmp_path / "area-bounds.geojson"
    with pytest.raises(RuntimeError, match="INSPIRE_AdministrativeUnit"):
        bl.extract_lad_polygon([], "Gwynedd", out)


def test_extract_raises_when_text_column_missing(tmp_path: Path):
    """If the INSPIRE GML has a different schema (e.g. legacy NAME
    column instead of `text`), surface a clear RuntimeError that
    points at LAD_NAME_COLUMN."""
    from lleolydd.cache.sources import boundary_line as bl

    gml = tmp_path / "INSPIRE_AdministrativeUnit.gml"
    # Legacy-style: NAME column, no `text`
    _write_inspire_gml(gml, [("Gwynedd", _GWYNEDD_COORDS)], name_col="NAME")
    out = tmp_path / "area-bounds.geojson"

    with pytest.raises(RuntimeError) as exc_info:
        bl.extract_lad_polygon([gml], "Gwynedd", out)

    msg = str(exc_info.value)
    assert "text" in msg
    assert "LAD_NAME_COLUMN" in msg
    assert not out.exists()


def test_extract_raises_when_lad_name_not_found(tmp_path: Path):
    """If the column is there but no row matches the requested name,
    surface a typo-friendly RuntimeError with the DISTINCT-query hint."""
    from lleolydd.cache.sources import boundary_line as bl

    gml = tmp_path / "INSPIRE_AdministrativeUnit.gml"
    _write_inspire_gml(gml, [("Gwynedd", _GWYNEDD_COORDS)])
    out = tmp_path / "area-bounds.geojson"

    with pytest.raises(RuntimeError) as exc_info:
        bl.extract_lad_polygon([gml], "Powys", out)

    msg = str(exc_info.value)
    assert "Powys" in msg
    assert "INSPIRE_AdministrativeUnit.gml" in msg
    assert "DISTINCT" in msg
    assert not out.exists()
