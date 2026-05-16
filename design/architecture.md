# Town Dataset — single architecture and the discipline that protects it

**Status:** the master architecture document for the Dolgellau Town Dataset — the first Awen instance. Everything we build must be on this page or in a charter linked from it. Anything not on this page is by definition not part of the system.
**Date:** 2026-05-10. Updated whenever a component is added, removed, or its role changes.
**Companion docs:** `constitutional-framework.md` (the ecosystem constitution this instance conforms to), `v0.1-schema.md` (data model), `cli-design.md` (CLI specs), `sources-backlog.md` (ingestion workflow), `pilot-ty-newyddion.md` (worked record), `ty-newyddion-review.html` (visualisation).

---

## 0. This document and the constitution

This is an **instance architecture**. It governs the concrete components of one Awen instance — the Dolgellau Town Dataset — and is the single master architecture document for *this* instance: if a component is not on this page, it is not in this instance's architecture.

Above it sits `constitutional-framework.md`, the **ecosystem-level constitution**. The constitution defines the governance and epistemic principles that hold across every Awen instance — computable trust, bounded authority, contradiction handling, supersession, longitudinal coherence. This document specifies how those principles take concrete form *here*, as components with charters and boundaries. The **Awen role map** (Llys / Craidd / IDRIS / Prawf / Craffter) is defined in the constitution (§2) and applied throughout this document.

Where this document and the constitution appear to disagree, the disagreement is a defect to be resolved deliberately: the constitution holds on governance principle, this document holds on this instance's concrete component design (constitution §0).

## 1. Purpose of this document

Past projects have sprawled. New ideas got built before their relationship to existing components was checked, components ended up overlapping, and a lot of later effort went on reconciliation work that should have been prevented up front. This document is the deliberate counter-pressure.

Its job is twofold. First, to hold a single, current map of every component the Town Dataset comprises — what each one does, what it consumes, what it produces, what it must not do. Second, to define the discipline that keeps that map honest as the system grows: a charter every new component must complete before it is built, and a small set of inviolable boundaries.

If a component is not on this page, it is not in the architecture. If a component on this page contradicts another, the contradiction is a bug in the architecture and must be resolved here before code touches it.

## 2. Awen role map

Every component performs exactly one Awen role. Components that try to span two roles are evidence that the role mapping is wrong, or that the component should be split. The five roles, with the components that perform them:

**Llys** (interaction, governance, accountability) — the way the system is talked to and the rules that govern change. Components: Read API, Write API, MCP server, the six CLI tools, the curator-identity layer.

**Craidd** (place-based trust core, curated and provenance-bound) — the canonical store of claims and the schema that shapes them. Components: Storage layer, Schema layer, Source registry, Evidence store.

**IDRIS** (reasoning and orchestration over Craidd + Prawf) — composing answers to non-trivial questions from underlying records. Components: none yet — deliberately deferred until the simple read interface has miles on it. When IDRIS components are built, they sit *above* the read API; they never reach into the storage layer.

**Prawf** (obligation and proof, evidence of process) — the hash-chained append-only audit trail. Components: Prawf logger, the public Prawf read endpoint, signature verification.

**Craffter** (advisory pattern-level learning) — observations that never mutate Craidd automatically. Components: none in v1, and explicitly walled off. When Craffter components are built they will run as separate processes that *read* the Craidd snapshot and produce advisory artefacts; they will have no write path into Craidd or Prawf.

The mapping is structural, not decorative. When we ask "where does this new thing belong?" the answer must name exactly one role.

## 3. Component register

The whole system as it currently stands. Each row is a charter in miniature; the longer charters are in §6.

| Component | Role | Consumes | Produces | Explicit non-goals |
|---|---|---|---|---|
| Storage layer | Craidd | DDL, validated writes from Write API | DuckDB files (`craidd.duckdb`, `prawf.duckdb`) | No business logic, no auth, no derived views |
| Schema layer | Craidd | predicate + entity-type registries | Validation contract used by every write | No I/O, no DB access — pure logic |
| Source registry | Craidd | source-entity claims | Resolution of source IDs to citation/visibility | Not a fetcher and not a triage system |
| Evidence store | Craidd | snapshot files, hashes | Filesystem under `evidence/` | No CDN, no remote sync, no mutation of received bytes |
| Read API | Llys | HTTP requests, snapshot exports | JSON responses, signed nightly export | No writes, no auth, no judgement |
| Write API | Llys | mTLS-authed HTTP, schema-valid payloads | Atomic writes to claims/proposals/Prawf | No reads beyond what's needed to validate writes |
| MCP server | Llys | MCP requests | Same answers as Read API, in MCP shape | Read-only — never writes |
| `craidd-init` | Llys | empty DB target | Bootstrapped DB with seed predicates and entity types | One-time tool — never used after v0 setup |
| `craidd-fetch` | Llys | source ID or new-source flags + URL | Snapshot, hash, archive URL, source-entity claims | Not a triage tool; not a proposal drafter |
| `craidd-propose` | Llys | candidate claim spec | Proposal file in `proposals/` + Prawf entry | Cannot accept its own proposal |
| `craidd-review` | Llys | pending proposals | Accepted/disputed/rejected claims + Prawf entries | Cannot create proposals; cannot fetch sources |
| `craidd-export` | Llys | claim + source tables | Signed JSON snapshot under `exports/` | Not a query tool; not a transformation layer |
| `craidd-status` | Llys | claim, proposal, Prawf state | Human-readable summary | Read-only — never writes; never long-running |
| Client library (`craidd_client.py`) | Llys (client side) | API endpoints | Pythonic wrappers for read + propose | Not a curator tool — cannot review |
| Curator-identity layer | Llys | mTLS certificates, role registry | Auth decisions for Write API and CLIs | Not a user database; not a public-facing identity service |
| Prawf logger | Prawf | every state-changing action | Append-only log entries with hash chain | Not deletable, not editable, not summarisable |
| Prawf read endpoint | Llys → Prawf | HTTP requests | Public log content + signature verification | No filtering that would hide actions; not for analytics |
| Town Dataset Review Dashboard | Llys (review) | claim + entity data (presently embedded; future: read API) | Per-claim cards + review-state JSON export | Not authoritative — it's a curator's review tool, not a data source |
| Building Research Agent (BRA) | Llys (contributor-side automation) | source-specific access (web, APIs, Nimble for v2); curator-approved allowlists; `seed/output/uprn-lookup.csv`; `craidd_client.py` | snapshots + hashes under `seed/`; draft claims; unresolved-subject queues; proposals submitted via the client library | Never writes to Craidd directly; does not paraphrase source material; does not auto-bind low-confidence subjects; does not republish copyrighted bytes |
| Lleolydd | Llys (curator-facing tool) | Craidd Read API; locally-staged OGL bulk corpus (OS Open UPRN / TOID / Linked Identifiers / INSPIRE / Zoomstack); curator identity from `craidd-review`'s identity layer | Proposals via `craidd_client.propose_claim()` and `craidd_client.propose_entity()` for `geometry`, `verified_building_toid`, `location_verification_status` (plus session/co-sign qualifiers); per-session audit CSVs under `seed/agents/lleolydd-runs/`; cache snapshots under `seed/lleolydd/snapshots/<release>/` | Never writes to Craidd directly (proposals only, including co-signed ones); does not auto-correct without curator confirmation; OGL-only at v1 (no Loqate/Ideal Postcodes); does not OCR or extract building footprints from aerial imagery; does not export PII; not a generic GIS; v1 UI scoped to `building` entities only |

That's twenty components, including the ones not yet built. A change to the schema reverberates here: every component touched by the change must have its row updated in the same commit.

## 4. Inviolable boundaries

These are the rules that, if broken, mean we have a different system than the one we're committed to. They are fewer than the temptations to break them.

1. **Craffter never writes to Craidd or Prawf.** Pattern-level observations are advisory, period. When learning components arrive, they read snapshots and emit separate artefacts.
2. **Reads never produce Prawf entries; writes always do.** The Prawf log records *change*. Read traffic is not change. Logging reads is operational telemetry, not Prawf.
3. **The Read API and Write API are separate processes on separate ports.** They share schema, not state. A bug in one cannot corrupt the other.
4. **No component reaches into the storage layer except through the schema layer.** The DDL and the validation contract are co-evolved.
5. **The energy study and other clients never read or write the DBs directly.** They go through the API or the client library. The Craidd's authority is the API surface, not the file format.
6. **Adding a new component requires updating this document in the same change.** A component that exists only in code is, by this document's definition, not yet in the architecture.
7. **A component performs exactly one Awen role.** If it doesn't, it should be split. If splitting feels wrong, the role mapping is wrong and needs fixing here first.

## 5. Change protocol — the fundamental check

Before any new component is built, before any existing component's role changes, before any new entity type or predicate is added, the change goes through the charter. The charter is six questions. They are intentionally cheap to answer for a small change and revealing for a large one.

**Charter form** — every component on this page has answered these:

1. **Awen role.** Exactly one of Llys / Craidd / IDRIS / Prawf / Craffter. State which.
2. **Why it exists.** One sentence. If you can't say it in a sentence, the component is wrong-shaped.
3. **What it consumes.** Inputs, in concrete terms — file paths, API endpoints, config values, claim shapes.
4. **What it produces.** Outputs, in concrete terms.
5. **What it explicitly does not do.** At least two things. The non-goals are the load-bearing part of the charter — they are how we prevent sprawl.
6. **What would change if it were removed.** A test of necessity. If the answer is "nothing important," the component is not necessary.

A new component without answers to all six questions is not part of the architecture. A component whose answers contradict another component's answers is a contradiction that must be resolved here before either ships.

The change protocol is enforced by review, not tooling, in v1. A future enhancement could be a CI check that parses the component register table and verifies every component has a charter. For now, the discipline is human and the curator is the enforcer.

## 6. Component charters

Each charter is short — the question is fitness, not exhaustiveness. The point is to answer the six questions and link to the implementation when it exists.

### 6.1 Storage layer

Role: Craidd. Why: holds the canonical claims, sources, and Prawf as durable files. Consumes: DDL from the schema layer, validated writes from the Write API. Produces: queryable DuckDB databases at known paths on the Pi. Explicit non-goals: no business logic, no auth, no derived analytical views. If removed: there is no canonical store, the system is not a system.

### 6.2 Schema layer

Role: Craidd. Why: defines what a valid claim, predicate, entity, and source look like. Consumes: predicate and entity-type definitions, qualifier vocabulary. Produces: a validation function used by every write path. Explicit non-goals: no I/O, no DB access, no auth — pure logic, pure functions. If removed: validation drifts across writers and the contract breaks down.

### 6.3 Source registry

Role: Craidd. Why: the catalog of source entities and their visibility, used by the Read API to filter citation detail and by `craidd-fetch` to identify existing sources. Consumes: source-type entity claims. Produces: lookup-by-id, visibility resolution, list-by-status. Explicit non-goals: not a fetcher, not a triage system, not a licence-management system. If removed: the visibility distinction collapses and private sources leak through the public API.

### 6.4 Evidence store

Role: Craidd. Why: durable filesystem location for raw source snapshots, addressed by source-id and date. Consumes: snapshot bytes from `craidd-fetch`. Produces: file paths under `evidence/sources/<source_id>/<date>.html` (or .pdf, .json). Explicit non-goals: no remote sync, no CDN, no mutation of bytes after write. If removed: provenance is unverifiable — citations point at URLs that may have changed.

### 6.5 Read API

Role: Llys. Why: the only public way to query the Craidd. Consumes: HTTP requests; snapshot exports for `/export/*`. Produces: JSON responses, signed nightly export. Explicit non-goals: never writes; no auth on read endpoints; no judgement (no scoring, no smart "best answer" — return the canonical view and let the consumer decide). If removed: the system has no consumers.

### 6.6 Write API

Role: Llys. Why: the only authenticated path that mutates the canonical store. Consumes: mTLS-authenticated HTTP requests with schema-valid payloads. Produces: atomic writes to claims, proposals, and Prawf. Explicit non-goals: no anonymous writes, no schema-bypass, no read endpoints beyond what's needed for write validation. If removed: nothing changes in the Craidd, ever.

### 6.7 MCP server

Role: Llys. Why: lets Claude (or any MCP client) query the Craidd in natural language. Consumes: MCP-shaped requests; delegates to Read API internally. Produces: same answers as Read API in MCP shape. Explicit non-goals: read-only; not a writer; not a proposer; not a translator. If removed: the live conversational demo of "ask in Welsh and get a sourced answer" disappears, but no canonical capability is lost.

### 6.8 The six CLIs

Charters for `craidd-init`, `craidd-fetch`, `craidd-propose`, `craidd-review`, `craidd-export`, and `craidd-status` are in `cli-design.md`. They share these structural commitments:

- Every CLI has exactly one purpose. None is a multi-tool; none reaches across paths.
- All writes go through the Write API, never direct to the storage layer. The CLIs are clients, not insiders.
- All actions that change state record an entry in Prawf via the Write API.
- All CLIs use the same `craidd_client.py` for transport — the CLI tools are thin command wrappers around the client library.

### 6.9 Client library (`craidd_client.py`)

Role: Llys (client side). Why: a single Python interface to the Read API and Write API, used by the CLIs and by external clients (energy study). Consumes: API endpoints, mTLS certificates. Produces: typed Python objects for entities, claims, and proposals. Explicit non-goals: cannot review proposals (only curators can, via the CLI authenticating through the Write API); does not cache writes; does not retry on schema errors. If removed: every client reimplements transport and validation, the contract drifts.

### 6.10 Curator-identity layer

Role: Llys. Why: enforces the two-tier curator/contributor distinction at the API layer. Consumes: mTLS certificates and a role registry on the Pi. Produces: auth decisions for Write API and CLIs (curator can accept proposals; contributor can only submit; nobody can self-accept). Explicit non-goals: not a user database, not a public-facing identity service, not OIDC-compatible. If removed: any contributor can self-accept and the two-tier split is fictitious.

### 6.11 Prawf logger

Role: Prawf. Why: the append-only hash-chained audit log. Consumes: every state-changing action from the Write API and CLIs. Produces: log rows with `prev_hash` and `this_hash`. Explicit non-goals: not editable, not deletable, not summarisable in-line — summaries live in Read API endpoints, not in the log itself. If removed: the system loses its proof layer and Awen's central claim collapses.

### 6.12 Prawf read endpoint

Role: Llys → Prawf. Why: exposes the log publicly and offers signature verification. Consumes: HTTP requests. Produces: log content with hash chain, plus a verification endpoint. Explicit non-goals: no filtering that hides actions, no analytics views (those belong in IDRIS or Craffter when they exist). If removed: the public-Prawf decision in v0.1 is undone.

### 6.13 Town Dataset Review Dashboard

Role: Llys (review). Why: lets a curator visually walk every claim before any of it goes canonical. Consumes: claim and entity data (currently embedded; future: from the Read API). Produces: per-claim cards plus a review-state JSON export. Explicit non-goals: not authoritative, not a public artefact, not a read replacement. If removed: reviews happen in YAML and the curator's eye glazes over.

### 6.14 Building Research Agent (BRA)

Role: Llys (contributor-side automation). Why: produces source-cited per-building research material and feeds it into the proposal queue for curator review, replacing curator handcraft for high-volume sources. One component with versioned scope: **v1** — historic-source research packs (Cadw, BLB, RCAHMW, council records, HMLR Price Paid); not yet built. **v2** — estate-agent listings (sale, rental, sold-archive narratives); active scope, design in `design/bra-v2-estate-agents.md` with pilot findings in `design/bra-v2-estate-agents-pilot.md`. v2 itself has three stages: **stage 1** agent discovery (`src/bra/listings/discover.py`), **stage 2** live-site ingest from a curator-approved allowlist via per-agent site-shape manifests, and **stage 3** archival ingest from the Internet Archive's Wayback Machine (`src/bra/listings/wayback.py`) for historic listings that have aged off live sites — a strictly-better citation surface because Wayback URLs are stable and the captured bytes never decay. Consumes: source-specific access (web, APIs, Nimble for v2 stages 1–2, Wayback CDX for stage 3); curator-approved allowlists (e.g. `seed/agents/dolgellau-agents.csv` for v2); `seed/output/uprn-lookup.csv` for subject resolution; `craidd_client.py` for proposal writes. Produces: per-source snapshot bundles under `evidence/listings/<agent_slug>/{live,wayback}/<id>/` each with raw HTML, metadata, sha256 hash, and Prawf-style run log; per-agent / per-source manifest CSVs under `seed/agents/wayback/<agent_slug>-<date>.csv` as the committed audit artefact; draft claims marked `pending_schema: v0.2` where v0.1 cannot model them; unresolved-subject queues for curator triage; proposals submitted via `craidd_client.propose_claim(...)` once schema supports them. Explicit non-goals: never writes to Craidd directly (proposals only); does not paraphrase source material (quote-with-citation only — verbatim text is the evidence record); does not auto-bind low-confidence subjects to buildings (the unresolved queue is the right default, not a failure mode); does not republish copyrighted bytes (image and floor-plan bytes captured under `restricted` visibility for curator review, never re-served by the Read API); does not auto-translate Welsh (honest `cy: null` where source is English-only); does not bypass robots.txt — both live-site and Wayback paths respect each host's stated policy absolutely. Runtime surface: a `bra` CLI with sub-commands per stage and source type (`bra listings discover` for v2 stage 1, `bra listings wayback` for v2 stage 3, `bra history` if v1 ships). The CLI's own detailed charter sits in `cli-design.md` once it is specified — this is a deliberate seventh top-level CLI alongside the six `craidd-*` CLIs, justified because BRA is a coherent research-and-propose workflow rather than a Craidd primitive. If removed: the dataset has no automated contributor pipeline; every claim arrives by curator handcraft; high-volume sources (estate-agent listings, historic-records inventories) cannot be tracked at the cadence they change, and historic listings pruned from agent sites are lost permanently.

### 6.21 Lleolydd — UPRN location-refinement tool

#### Awen role

**Llys** — curator-facing tool that produces proposals. Reads from Craidd, writes to the proposal queue, never to canonical claims or Prawf directly. Same constitutional posture as BRA (§6.14) and the energy study client.

#### Why it exists

Open-data UPRN-to-building matching (OS Open UPRN + OS Open TOID + OS Open Linked Identifiers + INSPIRE) gets ~70–90 % of the way in urban / regular housing and breaks predictably on rural and subdivided stock. The first-flow finding on 2026-05-15 surfaced the cost in the live system: energy-study `uprn-lookup.csv` carried "high confidence" UPRNs that turned out to be building-block references shared across 67–78 distinct addresses, blocking BRA subject resolution and forcing two of four candidate buildings to be bootstrapped with `uprn: null`. Without a curator-facing, provenance-tracked correction layer, downstream work — HMLR linkage, energy modelling, BRA, listed-building register cross-references — inherits silent errors. The CLIs are the wrong shape for this work: location correction is fundamentally visual and on-site.

#### Consumes

- Craidd Read API: building entities, address/name claims, current `geometry` claims, listing/sale_record cross-references, source visibility flags.
- Locally-staged OGL bulk corpus: OS Open UPRN, OS Open TOID, OS Open Linked Identifiers, INSPIRE Index Polygons, OS Open Zoomstack.
- Curator identity from the (forthcoming) `craidd-review`-shared identity layer.
- Optionally, in v1.x: aerial imagery layer (licence work pending).

#### Produces

- Proposals via `craidd_client.propose_claim()` for: `geometry` (point), `verified_building_toid`, `location_verification_status`, with qualifiers `verification_method`, `verified_at`, `cache_snapshot_id`, and (for co-signed field-session corrections) `field_session_id` + `co_signed_by`. See v0.1-schema §10 item 7.
- Proposals via `craidd_client.propose_entity()` (new, see `design/entity-proposal-shape.md`) when the curator creates a new building entity.
- Audit CSVs at `seed/agents/lleolydd-runs/<session-id>.csv` recording every session's placements, decisions, and signatures.
- Snapshot bundles at `seed/lleolydd/snapshots/<release>/` capturing the OGL bulk corpus state each correction was made against.

#### Explicit non-goals

- Does **not** write to Craidd directly. Every correction is a proposal subject to `craidd-review`, including co-signed ones (co-sign is an acceptance path, not a write path — see `design/lleolydd.md` §12.A).
- Does **not** auto-correct without curator confirmation. Auto-snap-to-TOID is a Craffter-shaped observation, not a Craidd fact, even at high confidence.
- Does **not** ingest commercial enrichment data (Loqate, Ideal Postcodes). OGL-only at v1, by decision (2026-05-16).
- Does **not** attempt OCR or building-footprint extraction from raw aerial imagery. That's a BRA-shaped agent if it ever exists.
- Does **not** export PII. Scope is buildings and locations, not occupants.
- Does **not** serve as a generic GIS. Scope is UPRN/TOID/INSPIRE alignment to Town Dataset entities.
- The v1 UI does **not** support entity types other than `building` (engine is type-agnostic; UI is scoped — see `design/lleolydd.md` §12.D).

#### What would change if removed

The Town Dataset would continue to grow, but with silently-wrong UPRNs propagating into HMLR linkage, sale-record attribution, energy floor-area cross-references, and BRA subject resolution. The known-wrong rural cases — farmsteads with point-on-yard, subdivisions with one-TOID-many-UPRNs, driveway-only addresses — would have no provenance-tracked correction route. Curator review would be the only available fix, and async review without a visual tool is impractical at the scale the dataset is heading toward (~190 Cadw listed buildings + ~1,400 surveyed buildings + the rural residue).

#### Versioned scope

- **v1 (current).** UPRN/TOID/INSPIRE alignment for Town Dataset `building` entities in Gwynedd. Online-first iPad PWA. MapLibre GL JS frontend. WebSocket/SSE pending-placement broadcast layer. Per-entity soft lock. Co-sign acceptance for synchronous field sessions. New-building creation via bundled entity_proposal + claim proposals.
- **v1.x (deferred).** Offline-capable PWA (tile pre-cache + IndexedDB queue + sync). Aerial imagery overlay. LIDAR overlay for ambiguous farmsteads. Bulk-triage list view. Welsh tutor pass on UI strings.
- **v2 (deferred to v0.3 schema decision).** Entity-type generalisation: monument / feature / open_space / infrastructure_asset modes enabled, on the back of v0.3 schema additions. `temporal_status` (existing/proposed/historic/removed) styling, enabling the energy modeller as a second user persona placing future-asset locations.

#### Inviolable boundaries (component-level)

In addition to the seven system-level boundaries already in `architecture.md`, Lleolydd specifically:

- Never mutates the OGL bulk cache from the curator UI. Cache rebuild is a separate `lleolydd-cache build` operation, run on a schedule, not on demand from the iPad.
- Never decides location verification status as a side-effect of a map view. Status is derived from claims + pending placements; the UI shows it but does not write it.
- Never co-signs as the originating curator. The no-self-acceptance principle is enforced at the API layer, not the UI layer.
- Never persists curator session state outside the broadcast layer. Sessions are ephemeral coordination; durable state is in claims, proposals, and Prawf.

## 7. Fitness checks

These are the ongoing tests that the architecture is still coherent. Run them mentally before every change; turn them into automated checks where possible.

1. **Role uniqueness.** Every component performs exactly one Awen role. Components that span two are evidence of misshape.
2. **Charter completeness.** Every component on this page has answered the six charter questions. None is half-charted.
3. **Single architecture.** No component reaches around the architecture (no direct DB access from clients, no read-side writes, no Craffter-into-Craidd).
4. **Boundary integrity.** None of the seven inviolable boundaries in §4 is broken.
5. **Reverberation discipline.** Every change to the schema or the component register has updated *every* affected row in §3.
6. **Non-goal honesty.** Each component's non-goals are real boundaries. If a non-goal is "we just won't bother to do that," it isn't a boundary; revise it.

## 8. What this document deliberately does not do

It does not set deadlines or sequencing. It does not list features. It does not predict what IDRIS or Craffter will look like when they exist. It does not police implementation details below the charter level — choosing FastAPI vs Litestar vs raw aiohttp is an implementation choice; it does not change the architecture.

If we resist the temptation to put any of those things in here, this document stays small enough to remain useful. The moment it becomes a sprawling estate of its own, the discipline has failed.
