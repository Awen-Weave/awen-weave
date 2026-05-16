# Entity Proposal Shape — design note

**Status:** committed 2026-05-16 (PR #7, commit `3dfef83`); cleanup pass applied in PR #8.
**Intended target path in repo:** `design/entity-proposal-shape.md`
**Triggered by:** Lleolydd design (`design/lleolydd.md` §12.B), but cross-cuts BRA, the energy study, and `craidd-propose`.
**Charter touch-points:** `architecture.md` §6.6 (Write API), §6.10 (Curator-identity layer), §6.11 (Prawf logger), §6.14 (BRA), §6.21 (Lleolydd), §6.22 (Proposal queue).

---

## 1. Why this exists

The proposal queue today carries **claim** proposals only. Every existing user — BRA, the energy study, `craidd-propose` (the CLI), the four real proposals on the Pi as of 2026-05-15 — adds *facts to entities that already exist*. Entity creation has been the bootstrap script's job: Tŷ Newyddion via `seed/buildings/ty-newyddion/bootstrap.py`, the four 2026-05-15 buildings via direct Code-side scripts.

Lleolydd needs to let curators create new buildings from the iPad. That can't go through a bootstrap script — it needs to be a curator-facing, provenance-tracked, no-self-acceptance proposal, just like every other Town Dataset mutation. So the proposal queue grows a second proposal type: **entity proposals**.

This is bigger than Lleolydd. Three other consumers benefit:

- **BRA v2.** When a sold-archive listing surfaces a building that doesn't exist as a Craidd entity, BRA today can't do anything with it (the draft sits in `still_ambiguous`). With entity proposals, BRA can submit a "this building probably exists" proposal alongside its claim drafts.
- **Energy study.** When the off-segment anchor work finds buildings outside the original 79-segment survey (Coleg Meirion Dwyfor on Ffordd Ty'n y Coed was the precedent — three blocks not in the survey), the same mechanism lets the energy study propose them rather than hand-bootstrap.
- **`craidd-propose` CLI.** Today it's claim-only. Add entity proposals so a curator at the kitchen table with a new building in mind can submit it without writing Python.

So this design covers the entity-proposal shape **once, properly**, for all four users.

---

## 2. Constitutional posture

The entity-proposal shape inherits all the existing claim-proposal disciplines — and one of them needs explicit re-statement here because entity proposals tempt the wrong shortcut:

- **Never writes to Craidd directly.** `craidd-review` is the only acceptance path. No "auto-create entity if X high-confidence claims arrive" shortcut.
- **No self-acceptance.** A curator who submits an entity proposal cannot accept it. (Lleolydd's co-sign path applies to entity proposals too — see §7.)
- **Provenance always.** Every entity proposal carries a source, a submitter identity, an evidence note, and (when applicable) a `cache_snapshot_id`.
- **The no-orphan rule** (new, specific to this shape): an entity proposal is never accepted in isolation if it would land an entity in Craidd with zero claims attached. Either it's bundled with at least one claim proposal that hangs off it (typical Lleolydd case: entity + initial geometry), or `craidd-review` rejects it with a "needs initial claims" error. Empty entities aren't useful and signal a bug somewhere upstream.

---

## 3. File shape

Sits in `/srv/town-dataset/proposals/` alongside claim proposals (file name disambiguates):

```
proposals/
  P-20260515-1430-a3f7c1e0.json         (existing claim proposal — unchanged)
  EP-20260516-1015-9c4d2b78.json        (new: entity proposal)
  P-20260516-1015-7e8a3f01.json         (claim proposal bundled with the EP above)
  P-20260516-1015-2b1d4c93.json         (another claim proposal in the same bundle)
```

The `EP-` prefix makes proposals discoverable at a glance and lets `craidd-review` filter by shape without parsing every file.

JSON shape:

```json
{
  "proposal_type": "entity",
  "proposal_id": "EP-20260516-1015-9c4d2b78",
  "submitted_at": "2026-05-16T10:15:23+01:00",
  "submitter": "huw@arloesidolgellau.com",
  "field_session_id": "FS-20260516-bridge-street-walk",   // optional
  "bundle_id": "B-20260516-1015-9c4d2b78",                // optional
  "entity": {
    "entity_type": "building",
    "names": [
      {"value": "Tŷ Newyddion", "language": "cy", "name_type": "current_local"},
      {"value": "Ty Newyddion", "language": "en", "name_type": "current_local"}
    ],
    "address_text": "Glyndwr Buildings, Bridge Street, Dolgellau, LL40 1AS",
    "external_refs": [
      {"scheme": "cadw", "value": "4938"},
      {"scheme": "uprn", "value": "200003184697"}
    ]
  },
  "source": {
    "source_id": "SRC-LLEOLYDD-20260516-1015",
    "source_type": "curator-on-site",
    "evidence_uri": "lleolydd://session/FS-20260516-bridge-street-walk/placement/9c4d2b78"
  },
  "note": {
    "cy": "Adeilad newydd ei adnabod yn ystod ymweliad maes Bridge Street.",
    "en": "Building newly identified during Bridge Street field walk."
  },
  "confidence": "high",
  "qualifiers": {
    "cache_snapshot_id": "lleolydd-cache-2026-05",
    "verification_method": "on-site"
  }
}
```

Three fields warrant explanation:

- **`bundle_id`** is the new piece. When an entity proposal arrives with bundled claim proposals (typical: Lleolydd's "Create new building" submits entity + initial geometry + initial name claims as one curator action), every proposal in the bundle carries the same `bundle_id`. `craidd-review` uses this to present and act on the bundle as a unit.
- **`entity.external_refs`** holds identifiers that aren't claims yet but are useful at acceptance time: UPRN (if any), Cadw / BLB references, OS TOID. These are *advisory* — they don't become claims unless the bundled claim proposals say so. They exist so `craidd-review` can do collision-detection ("this UPRN is already claimed by entity X — duplicate?") at review time.
- **`field_session_id`** is optional — present for Lleolydd-co-signed work, absent for async submissions (BRA, energy study, kitchen-table `craidd-propose`).

---

## 4. The bundle pattern

A "create new building" curator action is rarely just an entity. It's almost always entity + geometry + name(s) + address + maybe a UPRN claim. Submitting these as separate independent proposals would force the curator to wait for each to be accepted before adding the next — silly when they're conceptually one decision.

**The bundle.** All proposals submitted in one curator action share a `bundle_id`. The bundle is presented to `craidd-review` as a single review job:

```
Bundle B-20260516-1015-9c4d2b78 from huw@arloesidolgellau.com:
  EP-20260516-1015-9c4d2b78  Create entity (building) "Tŷ Newyddion / Ty Newyddion"
  P-20260516-1015-7e8a3f01   geometry POINT(-3.886 52.741) on this entity
  P-20260516-1015-2b1d4c93   address "Glyndwr Buildings, Bridge Street..." on this entity

Action:
  [a]ccept all   [r]eject all   [p]artial (review item-by-item)   [s]kip
```

**Acceptance.** A whole-bundle accept is atomic from the consumer's point of view: either the entity comes into existence with all its bundled claims, or none of it does. Internally, `craidd-review` accepts the EP first (creating the entity with a server-assigned `entity_id`), then immediately accepts the bundled claim proposals against that newly-created entity. If any single accept fails, the whole bundle rolls back and the proposals stay pending.

**Partial acceptance.** Sometimes the curator wants to accept the entity + geometry but defer a contested name claim. `[p]artial` walks the bundle item-by-item. The EP can be accepted on its own *if* at least one of its bundled claims is accepted with it (the no-orphan rule). Deferred items remain pending and can be reviewed later, attached to the now-existing entity by their original `subject_hint`.

**Rejection.** Rejecting the EP rejects the entire bundle. The curator can't keep the bundled claims around without an entity to attach them to.

---

## 5. Validation

A new `validate_entity_proposal()` pure function in the schema layer (`src/craidd/schema/validation.py`), exported alongside the existing `validate_proposal`. Validates the subset of the contract decidable without the live store:

- `entity_type` is a known type from the v0.1 (eventually v0.3) entity vocabulary.
- `names` is non-empty if `entity_type` is one that requires at least one name (all current entity types).
- For each `name`: `language` ∈ {`cy`, `en`}, `name_type` is a known qualifier value, `value` is non-empty.
- `address_text` is a string (no format validation; addresses are messy by design).
- `external_refs[].scheme` is from a known scheme registry (`uprn`, `toid`, `cadw`, `blb`, `nhle`, `osm-id`); values are well-formed for the scheme.
- `source` shape matches the existing claim-proposal source contract.
- `confidence` is one of the known confidence bands.
- `qualifiers` keys are all known v0.1+ qualifier names.

Does **not** check:

- Whether the entity already exists (DB-state — `craidd-review`'s job, with `external_refs` to help collision-detect).
- Whether bundled claim proposals are valid (each is validated separately by `validate_proposal`).
- Whether the bundle is internally consistent (e.g. names in claim proposals matching names in EP) — `craidd-review` handles consistency at acceptance time.

`validate_proposal` (existing) gains one tiny extension: when a claim proposal carries a `bundle_id` and a `subject_hint` of `"<bundle>"`, the subject is treated as deferred-to-acceptance-time rather than required-resolvable-now. The accept step resolves it to the just-created entity_id.

---

## 6. New client methods

`client/craidd_client.py` gains:

- **`propose_entity(submitter, entity_type, names, source, note, confidence, *, address_text=None, external_refs=None, qualifiers=None, field_session_id=None, bundle_id=None)`** → returns `proposal_id`. Validates via `validate_entity_proposal`; writes the EP file. If `bundle_id` is `None`, generates one.
- **`propose_bundle(submitter, entity_proposal, claim_proposals, *, field_session_id=None)`** → returns `bundle_id`. Generates a `bundle_id`, calls `propose_entity` and `propose_claim` (existing) for each item with that `bundle_id` set, returns the bundle id. Atomic at the *write-to-disk* level: if any single proposal in the bundle fails validation, no files are written.

Lleolydd uses `propose_bundle`. BRA, the energy study, and `craidd-propose` can use `propose_entity` standalone or `propose_bundle` for richer cases.

---

## 7. `craidd-review` extension

`craidd-review` gains:

- **Bundle awareness.** Lists pending work grouped by `bundle_id` rather than as a flat queue when bundles are present.
- **Entity-proposal acceptance.** Renders the EP (entity_type, names, address, external_refs, source, note). Action set: `[a]ccept` / `[r]eject` / `[s]kip`.
- **External-ref collision detection.** At render time, runs each `external_ref` against the live store. UPRN already claimed by entity X? Show the warning prominently. Cadw 4938 already claimed? Same. Helps the reviewing curator catch the dual-listing pattern (the Tŷ Newyddion / Glyndwr Milk Bar lesson from 2026-05-10) before creating a duplicate entity.
- **No-orphan enforcement.** If accepting an EP would land an entity with zero claims (because all its bundled claim proposals are being skipped or rejected), `craidd-review` blocks the accept with a "this would create an orphan entity" error.
- **Co-sign acceptance.** When the EP carries a `field_session_id` and the reviewing curator is a different identity from the submitter, the accept counts as a co-sign (per Lleolydd §12.A) — Prawf records both signatures and the session id. Standard async accept (no `field_session_id`) follows the existing single-curator path.
- **Atomic bundle accept.** `[a]ccept all on bundle` accepts the EP first (creating the entity), then accepts each bundled claim against it. Single transaction from the curator's perspective; rolls back on any internal failure.

---

## 8. Prawf treatment

Each entity proposal acceptance writes a Prawf entry:

```
event: entity-created
entity_id: TDS-DOL-B-00007
proposal_id: EP-20260516-1015-9c4d2b78
bundle_id: B-20260516-1015-9c4d2b78
submitter: huw@arloesidolgellau.com
acceptors: [richard@arloesidolgellau.com]      // co-signed; or [the-other-curator] for async
field_session_id: FS-20260516-bridge-street-walk    // present when co-signed
external_refs_resolved: {uprn: "200003184697", cadw: "4938"}
external_ref_collisions: []                    // anything caught by collision-detection
cache_snapshot_id: lleolydd-cache-2026-05
prev_hash: <chain>
this_hash: <chain>
```

Bundled claim acceptances write their normal Prawf entries, each carrying the `bundle_id` so the bundle can be reconstructed from Prawf in audit.

---

## 9. Edge cases

A short list of cases worth thinking through before implementation, with positions to argue from rather than answers:

- **A bundled claim is rejected after the EP is accepted.** The entity exists; the rejected claim doesn't attach. No rollback. Position: this is fine — entities accumulate claims over their lifetime, and rejecting one initial claim doesn't invalidate the entity's existence. The EP carried enough other claims to satisfy no-orphan.
- **The same building gets two competing EPs from two curators.** Same physical building, slightly different names / addresses. Position: external-ref collision-detection catches the obvious case (both EPs cite the same UPRN or Cadw ID). For pure-text duplicates without overlapping refs, this is no different from the existing claim-side problem of "is this the same subject?" — `craidd-review`'s reviewer-judgement loop is the answer. We don't try to auto-merge.
- **An EP cites a UPRN that a Lleolydd correction is about to move.** Race condition: curator A creates a new entity citing UPRN X; meanwhile curator B is mid-drag re-placing UPRN X on a different building. Position: this is exactly what the §12.A broadcast layer is for — B sees A's pending placement and can decide to wait or confer. The proposal queue doesn't need to handle this; the live coordination layer does.
- **An entity_type from a future schema version arrives in an EP.** E.g. `entity_type: "monument"` arrives before v0.3 schema lands. Position: `validate_entity_proposal` rejects it with a clear "unknown entity_type at current schema version" error. Proposals can't be allowed to forward-reference schema versions that aren't live, or the queue silently breaks at acceptance.
- **The cache snapshot referenced in an EP qualifier no longer exists** (someone deleted an old snapshot directory). Position: at acceptance, `craidd-review` warns but doesn't block. The verification was made against a real cache state at the time; the snapshot-id is the audit trail even if the data behind it has been pruned. (We probably shouldn't prune snapshots, but the queue shouldn't depend on them being immortal.)

---

## 10. Build order

1. **Schema layer.** `validate_entity_proposal()` + the `bundle_id` extension to `validate_proposal`. Pure functions, no DB. Cowork-side. *(small)*
2. **Client.** `propose_entity()` + `propose_bundle()` in `craidd_client.py`. Cowork-side. *(small)*
3. **`craidd-propose` CLI.** Add an `--entity` flag mode for kitchen-table entity creation. Cowork-side. *(small)*
4. **`craidd-review` extension.** Bundle awareness, EP rendering, collision detection, no-orphan enforcement, co-sign acceptance, atomic bundle accept. Code-side. *(meaty — biggest single piece of this work, and depends on `craidd-review`'s base implementation existing)*
5. **Lleolydd consumes it.** `propose_bundle` from `lleolydd-serve` write paths. Code-side, falls under Lleolydd Phase 3.

Items 1–3 can ship as a `cowork/entity-proposal-shape` PR independent of any consumer. Item 4 ships as part of `craidd-review`'s implementation (or as a fast-follow if `craidd-review` lands without bundle awareness — but bundle awareness is small enough to want in the first cut).

---

## 11. What this design deliberately doesn't cover

- **Entity update proposals.** This document is creation-only. Editing an existing entity (renaming, changing entity_type, retiring) is a separate proposal shape, deferred. For now, entity edits go through claim proposals on the entity's metadata predicates.
- **Entity deletion / retirement.** Also deferred. The constitutional position is that nothing is ever deleted from Craidd — entities can be retired (a `retired` claim, with `retired_at` and `retired_reason`), but their history is permanent. Retirement-by-proposal is a separate design.
- **Inter-entity reference proposals.** When a new entity should have a `relates_to_entity` claim back to an existing entity, that's a normal claim proposal in the bundle. Nothing special needed here.
- **The `_unresolved/` queue mechanic** that BRA v2 uses for listings whose subject can't be resolved. That stays at BRA's level — entity proposals are a different answer to a different question (BRA's `_unresolved/` says "I can't find a building for this listing"; an entity proposal says "I'm proposing a new building exists").

---

## 12. Open questions — resolved 2026-05-16

All five questions confirmed in the design-review pass:

a. **Bundle id format** → `B-<timestamp>-<short-uuid>`, generated by the client. Consistent with the existing `P-` and proposed `EP-` formats.

b. **Bundle-level rejection note** → Replicated across each rejected proposal in the bundle, so each rejection carries the reasoning standalone in audit.

c. **External-ref scheme registry** → Lives in the schema layer as a small enum, alongside the predicate registry. v1 schemes: `uprn`, `toid`, `cadw`, `blb`, `nhle`, `osm-id`. Extensible for v0.3.

d. **EP `subject_hint` nesting** → No. Design stays flat. Hierarchies emerge from `relates_to_entity` claims after acceptance. Revisit only if a concrete need surfaces.

e. **Co-sign timing** → A curator who joins a field session *after* an EP was submitted may still co-sign it, within the session's lifetime. Co-sign is about presence-in-session, not presence-at-the-instant-of-submission. The `session_id` pins the context.
