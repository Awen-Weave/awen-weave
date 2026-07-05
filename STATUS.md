# Awen Weave — STATUS

**Last updated:** 2026-07-04 (constitution **drift-check ride-along** added to the working tree — fails loud if the in-code model drifts from the awen-constitution `SCH-*` at the pinned tag; verified locally, **not yet committed/pushed**. Prior headline: **v0.2.0 on PyPI**, full suite green (234).)

## What works
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
