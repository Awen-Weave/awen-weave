# Craidd Foundation — Handover to Claude Code

**Date:** 2026-05-15
**From:** Cowork (foundation build session)
**To:** Claude Code (continuing BRA v2 and the rest of the build order)
**Branch:** `cowork/craidd-foundation`, committed at `14dec92`

## 1. What this is

The Craidd's foundation — the storage layer, the schema/validation
layer, and `craidd-init` — is built, sandbox-tested, and **deployed live
to the Pi**. This document is the orientation for picking up from here:
what the foundation provides, how to reach the deployed Craidd, how the
Building Research Agent integrates with it, and what is left to
reconcile.

It does not restate the architecture — `design/architecture.md` is still
the source of truth. This is the delta.

## 2. What the foundation provides

Three already-chartered components from `architecture.md`, implemented
under `src/` (layout note in §7):

### Schema layer — `src/craidd/schema/` (architecture.md §6.2)

Pure logic, no I/O, no DB access.

- `entity_types.py` — the 9 controlled entity types (`VALID_ENTITY_TYPES`).
- `qualifiers.py` — the qualifier vocabulary (`dialect`, `name_type`,
  `floor_scope`, `date_precision`), with closed vs open domains.
- `predicates.py` — the 58 v0.1 seed predicates as `PredicateDef`
  records; `SEED_PREDICATES`, `PREDICATE_REGISTRY`.
- `validation.py` — the validation contract: pure functions returning
  lists of error strings (empty = valid):
  - `validate_claim(claim, *, subject_entity_type, predicate_registry=PREDICATE_REGISTRY, deprecated_predicates=(), existing_active_predicates=())`
  - `validate_entity(entity_id, entity_type, visibility=None)`
  - `validate_predicate_def(pred)` and `validate_seed_predicates()`
  - `validate_qualifiers(qualifiers, pred)`

Everything is re-exported from the package:
`from craidd.schema import validate_claim, PREDICATE_REGISTRY, ...`

### Storage layer — `src/craidd/storage/` (architecture.md §6.1)

No business logic, no auth.

- `ddl.py` — `CRAIDD_DDL` and `PRAWF_DDL`: the v0.1 DDL transcribed
  faithfully from `v0.1-schema.md` §11, split across the two database
  files (a corruption in one cannot reach the other).
- `database.py` — thin connection helpers: `connect_craidd(path, *,
  load_spatial=True)`, `connect_prawf(path)`, `apply_ddl(conn, ddl)`,
  `database_is_empty(conn)`, plus the canonical path helpers
  `craidd_db_path()` / `prawf_db_path()` (default `DEFAULT_DATA_DIR =
  /srv/town-dataset`).
- `connect_craidd` loads DuckDB's `spatial` extension by default — it is
  required for the `claim.value_geom GEOMETRY` column.

### craidd-init — `src/cli/craidd_init.py` (cli-design.md §4.1)

The bootstrap CLI: creates both databases, applies the schema, seeds the
58 predicates. Idempotent against an empty DB; refuses a non-empty one.
Flags: `--data-dir`, `--actor`, `--dry-run`, `--json`. It is the one CLI
that touches the storage layer directly — it has to, because it creates
the storage everything else depends on.

### requirements.txt

`duckdb`, `pandas`. The repo had no dependency declaration before.

## 3. The deployed Craidd on the Pi

`craidd-init` was run on the Pi on 2026-05-15. There is now a live,
initialised, empty Craidd:

- `/srv/town-dataset/craidd.duckdb` — `entity`, `predicate`, `claim`
  tables plus the `current_claim` and `cy_coverage` views. 58 predicates
  seeded (`added_by = 'huw@arloesidolgellau.com'`). `entity` and `claim`
  are empty.
- `/srv/town-dataset/prawf.duckdb` — the `prawf_log` table, empty.
- The repo's working tree is at `/srv/town-dataset/` — rsync'd, **not a
  git checkout** (see §6).
- A Python venv is at `/srv/town-dataset/.venv` with `duckdb` and
  `pandas` installed.

To connect from code on the Pi:

```python
import sys
sys.path.insert(0, "/srv/town-dataset/src")
from craidd.storage import connect_craidd, connect_prawf
conn = connect_craidd("/srv/town-dataset/craidd.duckdb")
```

## 4. Pi access

- **Hostname:** `craidd` (Tailscale MagicDNS). **Tailscale IP:**
  `100.68.238.84` — reachable from anywhere on the tailnet.
- **SSH:** `ssh huw@craidd` — key-based.
- **Code + data:** `/srv/town-dataset/` (owned by `huw`).
- **venv:** `/srv/town-dataset/.venv` — invoke as
  `/srv/town-dataset/.venv/bin/python3`.
- The Pi also runs the SunFounder `pironman5` dashboard on port `34001`.

## 5. How the BRA integrates with the Craidd

The BRA produces draft claims that become proposals, that a curator
reviews into the Craidd. The foundation gives two integration points
**now** and one **later**.

**Now — validate against the schema layer.** Before the BRA queues a
draft claim, it can confirm the claim is schema-valid:
`from craidd.schema import validate_claim`. This catches predicate, type,
and qualifier errors at BRA time rather than at curator-review time.
Draft claims marked `pending_schema: v0.2` will not validate against the
v0.1 registry — that is expected; only v0.1-shaped claims should be
checked against it.

**Now — the seed predicate registry is the contract.**
`craidd.schema.PREDICATE_REGISTRY` is the authoritative list of which
predicates exist, their value types, cardinalities, and required
qualifiers. The BRA's claim extraction should target these names.

**Later — the proposal pipeline.** `craidd-propose`, `craidd-review`,
and the Write API are **not built yet** (see §8). Until they are, the
BRA continues to produce file-backed proposals via the v0
`client/craidd_client.py`, exactly as designed. When the pipeline is
built, those proposals get reviewed into the live `craidd.duckdb`. The
BRA does not — and per the architecture must never — write to the Craidd
directly.

## 6. Branch and git state

- **`cowork/craidd-foundation`** — the foundation commit (`14dec92`,
  12 files). Push to `origin` is Huw's call; the Pi got this branch's
  working tree by rsync, not by clone. Making the Pi a proper git
  checkout that can `git pull` is a deliberate follow-up.
- **`cowork/design-reconcile`** — parked design-doc edits that conflict
  with your branch (see §7).
- **`main`** — at `c928d02`: the HMLR seed data, the building research
  packs, and `.gitignore` updates, all committed this session.
- Your branch `claude/amazing-aryabhata-3414ef` was untouched throughout
  this session — the worktree isolation held.

## 7. Outstanding — for reconciliation

**`cowork/design-reconcile` — design-doc edits to merge into your
branch.** This branch (`e29cbfc`) holds Cowork-side edits to
`architecture.md`, `cli-design.md`, `v0.1-schema.md`, and a new
`building-research-agent.md`, parked rather than committed to `main`
because they overlap your active branch. Summary of the conflict: your
branch's BRA charter and v0.2 backlog items are the more advanced ones —
take yours; but the `v0.1-schema.md` "item 4 = proprietorship +
sale_record" content is **unique** (the HMLR work) and must not be lost
— it collides with your "item 4 = BRA v2 predicates" only on the number,
so renumber so both coexist. `cli-design.md` and
`building-research-agent.md` are Cowork-only — no conflict. You hold the
fuller BRA context, so you are the reconciliation owner.

**Layout-doc divergence.** The foundation is built under `src/`
(matching your `src/bra/`). But `CLAUDE.md` (its "Repo layout (target)"
section) and `v0.1-schema.md` §2 both still describe top-level
`schema/ api/ client/ cli/`. Those two layout sections need updating to
match the `src/` reality.

**Spec items surfaced while implementing `v0.1-schema.md`:**

- The §3.5 tables enumerate **58** predicates, but the prose summary
  says "52". The tables are authoritative; the count should be
  corrected.
- `predicate.description_cy` is `NOT NULL`, but §3.5 supplies English
  meanings only. All 58 predicates are seeded with a `"(Welsh
  description pending)"` placeholder rather than machine-translating —
  a proper Welsh pass (ideally Huw with his tutor) is needed.
- Minor: `street` and `area` entity types have no predicates in the
  §3.5 seed set; `building_type` is marked a "controlled enum" with
  values undefined; `listed_building_count` references an "`accessed_at`
  qualifier" that is not in the §3.2 qualifier vocabulary.

**Open question — Prawf genesis entry.** `craidd-init` creates
`prawf.duckdb` with an *empty* `prawf_log`. Whether the bootstrap itself
should be recorded as a genesis Prawf entry is deferred — it would need
the Prawf logger component (architecture.md §6.11), which was outside
the foundation's scope. Decide when that component is built.

## 8. What is NOT built yet

The foundation is storage + schema + `craidd-init` only. Still to build,
per `cli-design.md` §6 build order: `craidd-propose`, `craidd-review`,
`craidd-fetch`, `craidd-export`, `craidd-status`, then the Read API, the
Write API, the MCP server, the Prawf logger, and the curator-identity
layer. The `tests/` directory exists but is empty — the foundation was
verified by direct exercise this session; a proper test suite is a
near-term task.
