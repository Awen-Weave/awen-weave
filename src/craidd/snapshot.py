"""
src/craidd/snapshot.py — Deliverable A: the reusable snapshot builder.

Materialises a governed dataset into a STAMPED, VALIDATED snapshot directory an
off-tailnet consumer (e.g. CHI's edge worker) can fetch. Engine-agnostic — it
serves maes and tref alike; the instance supplies a reader that produces the
records, this module validates and writes them.

    snapshot-<iso>/
      manifest.json        # pins + source_ran_at + counts (brief §5)
      place-anchors.json   # array of SCH-PLACEANCHOR-001 records
      claims.json          # array of SCH-CLAIM-001 records
      stamps.json          # array of SCH-FEDERATION-001 stamps

Rules (brief §3), all fail-loud:
  1. EVERY record is constitution.validate-clean before it is written. If any
     record fails, the WHOLE snapshot fails — no partial snapshot is left on
     disk (validate fully in memory, write only once everything is clean).
  2. source_ran_at / ran_at_utc are READ from the source's own manifest and
     carried through — never re-derived here (verify-not-recall). The builder
     records what the reader supplies; it never manufactures a run-UTC.
  3. Deterministic output (stable record ordering, sorted keys) so a `git diff`
     on a committed snapshot is meaningful.

The build-time-snapshot implementation of the transport-invariant federation
model (spec §7): the same stamped records could equally travel a live API; here
they are frozen into a directory a repo commits or a static endpoint serves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .federation import now_utc


class SnapshotError(RuntimeError):
    """Fail-loud: a record failed validation, or the record set is malformed.

    Carries the full list of per-record violations so a build never silently
    drops a bad record — the whole snapshot is refused."""

    def __init__(self, message: str, problems: Optional[list] = None):
        super().__init__(message)
        self.problems = problems or []


@dataclass
class SnapshotRecords:
    """The record set a reader hands the builder for one snapshot.

    Kept deliberately thin: three logical files, each an array of plain dicts
    already shaped to their SCH-* schema. `source_ran_at` maps each federated
    source instance id to its OWN run-UTC (read from that source's manifest) —
    it lands verbatim in the manifest (verify-not-recall)."""

    place_anchors: list = field(default_factory=list)
    claims: list = field(default_factory=list)
    stamps: list = field(default_factory=list)
    source_ran_at: dict = field(default_factory=dict)


# logical file name -> (record list attribute, validation kind)
_FILES = (
    ("place-anchors.json", "place_anchors", "place-anchor"),
    ("claims.json", "claims", "claim"),
    ("stamps.json", "stamps", "federation-stamp"),
)


def compact_snapshot_id(built_utc: str) -> str:
    """A filesystem-safe snapshot id from an ISO build time.

    `2026-07-11T04:30:00+00:00` -> `snapshot-20260711T043000Z`. Deterministic:
    the same build time always yields the same id (no wall-clock read here)."""
    core = built_utc.split("+")[0].replace("Z", "")
    for ch in ("-", ":"):
        core = core.replace(ch, "")
    core = core.split(".")[0]  # drop any fractional seconds
    return "snapshot-" + core + "Z"


def _dump(obj) -> str:
    """Deterministic JSON: sorted keys, 2-space indent, UTF-8 kept, trailing
    newline — so a committed snapshot diffs cleanly."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


class SnapshotBuilder:
    """Validate a record set against the constitution and write a snapshot dir.

    `gate` is any object with `validate(kind, doc) -> ValidationResult` and
    `pin() -> ConstitutionPin` — a live `PorthValidator` on craidd, or the
    offline `SchemaValidator` in CI (see validation_gate.default_gate)."""

    def __init__(self, gate, awen_weave_version: str = "0.2.0"):
        self.gate = gate
        self.awen_weave_version = awen_weave_version

    # -- validation ----------------------------------------------------------
    def _validate_all(self, records: SnapshotRecords) -> list:
        """Validate every record; return the full list of problem strings.
        Empty list == the whole set is clean."""
        problems: list = []
        for _fname, attr, kind in _FILES:
            for i, record in enumerate(getattr(records, attr)):
                result = self.gate.validate(kind, record)
                if not result.valid:
                    ident = (
                        record.get("uprn")
                        or record.get("subject_id")
                        or (record.get("source_of_record") or {}).get("instance")
                        or f"index {i}"
                    )
                    problems.append(
                        f"{kind}[{i}] ({ident}): {'; '.join(result.violations)}"
                    )
        return problems

    def _manifest(self, records: SnapshotRecords, snapshot_id: str,
                  built_utc: str) -> dict:
        pin = self.gate.pin()
        counts = {
            "place_anchors": len(records.place_anchors),
            "claims": len(records.claims),
            "stamps": len(records.stamps),
        }
        return {
            "snapshot_id": snapshot_id,
            "built_utc": built_utc,
            "pins": pin.to_manifest_pins(self.awen_weave_version),
            "constitution_pin_source": pin.source,
            "source_ran_at": dict(records.source_ran_at),
            "counts": counts,
        }

    # -- build ---------------------------------------------------------------
    def build(self, records: SnapshotRecords, out_dir: Path,
              built_utc: Optional[str] = None,
              snapshot_id: Optional[str] = None) -> Path:
        """Validate then write a snapshot under `out_dir/<snapshot_id>/`.

        Returns the snapshot directory. Fail-loud: raises SnapshotError with the
        full problem list before writing anything if any record is invalid — no
        partial snapshot is left on disk.

        `built_utc` (the consumer's build instant) defaults to now; pass it
        explicitly for a deterministic/reproducible build. It is NOT a source
        run-UTC — those live in `records.source_ran_at` (verify-not-recall)."""
        built_utc = built_utc or now_utc()
        snapshot_id = snapshot_id or compact_snapshot_id(built_utc)

        # 1. Validate the whole set FIRST — no file is written if anything fails.
        problems = self._validate_all(records)
        if problems:
            raise SnapshotError(
                f"snapshot refused: {len(problems)} record(s) failed "
                f"constitution.validate ({self.gate.backend} gate) — no partial "
                f"snapshot written",
                problems,
            )

        # 2. Build every file's content in memory (deterministic ordering).
        manifest = self._manifest(records, snapshot_id, built_utc)
        contents = {"manifest.json": _dump(manifest)}
        for fname, attr, _kind in _FILES:
            contents[fname] = _dump(getattr(records, attr))

        # 3. Write once, all clean.
        snap_dir = Path(out_dir) / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        for fname, text in contents.items():
            (snap_dir / fname).write_text(text, encoding="utf-8")
        return snap_dir
