"""
Local wrapper for the constitution drift check (scripts/constitution_drift.py,
brief §6). The authoritative run is the constitution-drift CI workflow, which
checks the constitution out at the pinned tag; this test runs the same logic
when a constitution tree is available locally, and SKIPS otherwise so the
normal suite is unaffected.

Point it at a clone with:
  AWEN_CONSTITUTION_DIR=~/Developer/awen-porth/constitution pytest tests/schema/test_constitution_drift.py
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "constitution_drift.py"

# candidate constitution trees: env override, then a couple of usual siblings.
_CANDIDATES = [
    os.environ.get("AWEN_CONSTITUTION_DIR"),
    str(Path.home() / "Developer" / "awen-porth" / "constitution"),
    str(_REPO.parent / "awen-constitution"),
    str(_REPO / "_constitution"),
]


def _constitution_dir() -> Path | None:
    for cand in _CANDIDATES:
        if cand and (Path(cand) / "VERSION").exists():
            return Path(cand)
    return None


def _load_module():
    spec = importlib.util.spec_from_file_location("constitution_drift", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONST_DIR = _constitution_dir()

pytestmark = [
    pytest.mark.skipif(CONST_DIR is None, reason="no awen-constitution tree available"),
    pytest.mark.skipif(
        importlib.util.find_spec("jsonschema") is None,
        reason="jsonschema not installed (round-trip layer)",
    ),
]


def test_no_model_drift():
    mod = _load_module()
    const = mod.load_constitution(CONST_DIR)
    findings = mod.model_diff(const["schemas"])
    findings += mod.pairing_diff(const["root"], "0.2.0")
    assert findings == [], "model drift:\n" + "\n".join(findings)


def test_no_roundtrip_drift():
    mod = _load_module()
    const = mod.load_constitution(CONST_DIR)
    fixtures_path = _REPO / "tests" / "schema" / "fixtures" / "constitution_roundtrip.json"
    findings = mod.roundtrip_diff(const["schemas"], mod.load_fixtures(fixtures_path))
    assert findings == [], "round-trip drift:\n" + "\n".join(findings)
