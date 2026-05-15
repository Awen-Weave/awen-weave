"""
src/craidd/storage — the Craidd storage layer (architecture.md §6.1).

Materialises the v0.1 schema as two DuckDB databases (craidd.duckdb and
prawf.duckdb) and provides thin connection helpers. No business logic,
no auth. The only views it creates are the two the schema document
itself defines — current_claim and cy_coverage (design/v0.1-schema.md
§11); the storage layer invents no analytical views of its own.

Source of truth for the DDL: design/v0.1-schema.md §11.
"""
from __future__ import annotations

from .ddl import CRAIDD_DDL, PRAWF_DDL
from .database import (
    DEFAULT_DATA_DIR,
    CRAIDD_DB_FILENAME,
    PRAWF_DB_FILENAME,
    craidd_db_path,
    prawf_db_path,
    connect_craidd,
    connect_prawf,
    apply_ddl,
    database_is_empty,
)

__all__ = [
    "CRAIDD_DDL",
    "PRAWF_DDL",
    "DEFAULT_DATA_DIR",
    "CRAIDD_DB_FILENAME",
    "PRAWF_DB_FILENAME",
    "craidd_db_path",
    "prawf_db_path",
    "connect_craidd",
    "connect_prawf",
    "apply_ddl",
    "database_is_empty",
]
