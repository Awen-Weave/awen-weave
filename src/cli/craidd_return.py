#!/usr/bin/env python3
"""src/cli/craidd_return.py — build the Town Dataset RETURNS snapshot (Doctrine §8).

The up-flow half of standing federation: the Pi's commons-returnable claims,
stamped source_of_record = the Town Dataset instance, written as the same
four-file snapshot shape as catalogue/gazetteer snapshots, committed-to-repo so
the box PULLS it (the Pi never accepts inbound connections).

Runs ON THE PI, in its OWN exporter venv with awen-weave >= 0.2.1 (the Town
Dataset instance itself pins awen-weave 0.1.x — DO NOT bump the instance; give
the exporter a separate venv):

    python -m cli.craidd_return dolgellau \
        --source-root /srv/town-dataset \
        --duckdb /srv/town-dataset/craidd.duckdb \
        --out /srv/town-dataset/federated-out
    # then, as the Pi:  git add federated-out/ && git push   (box pulls)

Slice = ADJ-RETURN-001 open-identifier identity/linkage claims (see
craidd.returns) — NOT a filter on a `returnable:commons` stamp, which does not
exist. Every record is constitution.validate-clean (live porth gate on the Pi
else the vendored offline gate) before anything is written; fails loud, leaves no
partial snapshot. `--offline` forces the vendored gate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from craidd.ran_at import resolve_ran_at
from craidd.federation import SourceOfRecord
from craidd.gazetteer import gazetteer_stamp
from craidd.returns import RETURNABLE_PREDICATES, build_returns, read_returnable_claims
from craidd.snapshot import SnapshotBuilder, SnapshotError
from craidd.validation_gate import DEFAULT_PORTH_URL, default_gate

# Committed-to-repo delivery (Doctrine §8). Default output is a Pi path inside the
# town-dataset instance repo checkout; the Pi commits + pushes, the box pulls.
_DEFAULT_OUT = "/srv/town-dataset/federated-out"


def _build_dolgellau(args) -> int:
    try:
        import duckdb
    except ImportError:
        print("error: duckdb not available — run on the Pi / dataset host",
              file=sys.stderr)
        return 2

    ran_at = resolve_ran_at(args.source_root, manifest_path=args.source_manifest)
    source = SourceOfRecord(
        instance=args.instance,
        repo=args.repo,
        framework="tref",
        root=args.source_root,
        paths={"craidd": args.duckdb},
        ran_at_utc=ran_at.value,
        release=args.release,
    )

    con = duckdb.connect(args.duckdb, read_only=True)
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except Exception:
        pass
    predicates = tuple(args.predicate) if args.predicate else RETURNABLE_PREDICATES
    claim_rows = read_returnable_claims(con, predicates=predicates)
    con.close()

    if not claim_rows:
        print(f"NOTE: no returnable claims for predicates {predicates} in "
              f"{args.duckdb}. (The curator-confirmed UPRN↔building linkages live "
              f"in the Lleolydd cache, not Craidd, until the Town Dataset promotes "
              f"them — see the returns-channel report.) Nothing to export.",
              file=sys.stderr)
        return 3

    stamp = gazetteer_stamp(
        source=source,
        consumer_instance=args.consumer,        # the hub end: craidd:core
        craidd_node="place:dolgellau",
        craidd_source=args.instance,
        grade=args.grade,
        counts={"claims": len(claim_rows)},
        federated_utc=args.built_utc,
        licence="OGL",
        notes=f"returns slice: ADJ-RETURN-001 open-identifier identity/linkage "
              f"({', '.join(predicates)}); ran_at basis: {ran_at.basis}",
    )

    records = build_returns(
        claim_rows,
        source=source,
        consumer_instance=args.consumer,
        recorded_by=args.recorded_by,
        stamp=stamp,
    )

    gate = default_gate(args.porth_url, prefer_porth=not args.offline)
    print(f"validation gate: {gate.backend}")
    builder = SnapshotBuilder(gate, awen_weave_version=args.awen_weave_version)
    try:
        snap_dir = builder.build(records, args.out, built_utc=args.built_utc)
    except SnapshotError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"OK: wrote {snap_dir}")
    print(f"  claims={len(records.claims)} stamps={len(records.stamps)} "
          f"place_anchors={len(records.place_anchors)}")
    print(f"  predicates={predicates}  source={source.instance}  "
          f"ran_at_utc={ran_at.value} (basis: {ran_at.basis})")
    print("  next: (Pi) git add federated-out/ && git push   → box pulls; then "
          "insert the registry edge (awen-registry add-edge).")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the Town Dataset returns snapshot.")
    sub = parser.add_subparsers(dest="target", required=True)

    dol = sub.add_parser("dolgellau", help="materialise the Dolgellau returns slice")
    dol.add_argument("--source-root", default="/srv/town-dataset")
    dol.add_argument("--duckdb", default="/srv/town-dataset/craidd.duckdb")
    dol.add_argument("--out", default=_DEFAULT_OUT,
                     help="output dir; default = /srv/town-dataset/federated-out "
                          "(commit it into the town-dataset repo; the box pulls).")
    dol.add_argument("--instance", default="dolgellau-town-dataset",
                     help="source_of_record instance id (the federation-stamp form; "
                          "the registry canonical id is tref:dolgellau).")
    dol.add_argument("--repo", default="arloesidolgellau/town-dataset")
    dol.add_argument("--consumer", default="craidd:core",
                     help="the hub end (RATIFIED naming: craidd:core).")
    dol.add_argument("--recorded-by", default="huw@arloesidolgellau.cymru")
    dol.add_argument("--grade", default="A", choices=["A", "B", "C"])
    dol.add_argument("--release", default="returns")
    dol.add_argument("--predicate", action="append", default=None,
                     help="override the returnable predicate allowlist (repeatable); "
                          "default = craidd.returns.RETURNABLE_PREDICATES.")
    dol.add_argument("--source-manifest", default=None)
    dol.add_argument("--built-utc", default=None,
                     help="ISO build time (default now); set for a reproducible build")
    dol.add_argument("--awen-weave-version", default="0.2.3",
                     help="version pinned into the manifest (this exporter needs >=0.2.1)")
    dol.add_argument("--porth-url", default=DEFAULT_PORTH_URL)
    dol.add_argument("--offline", action="store_true",
                     help="use the vendored offline gate, skip porth")
    dol.set_defaults(func=_build_dolgellau)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
