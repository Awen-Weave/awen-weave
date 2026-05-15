"""
src/craidd/storage/database.py — thin DuckDB connection helpers.

The storage layer (architecture.md §6.1): no business logic, no auth —
just open connections to the canonical databases and apply the schema
DDL. The two databases are separate files (design/v0.1-schema.md §2) so
a corruption in one cannot reach the other:

  craidd.duckdb  entity, predicate, claim + the current_claim and
                 cy_coverage views
  prawf.duckdb   the append-only, hash-chained prawf_log

On the Pi both live under /srv/town-dataset/. Tests and dev pass an
explicit path instead of relying on that default.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from .ddl import CRAIDD_DDL, PRAWF_DDL  # re-exported for callers' convenience

# Canonical data directory on the Pi (design/v0.1-schema.md §2).
DEFAULT_DATA_DIR = Path("/srv/town-dataset")
CRAIDD_DB_FILENAME = "craidd.duckdb"
PRAWF_DB_FILENAME = "prawf.duckdb"


def craidd_db_path(data_dir: Path | str | None = None) -> Path:
    """Canonical path to craidd.duckdb (defaults to the Pi's data dir)."""
    base = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    return base / CRAIDD_DB_FILENAME


def prawf_db_path(data_dir: Path | str | None = None) -> Path:
    """Canonical path to prawf.duckdb (defaults to the Pi's data dir)."""
    base = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    return base / PRAWF_DB_FILENAME


def connect_craidd(
    db_path: Path | str | None = None,
    *,
    load_spatial: bool = True,
) -> duckdb.DuckDBPyConnection:
    """Open a connection to craidd.duckdb.

    Loads the DuckDB `spatial` extension by default — it provides the
    GEOMETRY type used by claim.value_geom (design/v0.1-schema.md §11).
    The first INSTALL needs network access; it is cached thereafter.
    Pass load_spatial=False only for operations that touch no geometry.
    """
    path = Path(db_path) if db_path is not None else craidd_db_path()
    conn = duckdb.connect(str(path))
    if load_spatial:
        conn.execute("INSTALL spatial; LOAD spatial;")
    return conn


def connect_prawf(
    db_path: Path | str | None = None,
) -> duckdb.DuckDBPyConnection:
    """Open a connection to prawf.duckdb. The Prawf log needs no
    extensions — it is plain columns only."""
    path = Path(db_path) if db_path is not None else prawf_db_path()
    return duckdb.connect(str(path))


def _split_statements(ddl: str) -> list[str]:
    """Split a multi-statement DDL script into individual statements,
    dropping blank and comment-only fragments. Safe for the controlled
    DDL in ddl.py — it contains no semicolons inside string literals."""
    statements: list[str] = []
    for chunk in ddl.split(";"):
        code_lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if code_lines:
            statements.append("\n".join(code_lines))
    return statements


def apply_ddl(conn: duckdb.DuckDBPyConnection, ddl: str) -> None:
    """Execute a multi-statement DDL script against an open connection,
    one statement at a time."""
    for statement in _split_statements(ddl):
        conn.execute(statement)


def database_is_empty(conn: duckdb.DuckDBPyConnection) -> bool:
    """True if the database has no user objects (tables or views) in the
    main schema. craidd-init uses this to decide whether bootstrap is
    safe — it refuses to run against a non-empty database (cli-design.md
    §4.1)."""
    row = conn.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'main'"
    ).fetchone()
    return row is not None and row[0] == 0
