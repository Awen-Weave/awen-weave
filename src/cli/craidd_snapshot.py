#!/usr/bin/env python3
"""
src/cli/craidd_snapshot.py — build a governed-dataset snapshot (S1 Deliverable A CLI).

Reads a governed dataset and writes a stamped, validated snapshot directory an
off-tailnet consumer can fetch. For S1 the one wired source is the Dolgellau Town
Dataset gazetteer; the builder itself (craidd.snapshot) is engine-agnostic.

Runs on craidd, where the store and the porth validation sibling both live:

    python -m cli.craidd_snapshot dolgellau-gazetteer \
        --source-root /srv/town-dataset \
        --duckdb /srv/town-dataset/craidd.duckdb
        # --out defaults to the committed repo path snapshots/dolgellau-gazetteer/

Delivery is committed-to-repo (resolved 2026-07-11): the snapshot lands in the
tracked repo path CHI's build pulls, so the flow is `craidd-snapshot …` then
`git add snapshots/ && git push` (as huw-awenweave) — no external dir to copy in.
CHI's pull_tref.py --snapshot points at the checked-out snapshot dir; the static
craidd endpoint is the later transport-hop option, not needed for the first proof.

Every record is constitution.validate-clean (live porth gate on craidd, else the
vendored offline gate) before anything is written; the build fails loud and
leaves no partial snapshot if any record is invalid. The manifest pins the LIVE
constitution version read from porth at build time.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from craidd.readers.dolgellau import build_gazetteer, read_from_duckdb
from craidd.ran_at import resolve_ran_at
from craidd.federation import SourceOfRecord
from craidd.snapshot import SnapshotBuilder, SnapshotError
from craidd.validation_gate import DEFAULT_PORTH_URL, default_gate

# Delivery is committed-to-repo (resolved 2026-07-11): the emitted snapshot lands
# in the tracked repo path CHI's build pulls (snapshots/dolgellau-gazetteer/), NOT
# an external craidd dir that then needs copying in. Computed from this file's
# location so it resolves to whatever checkout runs the CLI on craidd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMITTED_OUT = str(_REPO_ROOT / "snapshots" / "dolgellau-gazetteer")


def _build_dolgellau(args) -> int:
    try:
        import duckdb
    except ImportError:
        print("error: duckdb not available — run on craidd / the dataset host",
              file=sys.stderr)
        return 2

    ran_at = resolve_ran_at(args.source_root, manifest_path=args.source_manifest)
    source = SourceOfRecord(
        instance="dolgellau-town-dataset",
        repo="arloesidolgellau/town-dataset",
        framework="tref",
        root=args.source_root,
        paths={"gazetteer": args.duckdb},
        ran_at_utc=ran_at.value,
        release=args.release,
    )

    con = duckdb.connect(args.duckdb, read_only=True)
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except Exception:
        pass  # spatial already present in the town-dataset build
    buildings, name_claims = read_from_duckdb(con)

    records = build_gazetteer(
        buildings, name_claims,
        source=source,
        consumer_instance=args.consumer,
        recorded_by=args.recorded_by,
        craidd_node="place:dolgellau",
        craidd_source="dolgellau-town-dataset",
        grade=args.grade,
        federated_utc=args.built_utc,  # None -> now at build time
        ran_at_basis=ran_at.basis,     # declared in the stamp notes
    )

    gate = default_gate(args.porth_url, prefer_porth=not args.offline)
    print(f"validation gate: {gate.backend}")
    builder = SnapshotBuilder(gate)
    try:
        snap_dir = builder.build(records, args.out, built_utc=args.built_utc)
    except SnapshotError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"OK: wrote {snap_dir}")
    print(f"  place_anchors={len(records.place_anchors)} "
          f"claims={len(records.claims)} stamps={len(records.stamps)}")
    print(f"  source ran_at_utc={ran_at.value} (basis: {ran_at.basis})")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a governed-dataset snapshot.")
    sub = parser.add_subparsers(dest="target", required=True)

    dol = sub.add_parser("dolgellau-gazetteer",
                         help="materialise the Dolgellau gazetteer snapshot")
    dol.add_argument("--source-root", default="/srv/town-dataset")
    dol.add_argument("--duckdb", default="/srv/town-dataset/craidd.duckdb")
    dol.add_argument("--out", default=_COMMITTED_OUT,
                     help="output dir; default = the committed repo path "
                          "snapshots/dolgellau-gazetteer/ so the emitted "
                          "snapshot lands where CHI's build pulls it (then "
                          "git add + push as huw-awenweave). pull_tref.py "
                          "--snapshot points at the checked-out snapshot dir.")
    dol.add_argument("--consumer", default="care-home-insight")
    dol.add_argument("--recorded-by", default="huw@arloesidolgellau.cymru")
    dol.add_argument("--grade", default="B", choices=["A", "B", "C"])
    dol.add_argument("--release", default="complete")
    dol.add_argument("--source-manifest", default=None,
                     help="path to the source's run manifest (authoritative "
                          "ran_at_utc); default = <source-root>/run-manifest.json "
                          "if present, else the town-dataset git HEAD (proxy)")
    dol.add_argument("--built-utc", default=None,
                     help="ISO build time (default now); set for a reproducible build")
    dol.add_argument("--porth-url", default=DEFAULT_PORTH_URL)
    dol.add_argument("--offline", action="store_true",
                     help="use the vendored offline gate, skip porth")
    dol.set_defaults(func=_build_dolgellau)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
