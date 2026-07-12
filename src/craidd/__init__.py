"""
src/craidd — the Craidd core for the Dolgellau Town Dataset.

The Craidd is Awen's place-based trust core: the canonical store of
claims and the schema that shapes them. This package holds the two
Craidd-role components from design/architecture.md:

  - schema/   the schema layer (architecture.md §6.2): entity types,
              predicates, qualifiers, and the validation contract.
              Pure logic — no I/O, no DB access, no auth.
  - storage/  the storage layer (architecture.md §6.1): the DuckDB
              databases and thin connection helpers. No business logic.

Everything that *talks to* the Craidd — the Read/Write APIs, the
craidd-* CLIs, the MCP server, the client library — is Llys-role and
lives outside this package (src/cli/, src/api/, client/).

Source of truth for the data model: design/v0.1-schema.md.
"""
from __future__ import annotations

# The schema version this package implements. Bump deliberately, in step
# with a new design/vX.Y-schema.md document — never silently.
SCHEMA_VERSION = "v0.1"

# The awen-constitution release this package validates against
# (compatibility.md: constitution 0.1.x ↔ awen-weave 0.2.x). From constitution
# 0.2.0 the spec LEADS and this package validates against it; the CI drift
# check (scripts/constitution_drift.py, .github/workflows/constitution-drift.yml)
# fails loud if the in-code model here drifts from the SCH-* at this tag.
# Bump these together with the compatibility.md row when adopting a new
# constitution release.
CONSTITUTION_VERSION = "0.1.3"
CONSTITUTION_TAG = "v0.1.3"
