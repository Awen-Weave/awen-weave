"""
Smoke tests for src/cli/craidd_propose.py.

The CLI assembles a proposal from flags or a file, validates it against
the schema layer (validate_proposal), and writes a JSON file into
<data-dir>/proposals/. Tests run main() in-process against a temp dir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def craidd_propose():
    from cli import craidd_propose as mod  # type: ignore[import-not-found]
    return mod.main


def test_propose_from_flags_writes_proposal_file(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "floor_area_m2",
        "--value", "142.6",
        "--source-id", "TDS-DOL-SRC-DOL-ENERGY-2026",
        "--confidence", "medium",
        "--note", "smoke test",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("*.json"))
    assert len(proposals) == 1
    payload = json.loads(proposals[0].read_text())
    assert payload["subject"] == "TDS-DOL-B-00001"
    assert payload["predicate"] == "floor_area_m2"
    assert payload["value"] == 142.6
    assert payload["submitter"] == "test"


def test_propose_dry_run_writes_nothing(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "floor_area_m2",
        "--value", "142.6",
        "--source-id", "TDS-DOL-SRC-DOL-ENERGY-2026",
        "--confidence", "medium",
        "--dry-run",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    assert not (tmp_path / "proposals").exists() or not list(
        (tmp_path / "proposals").glob("*.json")
    )


def test_propose_invalid_predicate_exits_nonzero(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "not_a_real_predicate",
        "--value", "anything",
        "--source-id", "TDS-DOL-SRC-LOCAL",
        "--confidence", "medium",
        "--actor", "test",
    ])
    assert code == 1
    assert not (tmp_path / "proposals").exists() or not list(
        (tmp_path / "proposals").glob("*.json")
    )


def test_propose_from_file_round_trip(
    tmp_path: Path, craidd_propose, capsys,
):
    """A JSON file proposal should be loaded, restamped, validated, and
    written. The CLI overrides submitter and timestamp from the file with
    the --actor / current time."""
    src = tmp_path / "input.json"
    src.write_text(json.dumps({
        "subject": "TDS-DOL-B-00001",
        "predicate": "build_year",
        "value": 1890,
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "high",
    }))
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--from-file", str(src),
        "--actor", "test-curator",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("*.json"))
    assert len(proposals) == 1
    payload = json.loads(proposals[0].read_text())
    assert payload["predicate"] == "build_year"
    assert payload["value"] == 1890
    assert payload["submitter"] == "test-curator"


def test_propose_bilingual_value_via_flags(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "address",
        "--value-cy", "Stryd y Bont",
        "--value-en", "Bridge Street",
        "--source-id", "TDS-DOL-SRC-LOCAL",
        "--confidence", "high",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("*.json"))
    assert len(proposals) == 1
    payload = json.loads(proposals[0].read_text())
    assert payload["value"] == {"cy": "Stryd y Bont", "en": "Bridge Street"}
