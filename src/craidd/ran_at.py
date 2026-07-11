"""
src/craidd/ran_at.py — the canonical resolution order for a source's ran_at_utc.

`ran_at_utc` (SCH-FEDERATION-001) is the SOURCE's own run time, and verify-not-
recall bans MANUFACTURING or RE-DERIVING it — not reading a legitimate recorded
fact from the source. This module encodes the reusable order every source reader
follows, and makes the basis SELF-DECLARING so a Craffter auditing a stamp can
see whether the timestamp is authoritative or a proxy — carried in the stamp's
existing `notes` free-text, never a new Tier-1 schema property.

Resolution order (fail-loud):
  1. the source's run manifest `ran_at_utc`, if it emits one   -> basis "run-manifest"
  2. else the source repo's git HEAD commit time (a proxy)     -> basis "git-head-commit"
  3. else fail-loud — NEVER the builder's clock or the fetch time.

A git commit time can drift from the actual build time, so an authoritative run
manifest is preferred where a source emits one; until then git HEAD is a sound,
recorded proxy — declared as such so the meaning travels with the value.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# The conventional filename a source may drop at its root to declare its own run
# time authoritatively. Picked up automatically when present.
DEFAULT_MANIFEST_NAME = "run-manifest.json"

# Keys a run manifest may carry the source run-UTC under (first non-empty wins).
_MANIFEST_KEYS = ("ran_at_utc", "ran_at", "built_utc")


class RanAtError(ValueError):
    """Fail-loud: no legitimate recorded source run-UTC could be resolved."""


@dataclass(frozen=True)
class RanAt:
    """A resolved source run-UTC plus how it was obtained.

    `basis` is one of "run-manifest" (authoritative) or "git-head-commit" (a
    proxy). `note()` renders the self-declaring string for the stamp's notes."""

    value: str   # ISO-8601 source run time
    basis: str   # "run-manifest" | "git-head-commit"

    def note(self) -> str:
        return f"ran_at_utc basis: {self.basis}"


def _from_manifest(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise RanAtError(f"run manifest {path} unreadable: {exc}") from exc
    if isinstance(data, dict):
        for key in _MANIFEST_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise RanAtError(
        f"run manifest {path} carries none of {_MANIFEST_KEYS}"
    )


def _git_head_commit_utc(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cI"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RanAtError(
            f"cannot read git HEAD commit time from {root!r} ({exc}); the source "
            f"is not a git working tree — pass an explicit run manifest instead"
        ) from exc
    stamp = out.stdout.strip()
    if not stamp:
        raise RanAtError(f"empty git HEAD commit time for {root!r}")
    return stamp


def resolve_ran_at(
    source_root, *, manifest_path: Optional[str] = None
) -> RanAt:
    """Resolve a source's run-UTC by the canonical order. Reusable for every
    source, not just Dolgellau.

    - `manifest_path` given: read it, basis "run-manifest"; fail-loud if it is
      missing or carries no run-UTC (an explicit manifest that isn't there is an
      error, not a silent fallback).
    - else a `run-manifest.json` at `source_root`: same, basis "run-manifest".
    - else the source repo's git HEAD commit time, basis "git-head-commit".
    - else raise RanAtError (never the builder's clock)."""
    root = Path(source_root)
    if manifest_path is not None:
        candidate = Path(manifest_path)
        if not candidate.is_file():
            raise RanAtError(f"run manifest not found: {manifest_path}")
        return RanAt(_from_manifest(candidate), "run-manifest")

    conventional = root / DEFAULT_MANIFEST_NAME
    if conventional.is_file():
        return RanAt(_from_manifest(conventional), "run-manifest")

    return RanAt(_git_head_commit_utc(root), "git-head-commit")
