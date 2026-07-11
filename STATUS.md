# Awen Weave — STATUS

**Last updated:** 2026-07-11 (**S1 federation spine built** — snapshot builder + stamp emitter + async request queue in `src/craidd/`; validates every record against the live awen-porth `constitution.validate` gate (offline vendored-schema fallback); committed Dolgellau gazetteer sample snapshot. Written on the Mac, **not yet committed/pushed** — Huw commits + deploys to craidd. Prior headline: constitution drift-check ride-along staged; **v0.2.0 on PyPI**.)

## S1 — Federation spine (2026-07-11, in working tree, not yet committed)
- **Deliverable A — snapshot builder** (`src/craidd/snapshot.py`): materialises a governed dataset into `snapshot-<iso>/{manifest,place-anchors,claims,stamps}.json`. Every record is `constitution.validate`-clean before anything is written; fail-loud with the full violation list and **no partial snapshot** on any invalid record. Deterministic output (sorted keys, stable ordering) so a committed snapshot diffs meaningfully.
- **Deliverable B — stamp emitter** (`src/craidd/gazetteer.py`): reuses the core `provenance_stamp` (no hand-rolled stamp) to emit one SCH-FEDERATION-001 stamp per federated read, plus `place_anchor()` (SCH-PLACEANCHOR-001) and `federated_name_claim()` (SCH-CLAIM-001 carrying `binding=federated` + `federated_from` + `source_ran_at`, derived from the same `SourceOfRecord` so stamp and claim can't drift). `source ran_at_utc` read from the source, never re-derived (verify-not-recall); `federated_utc` ≠ `ran_at_utc`.
- **`ran_at_utc` resolution order + self-declaring basis** (`src/craidd/ran_at.py`, reusable across every source): (1) the source's `run-manifest.json` `ran_at_utc` if it emits one → basis `run-manifest`; (2) else the source repo's **git HEAD commit time** (a real recorded source fact, verify-not-recall — not the builder's clock) → basis `git-head-commit`; (3) else **fail-loud**. The basis is declared in the stamp's `notes` free-text (`"ran_at_utc basis: …"`) so a Craffter can see whether the timestamp is authoritative or a proxy — no new Tier-1 property (SCH-FEDERATION-001 untouched). Git commit time can drift from actual build time, so an authoritative manifest is preferred once a source emits one.
- **Deliverable C — async request queue** (`src/craidd/queue.py`): the `requests/{inbox,claimed,done}` directory contract + the §6 request schema + a reader stub that lists/parses/validates inbox items; `claim()`/`mark_done()` lifecycle wired for S6.
- **Validation gate** (`src/craidd/validation_gate.py`): one `Validator` seam, two backends — `PorthValidator` (live MCP `constitution.validate`/`.version` on craidd `:8081`, the canonical build-time gate) and `SchemaValidator` (offline, vendored machine-layer schemas at `src/craidd/constitution_vendor/`, pinned tag). `default_gate()` prefers porth, falls back to offline. Manifest pins the **live** constitution version read from porth at build time (0.1.2), not a hardcode.
- **First target** (`src/craidd/readers/dolgellau.py` + `cli/craidd_snapshot.py`): the Dolgellau gazetteer reader materialises place-anchors from the Town Dataset buildings (UPRN + geometry + labels; `county_gss`=Gwynedd W06000002; ward/community/lsoa null until Lleolydd coverage). `craidd-snapshot dolgellau-gazetteer` runs it on craidd.
- **Proven live**: all three record kinds validate `valid=true` against live porth (constitution 0.1.2); a federated claim missing `source_ran_at` fails loud (confirmed against porth AND offline). Committed sample: `samples/dolgellau-gazetteer/snapshot-20260711T000000Z/` (3 anchors / 4 claims / 1 stamp, built from real craidd data, validated by live porth). 14 spine tests green (full suite 247 passed; the 2 `test_constitution_drift` failures are the pre-existing 0.1.0-pin vs local-0.1.2-tree gap, unrelated).
- **Next for S1**: Huw commits + pushes to `Awen-Weave/awen-weave`; deploy to craidd (`git pull` + `pip install -e .`); run `craidd-snapshot dolgellau-gazetteer` for the real snapshot; append signal; **hand S2 to the CHI chat** (`pull_tref.py` consumes the snapshot). §9 non-blocking open (signalled to ARL-021 / the Town Dataset chat): the Town Dataset to emit its own `run-manifest.json` (built_utc + inputs) so stamps carry an authoritative run time rather than the git-HEAD-commit proxy — `resolve_ran_at` picks it up automatically once present.

## What works (framework, pre-S1)
- Framework extracted (Brief 1 ✓)
- **v0.2.0 published to PyPI** ✓ — `pip install awen-weave==0.2.0`; Phase 2.1 `federated` binding + provenance contract in core (`craidd.federation`); 234 tests green
- **v0.1.0 published to PyPI** ✓ — `pip install awen-weave`
- **v0.1.1 published to PyPI** ✓ — `pip install awen-weave==0.1.1`; clean-venv smoke test on the Dolgellau Pi (Python 3.13.5) confirms `address.description_cy == 'cyfeiriad post'` and zero remaining `CY_PENDING` across all 60 predicates
- CI check workflow green ✓
- **Constitution drift-check ride-along** — *added to this working tree, verified locally, not yet pushed.* A CI job (`constitution-drift`) that fails loud if this package's in-code model drifts from the awen-constitution `SCH-*` it declares compatibility with (`craidd.CONSTITUTION_TAG = v0.1.0`). From constitution 0.2.0 the spec leads and this is the enforcement (compatibility.md / constitution-mcp brief §6). Two layers: an exhaustive **model diff** (entity types; confidence/status/visibility enums; the 14 qualifier keys; the 6 closed qualifier domains; both cross-rules — `co_signed_by⇒field_session_id` and `binding=federated⇒federated_from+source_ran_at`; required claim fields) and a behavioural **round-trip** (this package's validators vs the schema must agree on every fixture). Verified: passes clean on the 0.2.0 model; catches injected enum/cross-rule drift with a named finding + exit 1. Files: `scripts/constitution_drift.py`, `.github/workflows/constitution-drift.yml`, `tests/schema/test_constitution_drift.py`, `tests/schema/fixtures/constitution_roundtrip.json`, and new `CONSTITUTION_VERSION` / `CONSTITUTION_TAG` in `src/craidd/__init__.py`.
- **First downstream consumer (Dolgellau Town Dataset) now running on v0.1.0** ✓ — Pi at Arloesi Dolgellau pulled the migrated repo, installed awen-weave==0.1.0, framework imports resolve from site-packages, all 3 entry-point scripts work, operational data (51 claims / 12 entities / 60 predicates) intact through the migration. (Pi is one upgrade behind v0.1.1 — picks up the Welsh on its next `pip install --upgrade`.)

## What doesn't yet
- Namespace restructure (Option β proper) deferred to v0.2.
- BRA refactor + extraction (Brief 4) — `src/bra/` stays in town-dataset until instance-specific constants are lifted into config.

## Next
- **Push the constitution drift-check ride-along** (staged in this working tree — see "What works"). Commit + push so `constitution-drift` runs on push/PR to main. **Only remaining gate: the PAT** — if `Awen-Weave/awen-constitution` is private, add a fine-grained read-only secret `CONSTITUTION_RO_TOKEN` (contents:read on awen-constitution); else the workflow falls back to `github.token`. (The `v0.1.0` tag the workflow checks out already exists on the constitution remote, alongside `v0.1.1` — confirmed 2026-07-04, `git ls-remote --tags`. So the old "tag must exist" dependency is done.)
- **Re-pin discipline (drift check):** bump `CONSTITUTION_TAG` (`src/craidd/__init__.py`) + the `compatibility.md` pairing row together **only when the constitution's machine layer (`SCH-*/VOC-*/POL-*`) changes** — NOT on prose-only constitution releases. Worked example: constitution 0.1.1 = `SOV-TRANSFER-001 draft→active`, machine layer byte-identical to `v0.1.0`, so the pin **stays** `v0.1.0`. A re-pin is the deliberate signal that the enforced model itself moved. Convention recorded in the constitution's `compatibility.md` → "Machine-layer pin".
- **Phase 2.5 — consumers re-pin** to `awen-weave==0.2.0`: Wnion (refactor `federation.py` onto core imports — brief staged) and Dolgellau Energy `EGNI-001` (native on the core binding — note staged). Both in their own chats.
- Remaining v0.2 design questions parked: namespace restructure, BRA refactor + extraction.
- Brief 16 (Welsh place-names) — framework-module ingestion that targets this repo (not town-dataset) per the 2026-05-22 routing decision.

## Recent releases

- **2026-07-03 — v0.2.0** ✓ published — Phase 2.1: the `federated` binding + provenance contract promoted into the core (design/v0.1-schema.md §10 item 8). Additive over 0.1.1 — no API break. PyPI: <https://pypi.org/project/awen-weave/0.2.0/>. Tag: `v0.2.0`. PR #7. (Publish note: after the Huw-Lab→Awen-Weave org move the PyPI trusted publisher had to be re-registered to owner `Awen-Weave` before the workflow could upload.) New: `binding` closed qualifier domain (`asserted`/`measured`/`curated`/`derived`/`federated`, no default), `federated_from` + `source_ran_at` source-of-record keys, the federated cross-rule (fail-loud), and `craidd/federation.py` (`SourceOfRecord`, `FederatedResult`, `provenance_stamp`, `federation_qualifiers`, `now_utc`, `FederationError`). DDL shape unchanged (qualifiers travel in `qualifiers_json`; stamp in `prawf_log.payload_json`). Full suite green: **234 passed**. Unblocks Wnion's Craidd migration + Dolgellau Energy federation. _(IDR-006 Awen/phase-2/awen-weave-federated-binding-BRIEF.md)_

- **2026-05-22 — v0.1.1** — `description_cy` backfill (additive bilingual data; no API change). All 60 predicates now carry tutor-attested Welsh from Catrin Stephens' 2026-05-19 magic-link session. PyPI: <https://pypi.org/project/awen-weave/0.1.1/>. Tag: `v0.1.1`. Workflow run: 26294896889 (success). _(cowork-to-code-awen-weave-0.1.1-cy-republish.md)_

## Deferred from initial migration

- `src/bra/` (Building Research Agent) code stays in
  arloesidolgellau/town-dataset for now. Design notes for BRA ship
  in this repo (`design/bra-*`), but the implementation requires a
  refactor to lift instance-specific constants into config before
  extraction is clean. Deferred to a follow-up brief (Brief 4)
  after the v0.1 migration arc completes.

## Routing
- Cowork: ~/CoworkOutbox/IDR-006 Awen/
- Working patterns: github.com/Huw-Lab/working-patterns
- Constitution rule service: **awen-porth** (`~/Developer/awen-porth`, → Awen-Weave org) — the MCP service that serves awen-constitution (`get_rule`/`list_rules`/`validate`/`version`), pinned at `v0.1.0`. The drift-check above is its §6 ride-along on this side.
