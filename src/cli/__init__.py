"""
src/cli — the craidd-* command-line tools (Llys role).

Thin command wrappers over the Craidd. Per cli-design.md §6 the build
order is: craidd-init, then craidd-propose, craidd-review, craidd-fetch,
craidd-export, craidd-status. Only craidd-init exists so far.

craidd-init is the one CLI that touches the storage layer directly — it
bootstraps the storage every other component depends on. The rest are
clients of the Read/Write APIs, never insiders (architecture.md §6.8).
"""
from __future__ import annotations
