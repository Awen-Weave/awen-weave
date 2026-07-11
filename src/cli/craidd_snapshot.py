#!/usr/bin/env python3
"""
src/cli/craidd_snapshot.py — build a governed-dataset snapshot (S1 Deliverable A CLI).

Reads a governed dataset and writes a stamped, validated snapshot directory an
off-tailnet consumer can fetch. For S1 the one wired source is the Dolgellau Town
Dataset gazetteer; the builder itself (craidd.snapshot) is engine-agnostic.

Runs on craidd, where the store and the porth validation sibling both live:

    python -m cli.craidd_snapshot dolgellau-gazetteer \
        --source-root /srv/town-dataset \
        --duckdb /srv/town-dataset/craidd.duckdb \
        --out /srv/town-dataset/snapshots

Every record is constitution.validate-clean (live porth gate on craidd, else the
vendored offline gate) before anything is written; the build fails loud and
leaves no partial snapshot if any record is invalid. The manifest pins the LIVE
constitution version read from porth at build time.
"""
from __future__ import annotations

import argparse
import sys

from craidd.readers.dolgellau import (
    build_gazetteer,
    read_from_duckdb,
    resolve_source_ran_at,
)
from craidd.federation import SourceOfRecord
from craidd.snapshot import SnapshotBuilder, SnapshotError
from craidd.validation_gate import DEFAULT_PORTH_URL, default_gate


def _build_dolgellau(args) -> int:
    try:
        import duckdb
    except ImportError:
        print("error: duckdb not available — run on craidd / the dataset host",
              file=sys.stderr)
        return 2

    ran_at = args.source_ran_at or resolve_source_ran_at(args.source_root)
    source = SourceOfRecord(
        instance="dolgellau-town-dataset",
        repo="arloesidolgellau/town-dataset",
        framework="tref",
        root=args.source_root,
        paths={"gazetteer": args.duckdb},
        ran_at_utc=ran_at,
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
    print(f"  source ran_at_utc={ran_at}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a governed-dataset snapshot.")
    sub = parser.add_subparsers(dest="target", required=True)

    dol = sub.add_parser("dolgellau-gazetteer",
                         help="materialise the Dolgellau gazetteer snapshot")
    dol.add_argument("--source-root", default="/srv/town-dataset")
    dol.add_argument("--duckdb", default="/srv/town-dataset/craidd.duckdb")
    dol.add_argument("--out", default="/srv/town-dataset/snapshots")
    dol.add_argument("--consumer", default="care-home-insight")
    dol.add_argument("--recorded-by", default="huw@arloesidolgellau.cymru")
    dol.add_argument("--grade", default="B", choices=["A", "B", "C"])
    dol.add_argument("--release", default="complete")
    dol.add_argument("--source-ran-at", default=None,
                     help="ISO source run-UTC; default = town-dataset git HEAD")
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
