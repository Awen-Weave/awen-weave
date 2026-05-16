"""
Lleolydd — UPRN location-refinement tool (architecture.md §6.21).

Phase 1 of Lleolydd is the OGL-data cache build: download OS Open UPRN,
OS Open TOID, OS Open Linked Identifiers, INSPIRE Index Polygons, and OS
Open Zoomstack; clip to the Gwynedd boundary; index into a DuckDB
spatial database; compute UPRN status bands (auto-snapped / unsnapped /
contested / non-postal). The `verified` band is left empty in Phase 1
— it depends on the Craidd read API which Phase 2 wires in.

Subsequent phases (per design/lleolydd.md §6):
  Phase 2 — read-only viewer (backend + MapLibre PWA).
  Phase 3 — override workflow + WebSocket/SSE broadcast + co-sign
            acceptance + new-entity creation. Blocked on craidd-review.
  Phase 4 — bulk-triage view.
  Phase 5 — deferred (offline PWA, aerial, LIDAR, v0.3 entity types).
"""
from __future__ import annotations

LLEOLYDD_VERSION = "0.1"
