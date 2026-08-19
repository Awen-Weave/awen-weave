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

import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .federation import now_utc

# ── coverage regression (rule 4) ────────────────────────────────────────────────────────────────
# A GSS (E06000001) or census area code (E01000001 LSOA / E00… OA): a nation letter followed by
# eight digits, not embedded in a longer alphanumeric run — so a bare UPRN like 100023336956 never
# matches and a per-property layer is correctly seen as carrying no nation code at all.
_NATION_CODE = re.compile(r"(?<![A-Za-z0-9])([EWSN])\d{8}(?![0-9])")
_NATION_NAME = {"E": "england", "W": "wales", "S": "scotland", "N": "northern-ireland"}
# Every claims shape the estate actually writes, newest-first preference. Checked on the live box
# 16/08: claims.json (flood, elderly, heritage points), claims.json.gz (desnz, census, gazetteer,
# gp) and claims.jsonl.gz (the streamed tiled layers — conservation, coal, roads, coast path).
_CLAIMS_FILES = ("claims.json", "claims.json.gz", "claims.jsonl.gz")


def _subjects_by_nation(claims) -> dict:
    """Nation letter -> the set of distinct nation-coded subject_ids under it.

    WHY THIS EXISTS, one level finer than `_nations_of`. The England+Wales flood run of 19/08
    completed `rc=0` having LOST TWO ENGLISH AUTHORITIES — North Devon and Cotswold, both dropped on
    a transient truncated WFS body — and the nation-presence check above passed correctly, because
    England was still there. 294 authorities where the snapshot it replaced had 296, and the only
    thing that noticed was a line in the runner's own log.

    That is the same shape as the 16/08 failure it was written for, one level down: a national layer
    silently shrinking. A guard that catches a dropped NATION but not a dropped AUTHORITY produces
    confidence about exactly the case a consumer would hit — a lookup on a real GSS code returning
    nothing, with no error anywhere.
    """
    out: dict = {}
    for c in claims:
        if not isinstance(c, dict):
            continue
        sid = str(c.get("subject_id", ""))
        m = _NATION_CODE.search(sid)
        if m:
            out.setdefault(m.group(1), set()).add(sid)
    return out


def _nations_of(claims) -> set:
    """The nation letters present across a claim set's subject_ids. Empty for a UPRN-keyed layer."""
    out = set()
    for c in claims:
        if not isinstance(c, dict):
            continue
        m = _NATION_CODE.search(str(c.get("subject_id", "")))
        if m:
            out.add(m.group(1))
    return out


def _read_claims(path: Path):
    """Read one claims file in any of the three shapes the estate writes. None if unreadable."""
    try:
        if path.name.endswith(".jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
        raw = (gzip.open(path, "rt", encoding="utf-8") if path.name.endswith(".gz")
               else path.open("r", encoding="utf-8"))
        with raw as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, list) else doc.get("claims", [])
    except Exception:
        return None


def _prior_snapshot(out_dir: Path):
    """The newest existing snapshot under out_dir, or None. Sorted by name: snapshot ids are
    compact UTC timestamps, so lexical order IS chronological order."""
    try:
        snaps = sorted(p for p in Path(out_dir).glob("snapshot-*") if p.is_dir())
    except OSError:
        return None
    return snaps[-1] if snaps else None


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

    # -- coverage regression --------------------------------------------------
    def _assert_no_coverage_regression(self, records: "SnapshotRecords",
                                       out_dir: Path) -> None:
        """Refuse a rebuild that drops a nation the snapshot it replaces carried.

        SELF-LIMITING BY DESIGN, so a guard added at the shared spine cannot break builds it was
        never meant to police. It does nothing unless the NEW record set is nation-coded:

          * new set has no nation codes  -> no-op. A per-UPRN layer (or a layer that emits no
            claims at all, like planning-lifecycle) has nothing to compare and never will.
          * no prior snapshot            -> no-op. A first build cannot shrink anything, and a
            guard that makes the empty case impossible is its own failure mode.
          * prior present but its claims cannot be read -> RAISE. This is the ambiguous state, and
            it is only reached for a layer we already know is nation-coded. Passing silently here
            is precisely the "empty scan reads as clean" defect the estate keeps paying for.
          * a nation present before and absent now -> RAISE.

        Widening coverage is always fine. A deliberate REDUCTION is expressed by removing the prior
        snapshot first, which makes shrinking an explicit act rather than a side effect of a flag.
        """
        new_nations = _nations_of(records.claims)
        if not new_nations:
            return                                   # not a nation-coded layer; nothing to police

        prior = _prior_snapshot(out_dir)
        if prior is None:
            return                                   # first build

        prior_claims = None
        for name in _CLAIMS_FILES:
            f = prior / name
            if f.exists():
                prior_claims = _read_claims(f)
                if prior_claims is not None:
                    break
        if prior_claims is None:
            raise SnapshotError(
                f"coverage check could not read the prior snapshot's claims in {prior} — this "
                f"layer IS nation-coded ({sorted(_NATION_NAME[n] for n in new_nations)}), so the "
                f"check matters and cannot be skipped. Looked for {list(_CLAIMS_FILES)}. An "
                f"unverifiable coverage comparison is not a passing one."
            )

        prior_nations = _nations_of(prior_claims)
        dropped = prior_nations - new_nations
        if not dropped:
            # A nation kept but THINNED. Counted per nation rather than in total, because a total
            # could be held level by one nation growing while another loses authorities.
            new_by = _subjects_by_nation(records.claims)
            prior_by = _subjects_by_nation(prior_claims)
            thinned = {n: (len(prior_by[n]), len(new_by.get(n, ())))
                       for n in prior_by if len(new_by.get(n, ())) < len(prior_by[n])}
            if thinned:
                detail = "; ".join(
                    f"{_NATION_NAME[n]} {before} -> {after} ({before - after} lost)"
                    for n, (before, after) in sorted(thinned.items()))
                missing = sorted(
                    s for n in thinned for s in (prior_by[n] - new_by.get(n, set())))
                raise SnapshotError(
                    f"coverage REGRESSION (subjects, not nations): every nation is still present, "
                    f"but this rebuild covers FEWER subjects than the snapshot it replaces "
                    f"({prior.name}) — {detail}. "
                    f"First missing: {missing[:8]}{' …' if len(missing) > 8 else ''}. "
                    f"This is the 19/08 flood case: an England+Wales rebuild finished rc=0 having "
                    f"lost North Devon and Cotswold to a transient truncated WFS body, and the "
                    f"nation-presence check passed because England was still there. A consumer "
                    f"looking up a real GSS code would have got nothing, with no error anywhere. "
                    f"Re-run the failed subjects, or, if the reduction is genuinely intended, "
                    f"remove the prior snapshot deliberately first."
                )
        if dropped:
            raise SnapshotError(
                f"coverage REGRESSION: this rebuild covers "
                f"{sorted(_NATION_NAME[n] for n in new_nations)} but the snapshot it replaces "
                f"({prior.name}) covered {sorted(_NATION_NAME[n] for n in prior_nations)} — it "
                f"DROPS {sorted(_NATION_NAME[n] for n in dropped)}. "
                f"A re-materialise must not silently shrink national coverage (flood-coverage, "
                f"16/08: --nations wales cut 296 English authorities out of a national layer and "
                f"only an unrelated failure stopped it shipping). Restore the missing nation, or, "
                f"if the reduction is genuinely intended, remove the prior snapshot deliberately "
                f"first."
            )

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

        # 1b. RULE 4 — a re-materialise must not silently SHRINK national coverage.
        #
        # This lives HERE, in the one place every snapshot write passes through, and not in the
        # runners. It was in a runner, and on 16/08 that cost the estate a 93% coverage loss it
        # caught only by luck: flood-coverage was re-materialised with `--nations wales`, dropping
        # 296 English authorities (646 claims -> 48), and the guard did not fire because
        # `build_flood_snapshot.py` is a SEPARATE runner from the shared `build_layer_snapshot.py`
        # the guard had been wired into. Seven runners in the catalogue write snapshots; two called
        # the guard. All seven call THIS method.
        #
        # A guard that covers one path and not its sibling is worse than no guard, because it
        # produces confidence. So the check moved to the chokepoint.
        self._assert_no_coverage_regression(records, Path(out_dir))

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
