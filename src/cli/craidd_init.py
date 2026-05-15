#!/usr/bin/env python3
"""
craidd-init — bootstrap a fresh Craidd database (cli-design.md §4.1).

Creates the two DuckDB databases (craidd.duckdb and prawf.duckdb) under
the target data directory, applies the v0.1 schema, and seeds the
predicate registry with the v0.1 predicate set.

This is the one CLI that touches the storage layer directly — it has to,
because it creates the storage every other component depends on. It is
run ONCE, at Pi setup. It is idempotent against an empty database and
REFUSES to run against a non-empty one (cli-design.md §4.1): there is no
re-init in production.

Entity types are not seeded as rows — the controlled entity-type list is
the CHECK constraint baked into the schema DDL, installed when the DDL
runs. Only the predicate registry is seeded data.

NOTE — Prawf genesis entry: craidd-init creates prawf.duckdb with an
empty prawf_log table. It does NOT write a genesis entry recording the
bootstrap — that would need the Prawf logger component (architecture.md
§6.11), which is outside the foundation's scope. Whether the bootstrap
itself should be Prawf-logged is an open question for when that
component is built; see the foundation handover.

USAGE
-----
    python3 src/cli/craidd_init.py [--data-dir PATH] [--actor NAME]
                                   [--dry-run] [--json]

    --data-dir PATH   where to create the databases
                      (default: /srv/town-dataset, the Pi's canonical dir)
    --actor NAME      recorded as predicate.added_by on every seeded
                      predicate (default: "craidd-init")
    --dry-run         validate and report what would be created; create
                      nothing
    --json            machine-readable output

EXIT CODES
----------
    0  success (databases created and seeded), or a clean dry-run
    1  refused — a target database already exists and is non-empty
    2  error — the seed set is malformed, or a database error occurred
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Put the src/ root on the import path so `craidd.*` resolves when this
# script is run directly: python3 src/cli/craidd_init.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from craidd import SCHEMA_VERSION
from craidd.schema import SEED_PREDICATES, validate_seed_predicates
from craidd.storage import (
    CRAIDD_DDL,
    PRAWF_DDL,
    craidd_db_path,
    prawf_db_path,
    connect_craidd,
    connect_prawf,
    apply_ddl,
    database_is_empty,
)

_INSERT_PREDICATE = (
    "INSERT INTO predicate "
    "(name, value_type, cardinality, applies_to_types, description_cy, "
    "description_en, constraint_json, required_qualifiers, added_by) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _seed_predicate_rows(actor: str) -> list[tuple]:
    """Build the INSERT parameter rows for the predicate registry. The
    applies_to_types and required_qualifiers columns are stored as JSON
    array strings, per design/v0.1-schema.md §3.3."""
    return [
        (
            p.name,
            p.value_type,
            p.cardinality,
            json.dumps(list(p.applies_to_types)),
            p.description_cy,
            p.description_en,
            p.constraint_json,
            json.dumps(list(p.required_qualifiers)),
            actor,
        )
        for p in SEED_PREDICATES
    ]


def _check_target_empty(label: str, path: Path, connect_fn) -> str | None:
    """Return an error string if `path` exists and is a non-empty
    database; return None if it is safe to bootstrap (file absent, or
    present but empty)."""
    if not path.exists():
        return None
    try:
        conn = connect_fn(path)
        empty = database_is_empty(conn)
        conn.close()
    except Exception as exc:
        # Any failure to open/inspect an existing file is a refusal —
        # craidd-init must never bootstrap over an unreadable database.
        return f"{label}: could not inspect existing file at {path}: {exc}"
    if not empty:
        return (
            f"{label}: {path} already exists and is not empty. craidd-init "
            f"refuses to run against a non-empty database — there is no "
            f"re-init in production (cli-design.md §4.1)."
        )
    return None


def _report_failure(as_json: bool, *, code: int, reason: str,
                    detail: list[str]) -> None:
    if as_json:
        print(json.dumps(
            {"ok": False, "exit_code": code, "reason": reason,
             "detail": detail},
            indent=2,
        ))
    else:
        print(f"craidd-init: FAILED — {reason}", file=sys.stderr)
        for line in detail:
            print(f"  - {line}", file=sys.stderr)


def _report_dry_run(as_json: bool, craidd_path: Path, prawf_path: Path,
                    n_predicates: int, actor: str) -> None:
    if as_json:
        print(json.dumps(
            {"ok": True, "dry_run": True, "schema_version": SCHEMA_VERSION,
             "craidd_db": str(craidd_path), "prawf_db": str(prawf_path),
             "predicates_to_seed": n_predicates, "actor": actor},
            indent=2,
        ))
    else:
        print("craidd-init: DRY RUN — nothing created")
        print(f"  schema version : {SCHEMA_VERSION}")
        print(f"  would create   : {craidd_path}")
        print(f"                   {prawf_path}")
        print(f"  would seed     : {n_predicates} predicates "
              f"(added_by = {actor!r})")


def _report_success(as_json: bool, craidd_path: Path, prawf_path: Path,
                    seeded: int, actor: str) -> None:
    if as_json:
        print(json.dumps(
            {"ok": True, "dry_run": False, "schema_version": SCHEMA_VERSION,
             "craidd_db": str(craidd_path), "prawf_db": str(prawf_path),
             "predicates_seeded": seeded, "actor": actor},
            indent=2,
        ))
    else:
        print("craidd-init: OK — Craidd bootstrapped")
        print(f"  schema version    : {SCHEMA_VERSION}")
        print(f"  craidd.duckdb     : {craidd_path}")
        print(f"  prawf.duckdb      : {prawf_path}")
        print(f"  predicates seeded : {seeded} (added_by = {actor!r})")
        print("  prawf_log         : created empty (no genesis entry — "
              "see the craidd-init docstring)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="craidd-init",
        description="Bootstrap a fresh Craidd database (cli-design.md §4.1).",
    )
    parser.add_argument(
        "--data-dir", default=None,
        help="directory to create the databases in "
             "(default: /srv/town-dataset)",
    )
    parser.add_argument(
        "--actor", default="craidd-init",
        help="recorded as predicate.added_by on every seeded predicate",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="validate and report what would be created; create nothing",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="machine-readable output",
    )
    args = parser.parse_args(argv)

    craidd_path = craidd_db_path(args.data_dir)
    prawf_path = prawf_db_path(args.data_dir)

    # --- 1. validate the seed set before touching anything --------------
    seed_errors = validate_seed_predicates()
    if seed_errors:
        _report_failure(args.as_json, code=2,
                        reason="seed predicate set is malformed",
                        detail=seed_errors)
        return 2

    # --- 2. refuse if either target database exists and is non-empty ----
    refusals: list[str] = []
    for label, path, connect_fn in (
        ("craidd.duckdb", craidd_path,
         lambda p: connect_craidd(p, load_spatial=False)),
        ("prawf.duckdb", prawf_path, connect_prawf),
    ):
        msg = _check_target_empty(label, path, connect_fn)
        if msg:
            refusals.append(msg)
    if refusals:
        _report_failure(
            args.as_json, code=1,
            reason="target database already exists and is non-empty",
            detail=refusals,
        )
        return 1

    # --- 3. dry run: report and stop ------------------------------------
    if args.dry_run:
        _report_dry_run(args.as_json, craidd_path, prawf_path,
                        len(SEED_PREDICATES), args.actor)
        return 0

    # --- 4. bootstrap ---------------------------------------------------
    try:
        craidd_path.parent.mkdir(parents=True, exist_ok=True)

        # craidd.duckdb — v0.1 schema + seeded predicate registry
        conn = connect_craidd(craidd_path)
        apply_ddl(conn, CRAIDD_DDL)
        conn.executemany(_INSERT_PREDICATE, _seed_predicate_rows(args.actor))
        seeded = conn.execute("SELECT count(*) FROM predicate").fetchone()[0]
        conn.close()

        # prawf.duckdb — empty append-only log table
        pconn = connect_prawf(prawf_path)
        apply_ddl(pconn, PRAWF_DDL)
        pconn.close()
    except Exception as exc:
        _report_failure(args.as_json, code=2,
                        reason="database error during bootstrap",
                        detail=[str(exc)])
        return 2

    _report_success(args.as_json, craidd_path, prawf_path, seeded, args.actor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
