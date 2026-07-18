"""
Smoke tests for src/cli/craidd_init.py.

Runs the CLI's main() against a temp data-dir, asserts the two DuckDB
files appear and the predicate registry is seeded with the expected
number of rows. Idempotence-against-empty + refuse-against-non-empty
behaviours are documented (cli-design.md §4.1) and exercised here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def craidd_init():
    """Import the CLI's main() — pytest.ini adds src/ to pythonpath."""
    # Import inside fixture so test collection doesn't fail if optional
    # deps are missing in some env (they're not, but the pattern is safe).
    from cli import craidd_init as mod  # type: ignore[import-not-found]
    return mod.main


def test_init_creates_both_databases(tmp_path: Path, craidd_init, capsys):
    code = craidd_init(["--data-dir", str(tmp_path), "--actor", "test"])
    assert code == 0, capsys.readouterr().err
    assert (tmp_path / "craidd.duckdb").is_file()
    assert (tmp_path / "prawf.duckdb").is_file()


def test_init_seeds_predicate_registry(tmp_path: Path, craidd_init, capsys):
    code = craidd_init(["--data-dir", str(tmp_path), "--actor", "test"])
    assert code == 0, capsys.readouterr().err

    conn = duckdb.connect(str(tmp_path / "craidd.duckdb"), read_only=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM predicate").fetchone()[0]
    finally:
        conn.close()
    # v0.1-schema.md §3.5 enumerates 58 predicates plus §10 item 7's two
    # additions (verified_building_toid, location_verification_status) = 60,
    # plus AWE-004's alc_grade (the first national-layer `area` predicate) = 61.
    # Same count the schema-layer test pins. The CLI must agree with the registry.
    assert count == 61


def test_init_refuses_non_empty_db(tmp_path: Path, craidd_init, capsys):
    """Second invocation on the same data-dir must refuse, exit code 1."""
    first = craidd_init(["--data-dir", str(tmp_path), "--actor", "test"])
    assert first == 0
    capsys.readouterr()  # drain
    second = craidd_init(["--data-dir", str(tmp_path), "--actor", "test"])
    assert second == 1


def test_init_dry_run_creates_nothing(tmp_path: Path, craidd_init, capsys):
    code = craidd_init([
        "--data-dir", str(tmp_path), "--actor", "test", "--dry-run",
    ])
    assert code == 0
    # Files should NOT exist after dry-run
    assert not (tmp_path / "craidd.duckdb").exists()
    assert not (tmp_path / "prawf.duckdb").exists()


def test_init_json_output_is_parseable(tmp_path: Path, craidd_init, capsys):
    code = craidd_init([
        "--data-dir", str(tmp_path), "--actor", "test", "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert isinstance(payload, dict)
