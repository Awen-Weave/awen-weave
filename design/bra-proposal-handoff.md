# BRA → proposal-queue handoff — design note

**Status:** design of record. The three decisions in §3 were approved 2026-05-15 and the Cowork-side of §4 is built — `value_from_claim_columns` in the schema layer, `validate_proposal` wired into `craidd_client.py`, and the `propose_from_claim` adapter method. The remaining piece is the BRA-side loop (§4 step 3), which is Code's, in `src/bra/`.
**Date:** 2026-05-15
**Companion docs:** `craidd-propose-spec.md` (the proposal format and its validation), `architecture.md` §6.14 (the BRA charter — names the intended submission path), `building-research-agent.md` / `bra-v2-estate-agents.md` (BRA design), `client-contract.md` (the proposal format `craidd_client.py` owns).

---

## 1. The seam

BRA v2 now produces draft claims on disk — 27 live + 1,636 historic = 1,663, each citing a sha256-hashed source snapshot. `craidd-propose` is built. They do not yet join, because the two sides were built to two different shapes, each correct for its own spec:

- **BRA emits *claim*-shaped, batched drafts.** `src/bra/listings/claims.py`'s `DraftClaim` mirrors a `claim`-table row: type-tagged value columns (`value_real`, `value_geom`, `value_en` / `value_cy`, …), a `subject_id`, a bare `source_id` string. Each output file holds an *array* of drafts for one listing.
- **`craidd-propose` ingests *proposal*-shaped, single records.** One untyped `value`, a `subject` or `subject_hint`, a `source` mapping, one proposal per file — the `craidd_client.py` proposal format.

Neither side is wrong. BRA was wired to `validate_claim`; `craidd-propose` to the proposal contract. The join between them was never built — this note designs it.

## 2. What can actually flow now

Before the mechanics: a volume expectation worth setting. BRA splits its drafts into v0.1-shaped (predicates that exist today — in practice `address`, `geometry`, `floor_area_m2`) and `pending_schema: "v0.2"` (predicates v0.2 will introduce — `tenure`, `bedrooms`, `epc_band`, `council_tax_*`, `listing_events`, and the rest). `validate_proposal` correctly rejects every v0.2-pending draft as an unknown predicate.

So "the 1,663 flow" is really **"the v0.1 slice flows now; the v0.2-pending bulk waits on the v0.2 schema."** That is the schema discipline working as intended, not a fault — but it means the handoff built now serves a minority of the current drafts, and its real payoff arrives with v0.2. Worth building anyway: the v0.1 slice is the proof the pipeline works end to end, and the adapter is unchanged when v0.2 lands.

## 3. Three decisions

### 3.1 Where the claim→proposal adapter lives

**The question.** Something must collapse BRA's type-tagged `DraftClaim` (many `value_*` columns) into the proposal format's single `value` (with bilingual → a `{cy, en}` mapping). Where?

**Options.** (a) BRA-side — a `to_proposal()` on `DraftClaim`; (b) client-side — a converter in/near `craidd_client.py`; (c) schema-side — a pure helper next to `validate_proposal`.

**Recommendation: split it.** The type-tagged-columns → single-value collapse is generic Craidd knowledge — it is the inverse of `validation.py`'s `_VALUE_COLUMNS` map — so a small pure helper belongs in the **schema layer**. The assembly of a full proposal dict belongs in **`craidd_client.py`**, which already owns the proposal format. BRA imports neither concern — it just calls the client. This keeps the disjoint-tree discipline intact: the foundation and client stay generic, BRA depends on them and not the reverse.

### 3.2 Batch mode on the CLI, or the library path

**The question.** BRA produces batches (an array per listing); `craidd-propose` takes one proposal per file. Does the CLI grow a batch mode, or does BRA submit a different way?

**Options.** (a) `craidd-propose` grows `--from-file` accepting an array, or a `--batch` flag; (b) BRA goes through `craidd_client.propose_*()` directly, in a loop, and `craidd-propose` stays single-record and human-facing.

**Recommendation: the library path (b).** `architecture.md` §6.14 already names BRA's submission route as "proposals submitted via `craidd_client.propose_claim(...)`" — the library, not the CLI. `craidd-propose` is the curator's *manual* entry point; it has no reason to carry BRA's batching. BRA loops over each draft file's array and calls the client per draft. The loop lives in `src/bra/` because the batching is BRA-workflow-specific.

### 3.3 Wiring `validate_proposal` into `craidd_client.py`

**The question.** `craidd_client.propose_claim()` today writes a proposal file without schema validation — its v0 docstring explicitly defers validation to review. The schema layer now *has* `validate_proposal`. Does the library call it?

**Options.** (a) Leave the library unvalidated, validate only at review; (b) wire `validate_proposal` into the library's write path so both entry points — CLI and library — validate at submit.

**Recommendation: wire it in (b).** The "validation happens at review" line was a stopgap from before the schema layer existed. With BRA about to push volume through the library path, catching a malformed draft at submit rather than review is exactly the guarantee `validate_proposal` was built for. It is a small, contained change to one method.

## 4. The recommended path, in one picture

1. **Schema layer** — add a pure helper beside `validate_proposal` that collapses a claim's type-tagged `value_*` columns into the single proposal `value` (bilingual → `{cy, en}`).
2. **`craidd_client.py`** — wire `validate_proposal` into the existing `propose_claim()` write path; add a `propose_from_claim(claim_mapping, …)` method that uses the schema helper, then writes through the same validated path.
3. **BRA** — a step in `src/bra/` loops over each draft file's `draft_claims` array, skips `pending_schema: "v0.2"` entries, and calls `craidd_client.propose_from_claim()` for each v0.1-shaped draft.
4. **`craidd-propose` (the CLI)** — unchanged. Stays single-record and human-facing.

Result: both submission paths validate at submit; the proposal format stays single-sourced in `craidd_client.py`; the v0.1 slice flows now; the adapter is unchanged when v0.2 unlocks the rest.

## 5. Implementation details to settle (not curator decisions — flagged so they are not forgotten)

- **Qualifier reconciliation.** BRA's `DraftClaim` can carry non-v0.1 qualifiers (e.g. `geometry_source`, `floor_area_basis`). BRA already has `_split_qualifiers` for this; the adapter must apply the same split so only v0.1-vocab qualifiers reach `validate_proposal`, with the rest dropped or preserved in the proposal's `note`.
- **Unresolved subjects do not flow.** BRA emits a `TDS-DOL-UNRESOLVED-…` placeholder `subject_id` when subject resolution fails. Those drafts should *not* become proposals — they stay in BRA's unresolved-subject queue (the charter's design) until resolution. Only resolved-subject drafts convert.
- **Source-entity existence.** A proposal cites a source by id; `craidd-review` checks that the source entity exists. Whether BRA's `TDS-DOL-SRC-AGENT-…` source entities are in the Craidd yet is a `craidd-fetch` / `craidd-review` concern — noted here only so it is on the radar before the first BRA batch is reviewed.

## 6. What this note does not decide

It does not touch the v0.2 schema work that unblocks the bulk of BRA's drafts — that is a Track A schema-version charter of its own. It does not design `craidd-review`'s handling of a high-volume BRA batch (batchable-predicate policy, the `proposals/` vs energy-study `proposals-out/` reconciliation in `craidd-propose-spec.md` §7). It assumes BRA's draft-file on-disk format is stable; if Code is still changing it, the adapter waits on that settling.
