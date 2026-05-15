# Town Dataset — CLI tool design

**Status:** design draft for the curator command-line tools. Each tool has been chartered against `architecture.md` before specification here. None of these tools is built yet.
**Date:** 2026-05-10
**Companion docs:** `architecture.md` (the discipline), `v0.1-schema.md` (data model), `sources-backlog.md` (workflow context).

---

## 1. Why six CLIs and not one

Past projects in this space have ended with a single sprawling tool that does too many things, plus three half-finished sibling tools that overlap. The architecture document sets the discipline that pushes back on this: every component performs exactly one Awen role and has explicit non-goals. The CLIs are no exception.

Six narrow tools, each a thin wrapper over `craidd_client.py`, each with a single job. Together they cover the curator's whole working surface; individually they are short to write, easy to test, and impossible to confuse for one another.

| CLI | One-line purpose |
|---|---|
| `craidd-init` | Bootstrap a fresh Craidd database with seed predicates and entity types. One-time. |
| `craidd-fetch` | Snapshot a web source into evidence and create or update its source entity. |
| `craidd-propose` | Submit a proposal claim. Used by curator (manually) and by client code (energy study). |
| `craidd-review` | Walk pending proposals and accept, dispute, or reject each. Curator-only. |
| `craidd-export` | Produce the signed nightly snapshot. Run by cron on the Pi. |
| `craidd-status` | Read-only summary of queue depth, recent Prawf, source coverage. |

Two of these (`craidd-fetch` and `craidd-review`) are the focus of this document. The other four get short charters at the end so the catalog is complete from the start — that itself is part of the discipline. We agree on the boundaries before writing a single line.

**One adjacent tool, designed separately.** The **Building Research Agent** (chartered in `architecture.md` §6.14, fully designed in `design/building-research-agent.md`) sits alongside the six CLIs but is not part of the same family. It uses `craidd_client.py` and `craidd-fetch`, produces output that feeds `craidd-review`, but is a longer-running automation rather than a thin command wrapper. It belongs to the same overall workflow but has its own scope, naming, and design document.

## 2. `craidd-fetch` — snapshot a source

### 2.1 Charter

**Awen role.** Llys. Curator action that creates evidence and source-entity claims; not a Craidd component itself.

**Why it exists.** A source must be snapshotted, hashed, and recorded with provenance before any claim can cite it. Doing this manually leads to inconsistency in evidence layout and missed archive submissions.

**What it consumes.** Either a known source ID (re-snapshot) or a URL plus minimal metadata to create a new source entity. Curator-key authentication.

**What it produces.** A snapshot file under `evidence/sources/<source_id>/<YYYY-MM-DD>.html` (or `.pdf`/`.json` depending on content type), a SHA-256 hash, an archive.org submission, and Write-API calls that record `accessed_at`, `file_hash`, and `archive_url` claims on the source entity.

**What it explicitly does not do.** It does not triage the source. It does not draft proposals from the content. It does not interpret what's in the page. It does not delete or replace older snapshots — multiple dated snapshots over time are valuable.

**What would change if removed.** Source ingestion would happen by curator handcraft, with predictable drift in evidence layout, hash discipline, and archive.org coverage.

### 2.2 Command shape

```
craidd-fetch <source_id> [options]                                # re-snapshot existing source
craidd-fetch --new --url=<url> --title=<title> --org=<org>        # new source
                  --licence=<licence> [--visibility=public]
                  [--source-id=<custom-id>]
                  [options]

Options:
  --no-archive             Skip archive.org submission (default: submit)
  --content-type=<mime>    Override auto-detection (html|pdf|json|other)
  --note=<text>            Free-text note to attach as a claim
  --dry-run                Fetch and hash, but make no Write-API calls
  --verbose                Print HTTP transcript and Write-API responses
```

### 2.3 Behaviour, step by step

1. Resolve the source. If `<source_id>` is given, look it up via the Read API (`GET /sources/<id>`); fail if it doesn't exist. If `--new` is given, generate a source ID (or use `--source-id`) and verify it doesn't already exist.
2. Fetch the URL with a 30-second timeout, following at most three redirects, recording the final URL.
3. Detect content type from `Content-Type` header (overridable). Save bytes to `evidence/sources/<source_id>/<YYYY-MM-DD>.<ext>`. If a snapshot for today already exists, append a `-NN` suffix.
4. Compute SHA-256 of the saved file.
5. Submit the URL to web.archive.org via the Save Page Now API; capture the resulting archive URL. If the submission fails, the fetch still succeeds — record `archive_url: null` with a note. Skip if `--no-archive`.
6. For a new source, call the Write API to create the source entity and its initial claims (`title_en`, `title_cy` if `--title-cy`, `organisation`, `url`, `licence`, `visibility`).
7. For every fetch (new or re-snapshot), call the Write API to add `accessed_at`, `file_hash`, and `archive_url` claims to the source entity. These are multi-cardinality claims — historical snapshots remain queryable.
8. Print a one-screen summary: source ID, file path, hash, archive URL, list of claims added.

### 2.4 Errors and edge cases

- **HTTP 4xx/5xx**: log to Prawf as a fetch attempt, write a `fetch_outcome` claim with status code, do not save bytes. The source entity *records the failed attempt*.
- **HTTPS certificate failure**: refuse, with a clear message. Do not bypass.
- **Robots.txt prohibits fetching**: refuse, with a clear message. Defer; a curator may decide to capture by other means and ingest manually.
- **Rate limiting from origin**: respect `Retry-After`. Don't auto-retry beyond three attempts.
- **Hash collision**: extremely unlikely; if observed, append timestamp suffix and warn the curator.
- **Disk full or write permission**: fail before any Write-API call. Atomicity matters more than completeness.

### 2.5 Identity and authorisation

Curator-only. The CLI authenticates with the curator's mTLS client cert against the Write API. Contributors do not run `craidd-fetch` — fetching produces source-entity claims, which are mutations of the canonical store.

## 3. `craidd-review` — walk the proposal queue

### 3.1 Charter

**Awen role.** Llys. The most explicitly Awen-shaped of all the CLIs: it is where human judgement enters the system as the source of truth.

**Why it exists.** Proposals from contributors and from `craidd-propose` accumulate in the queue. The curator must review each, decide its disposition, and have that decision signed and recorded. Without this tool the proposal queue is a static directory.

**What it consumes.** Pending proposals from `proposals/` on the Pi, accessed via the Read API. Curator-key authentication. Optional filters by source, subject, predicate, or submitter.

**What it produces.** Per proposal: an accepted, accept-as-competing, disputed, or rejected outcome. Each outcome is a Write-API call that mutates claims and writes a Prawf entry signed by the curator. The session log itself is also a Prawf entry capturing what was reviewed, when, by whom.

**What it explicitly does not do.** It does not create proposals. It does not fetch sources. It does not allow self-acceptance — a proposal whose submitter equals the current curator is offered for review by another curator only. It does not skip the Prawf log; even rejections are logged.

**What would change if removed.** Proposals never become canonical. The queue grows; the Craidd freezes at its bootstrap state.

### 3.2 Command shape

```
craidd-review [options]

Options:
  --filter-source=<id>          Only proposals citing this source
  --filter-subject=<id>         Only proposals about this entity
  --filter-predicate=<name>     Only proposals on this predicate
  --filter-submitter=<id>       Only proposals from this contributor
  --filter-since=<date>         Only proposals submitted after this date
  --batch-mode                  No prompts; require --action and --filter
  --action=<accept|compete|dispute|reject>   Used with --batch-mode
  --reason=<text>               Required for dispute and reject; used with batch
  --limit=<n>                   Stop after n proposals
  --resume                      Skip proposals already reviewed in a prior interrupted run
  --dry-run                     Walk the queue and print actions, but make no Write-API calls
```

### 3.3 Interactive walk

Run with no arguments, the tool walks the queue one proposal at a time. For each:

```
─────────────────────────────────────────────────────────────────────────────
PROPOSAL  P-0190f9...                                  submitted 2026-04-12
SUBMITTER arloesi-dolgellau-energy-study (contributor)
SUBJECT   TDS-DOL-B-00027  Eldon Square commercial townhouse
PREDICATE floor_area_m2
VALUE     142.6
SOURCE    TDS-DOL-SRC-DOL-ENERGY-2026 (PUBLIC, OGL)
          "Dolgellau Energy Study EPC match"
EVIDENCE  file://evidence/dol-energy/seg27_b27.json
CONFIDENCE medium
NOTE      Derived from EPC match audit, fuzzy score 0.91.

EXISTING CLAIMS on (TDS-DOL-B-00027, floor_area_m2):
  (none)

[a]ccept canonical  [c]ompete  [d]ispute existing  [r]eject  [s]kip  [q]uit
> _
```

The curator types one letter. For `accept`, the proposal becomes a live claim; for `compete`, both the proposal and any existing canonical stay active and the predicate gains a contradiction; for `dispute`, the existing canonical is marked `disputed` and the proposal enters as a new active claim; for `reject`, the curator is prompted for a reason and the proposal moves to `proposals/rejected/`. Every action is signed and Prawf-logged.

`skip` defers the proposal to a later session; `quit` ends the session and writes a session-summary entry to Prawf.

### 3.4 Batch mode for routine corrections

The energy study, in steady state, will produce many small geometry corrections — postcode-centroid points being superseded by better-resolution OS UPRN points. These are low-controversy and high-volume. Batch mode handles them:

```
craidd-review --batch-mode --action=compete \
              --filter-source=TDS-DOL-SRC-OS-UPRN-2026 \
              --filter-predicate=geometry \
              --reason="OS UPRN higher-confidence supersedes postcode centroid"
```

This walks every matching proposal, accepts it as a competing claim, and writes a single batch Prawf entry that summarises the action and lists every proposal accepted. Batch acceptance is allowed only for predicates that the curator has flagged as "batchable" in the predicate registry — a small set, deliberately. `listed_grade` is not batchable; `geometry` is.

### 3.5 Self-acceptance prevention

Before offering a proposal to the curator, the tool checks whether the submitter equals the current curator. If yes, the proposal is held back with a message: "Proposal P-... was submitted by you. Awaiting another curator." This is the schema-enforced two-tier rule (architecture §4 boundary 6) acting at the CLI surface.

In v0 with one curator (Huw) and Huw owning Tŷ Newyddion, this means proposals about Tŷ Newyddion submitted by Huw cannot be accepted by Huw. Either a second curator is added (Richard, or a named Arloesi Dolgellau person) or those proposals stay pending until one is. This is a deliberate friction.

### 3.6 Errors and edge cases

- **Schema validation fails on accept**: the proposal is invalid in the current schema (e.g. uses a deprecated predicate). Curator is shown the validation error and offered the choice to dispute, reject, or hold for schema update.
- **Source visibility mismatch**: a proposal cites a `private` source but tries to make a public claim. Allowed, but the read API will mark the claim's source as "internal" — the curator is shown what that will look like before accepting.
- **Network drop mid-session**: the session-summary Prawf entry is written on quit OR on the next successful action. On reconnect, `--resume` skips proposals already actioned.
- **Two curators reviewing the same queue concurrently**: the Write API is the lock holder; the second curator's accept attempt on a proposal already accepted gets a clear "already actioned" error.

### 3.7 Identity and authorisation

Curator-only. mTLS-authenticated to the Write API. Every action is signed with the curator's key, and the signature ends up in the Prawf entry — externally verifiable.

## 4. The other four CLIs — short charters

These are not specified in detail here; they are listed so the architecture and the catalog are complete from the start. Detailed specs follow when they are next on deck.

### 4.1 `craidd-init`

Llys. Bootstraps a fresh DB with the v0.1 schema, seed predicates, and the controlled entity-type list. Run once on the Pi at setup. Idempotent against an empty DB; refuses to run against a non-empty one. No re-init in production — that's a destructive operation that should be a separate, conspicuously-named tool if ever needed.

### 4.2 `craidd-propose`

Llys. Submits a proposal claim from a JSON or YAML file, or from interactive prompts. Used by the curator manually and by client code (energy study) via the same library underneath. Cannot accept its own proposal. Written before `craidd-review` because there's no point reviewing an empty queue.

### 4.3 `craidd-export`

Llys. Generates the signed nightly snapshot under `exports/`, computes a digest, and writes a Prawf entry recording the digest. Run by cron at 03:00 local. Read-only against claims; write-only against `exports/` and Prawf. The signed digest is what consumers verify against — the snapshot is not authoritative, the live API is.

### 4.4 `craidd-status`

Llys. Read-only. Prints to terminal: queue depth (pending proposals by source/submitter), recent Prawf events (last N), source coverage (claims per source, queued sources awaiting fetch), Welsh coverage (`cy_coverage` view), and any deprecated predicates still in active use. Used by the curator to decide what to do next. Never long-running, never blocking, never makes decisions — it surfaces them.

## 5. Shared infrastructure

All six CLIs are thin command wrappers. They share four pieces of underlying machinery:

- **`craidd_client.py`** — the Python client library. All transport, all auth, all schema validation lives here. CLIs do not call HTTP directly.
- **A common argument parser style** — every CLI uses the same flag conventions (`--filter-*`, `--dry-run`, `--verbose`, `--reason`). This is enforced by code review, not by an abstract base class — the conventions are simple enough to remember, and a base class would be premature.
- **A common output style** — every CLI prints a one-screen summary of what it did. Successful actions exit 0; errors exit non-zero with a short message. JSON output (`--json`) is available on every CLI for tool composition.
- **Prawf signing** — every state-changing action is signed with the curator's key before transmission. The CLI never trusts the server to sign; the server trusts the signature on receipt.

If a future CLI needs to reach around any of these — a curator-side logic that the client library can't express, a side-channel write that bypasses the Write API — that is a sign the architecture has drifted. Charter the new component first; if the charter holds, extend the client library, not the CLI.

## 6. Build order

1. `craidd_client.py` (library) and `craidd-init` together — without these, nothing else can be built or tested.
2. `craidd-propose` — gives us a way to make proposals, even before review exists. Manual-only at first.
3. `craidd-review` — turns the queue into canonical claims.
4. `craidd-fetch` — automates source ingestion. Until this exists, sources are created via `craidd-propose` with manually-attached snapshots.
5. **Building Research Agent** — once `craidd-fetch` and `craidd-review` exist, the Agent ties them together for per-building research. See `design/building-research-agent.md`. This is the point at which the dataset's growth rate changes from one-evening-per-building to one-batch-per-evening.
6. `craidd-export` — only matters once there's enough Craidd content to export; can be the last thing.
7. `craidd-status` — small and useful at any point; build whenever the curator's working day demands it.

The order is deliberate: the queue and the review loop come before automation. We learn the workflow by hand on a small set of claims before building the tools that scale it. The Building Research Agent slots in where automation begins to pay off — once the foundations are tested manually, the Agent makes the manual pattern repeatable.

## 7. Open questions for review

1. **Batchable predicates** — which predicates can be accepted in batch via `craidd-review --batch-mode`? My starting list: `geometry` (when superseding from a higher-confidence source), `accessed_at`, `file_hash`, `archive_url`. Listed-status, naming, and event predicates are *not* batchable. Worth challenging.
2. **Re-snapshot cadence** — should `craidd-fetch` refuse to re-snapshot a source if the last snapshot is fewer than N days old, unless `--force`? Argument for: discourages accidental hammering of source sites. Argument against: curator should decide. I lean towards a soft warning rather than refusal.
3. **Anonymous proposals** — v0.1 says all proposals come from authenticated submitters. Should there be a public proposal form (web) for community contributions? My answer for v1: no. Public contribution is a v2 feature; opening that door is a substantial governance change that deserves its own charter.
4. **CLI-to-CLI composition** — should `craidd-fetch` ever auto-trigger `craidd-propose` once a source is snapshotted? My answer: no. The two are charterly separate. Let a wrapper script compose them if a curator wants that.
5. **Welsh-language CLI** — should the CLI commands and prompts be available in Welsh? Symbolically valuable. Practically hard at v1 — defer to v2 with a clear note that the i18n hooks are baked in from the start (string tables, no embedded English in core logic).

These five items are the next round of discussion before any of the above is built.
