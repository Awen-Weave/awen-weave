"""
Lleolydd cache — OGL bulk data clipped to Gwynedd, indexed for fast
spatial lookup, plus per-snapshot manifests for reproducibility.

Module layout:
  build.py    — orchestrator (download → load → index → bands → snapshot)
  bands.py    — UPRN status-band classifier (pure-function on input rows)
  snapshot.py — per-release manifest writer (sources + hashes + counts)
  sources/    — one module per OGL source (download + load + columns)

The cache lives at <data-dir>/seed/lleolydd/cache.duckdb. Snapshot
manifests live at <data-dir>/seed/lleolydd/snapshots/<release>/. Both
referenceable from claims via the `cache_snapshot_id` qualifier
(v0.1-schema.md §10 item 7.3) — a curator verification today is
reproducible against the exact OGL data state it was made against.
"""
from __future__ import annotations
