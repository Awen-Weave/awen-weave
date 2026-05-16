# Lleolydd — UPRN location-refinement tool

**Status:** design draft, 2026-05-16. Not yet committed.
**Intended target path in repo:** `design/lleolydd.md`
**Charter target:** `architecture.md` §6.21 (new component, register count 19 → 20).
**Companion CLI/service:** to be added to `cli-design.md` as a new top-level tool alongside `bra`, `craidd-*`.

---

## 0. Name

**Lleolydd** — Welsh for "locator". Pronounced *llay-ol-ith*. Sits next to Llys / Craidd / IDRIS / Prawf / Craffter / BRA in the Awen family of named components, keeps the Welsh-rooted positioning, and reads as a noun for a tool the curator uses rather than an autonomous agent.

**Locked 2026-05-16.** Alternatives considered (`Cyfeirnod`, `Sicrhau Lleoliad`, English `LRA`) but Lleolydd is the chosen name.

---

## 1. Why this exists

Two converging facts from the current state of the Town Dataset:

1. **UPRN inaccuracy is already a blocker, not a future problem.** The 2026-05-15 first-flow finding identified that the energy study's `uprn-lookup.csv` contains "high confidence" UPRNs that are actually building-block references shared across 67–78 distinct addresses (EPC-API-derived, not unit-level). Two of four candidate buildings in the first BRA bootstrap had to be flagged `uprn: null` because of this. 303 BRA drafts remain `still_ambiguous` for related reasons. HMLR cross-references built on those UPRNs would be silently wrong.

2. **The data path to fix this is already chosen but not yet implemented.** The 2026-05-10 OS Places gap analysis resolved that the durable, OGL-licensed route is OS Open UPRN + OS Open TOID + OS Open Linked Identifiers + INSPIRE polygons. That decision stands. What it lacks is a human-in-the-loop overlay for the cases where the open-data combination doesn't reach the answer — large farmsteads where the point sits on a yard, subdivided town-centre properties where one TOID carries multiple UPRNs, long driveway-only addresses, non-postal features.

The briefing document (`UPRN History and Enhancement.docx`, 2026-05-16) is explicit about this last gap: "*the case of farms and dispersed rural properties where the UPRN sits in a yard or driveway rather than on a specific dwelling — that's where local knowledge or LIDAR/aerial-imagery-based building extraction still adds genuine value.*" Rural Gwynedd is the worst-case geography for this, and the Town Dataset is the demonstrator that should expose and solve it.

Lleolydd is the curator-facing tool that turns local knowledge into provenance-bound corrections.

---

## 2. Awen role and charter

Six-question charter (per `architecture.md` discipline):

**Awen role.** Llys (curator-facing tool that produces proposals). Reads from Craidd; writes to the proposal queue; never to canonical claims or Prawf directly. Same discipline as BRA and the energy study.

**Why it exists.** Open-data UPRN-to-building matching gets you ~70–90 % of the way in urban / regular housing and breaks predictably on rural and subdivided stock. Without a verified, provenance-tracked correction layer, downstream work (HMLR linkage, energy modelling, BRA subject resolution, listed-building register cross-references) inherits silent errors. Existing CLIs aren't the right shape: location correction is fundamentally visual and on-site.

**Consumes.**
- Craidd Read API for: building entities, address/name claims, current `geometry` claims, listing/sale_record cross-references where present, source visibility.
- Locally-staged OGL bulk data: OS Open UPRN, OS Open TOID, OS Open Linked Identifiers, INSPIRE Index Polygons, OS Open Zoomstack (basemap tiles).
- Optionally: aerial imagery layer (OS OpenData Vector Map District, or Bing Aerial via standard tile XYZ — licensing TBC per layer at review time).

**Produces.**
- Proposals via `craidd_client.propose_claim()` for: `geometry` (point), `verified_building_toid` (new predicate, v0.2 dependency), `location_verification_status` (new predicate, v0.2 dependency), and `location_verified_at` / `location_verified_by` qualifiers.
- Audit CSVs under `seed/agents/lleolydd-runs/` recording every session (entity_id, before/after point, before/after TOID, decision band, curator, timestamp, evidence URIs).
- A snapshot of the OGL bulk corpus used in each release at `seed/lleolydd/snapshots/<release>/` so reasoning is reproducible after OS updates.

**Explicit non-goals.**
- Does **not** write to Craidd directly. Every correction is a proposal subject to `craidd-review`.
- Does **not** auto-correct without curator confirmation. A pure auto-snap-to-TOID is a Craffter-style observation, not a Craidd fact — even when confidence is high.
- Does **not** ingest commercial enrichment data (Loqate, Ideal Postcodes). OGL stack only, by decision.
- Does **not** attempt OCR / building-footprint extraction from raw aerial imagery (defer; that's a BRA-shaped agent if needed).
- Does **not** export PII; the dataset is buildings and locations, not occupants.
- Does **not** serve as a generic GIS. Scope is UPRN/TOID/INSPIRE alignment to Town Dataset entities.

**What would change if removed.** The Town Dataset would continue to grow, but with silently-wrong UPRNs propagating into HMLR linkage, sale-record attribution, energy floor-area cross-references, and BRA subject resolution. The known-wrong rural cases (farms, subdivisions, driveway-only addresses) would have no provenance-tracked correction route. Curator review would be the only fix path, and review without a visual tool is impractical.

---

## 3. Data sources (locked: OGL-only)

Per 2026-05-16 decision, the v1 stack is fully Open Government Licence:

| Source | Purpose | Refresh | Licence |
|---|---|---|---|
| OS Open UPRN | Canonical UPRN → point coordinate | Quarterly bulk | OGL |
| OS Open TOID | Building/structure polygons + generalised XY | Quarterly bulk | OGL |
| OS Open Linked Identifiers | UPRN ↔ USRN ↔ TOID relationships | Quarterly bulk | OGL |
| INSPIRE Index Polygons (E&W) | Freehold land parcels (HM Land Registry) | Monthly | OGL |
| OS Open Zoomstack | Basemap raster/vector tiles | Quarterly bulk | OGL |

**Explicitly excluded from v1:**
- AddressBase Plus / Premium (paid OS licence; PSGA-via-Gwynedd-Council route remains an open future option per 2026-05-10 OS Places gap notes, would unlock richer TOID cross-references but not required for the rural correction use case).
- Commercial enrichment (Loqate / Ideal Postcodes).
- LIDAR (Defra national LIDAR is OGL, could be added later; defer).

**Local staging.** OGL bulk data ingested into a SpatiaLite or DuckDB-spatial cache under `seed/lleolydd/cache.duckdb`. Refresh cadence: quarterly cron on the Pi, mirroring the OS release cycle. Each refresh writes a snapshot manifest with file hashes so a given correction can be traced back to the exact data state it was made against.

---

## 4. Architecture

```
+----------------------------+        +------------------------------+
|        iPad (PWA)          |  HTTPS |     Pi: lleolydd-service     |
|  - Leaflet / MapLibre GL   | <----> |     (FastAPI, port TBD)      |
|  - bilingual UI            |        |                              |
|  - tap to inspect          |        |   - reads Craidd via Read    |
|  - drag to relocate        |        |     API (existing)           |
|  - colour-coded buildings  |        |   - reads OGL cache          |
|  - submit -> proposal      |        |   - writes via               |
+----------------------------+        |     craidd_client            |
                                      |     .propose_claim()         |
                                      +------------------------------+
                                              |          |
                                              v          v
                                         Craidd       Proposal
                                         Read API     queue
                                                      (/srv/town-
                                                       dataset/
                                                       proposals/)
```

**Backend (lleolydd-service).** Small FastAPI service running alongside the existing Read API on the Pi. Endpoints (provisional):

- `GET /lleolydd/area?bbox=<minlat,minlon,maxlat,maxlon>` — returns all known UPRNs + TOIDs + INSPIRE parcels in the bbox, with each UPRN tagged by status band.
- `GET /lleolydd/uprn/{uprn}` — for one UPRN: original OS Open coordinate, auto-snapped TOID (if any), any curator-verified override, all source provenance.
- `GET /lleolydd/entity/{entity_id}` — same as above but keyed by Craidd entity_id, returning the UPRN(s) currently claimed for that entity.
- `POST /lleolydd/proposal` — body carries the curator's decision (new point, new TOID, status verdict, evidence note). Service validates against the schema and writes a proposal via `craidd_client.propose_claim()` using the curator's identity from the auth header. Returns the proposal id.

**Status bands** (the colour code on the map):

| Band | Colour | Meaning |
|---|---|---|
| `verified` | green | A curator has explicitly placed/confirmed the point and TOID. Source = curator on-site or curator desk-verified. |
| `auto-snapped` | amber | OS Open Linked Identifiers (or our spatial match) connects this UPRN to exactly one TOID and the original point falls inside the TOID. Plausibly correct, not curator-confirmed. |
| `unsnapped` | red | UPRN point doesn't fall inside any TOID, or matches multiple. Needs curator attention. |
| `contested` | purple | More than one verified claim exists with different points/TOIDs. Curator review job. |
| `non-postal` | grey | OS-allocated UPRN for a non-postal feature (substation, post box, defibrillator). Out of scope for this tool by default; tucked away behind a layer toggle. |

These bands are computed server-side at session start and cached. A proposal acceptance updates the band on the next refresh; verification status is itself a Craidd claim, so the bands are derived from the live store, not stored separately.

**Frontend (iPad PWA).** Single-page web app, served as static assets from the Pi. Leaflet or MapLibre GL JS (final pick at build time — Leaflet is simpler; MapLibre handles vector tiles better and is the right call if OS Open Zoomstack vector tiles are used). Three view modes:

1. **Map mode** (default). OGL basemap + TOID polygons + UPRN points colour-coded by band. Tap a building or point to open the inspector.
2. **Inspector mode** (slide-up panel). Shows current entity claims, original UPRN coordinate, current best snap, verification history. Two action buttons:
   - *Confirm location* — adopts the current best point/TOID as verified. Single tap.
   - *Override location* — enters drag-to-place mode. The pin becomes draggable, building polygons highlight on hover, "snap to this building" appears on tap. Save submits a proposal.
3. **Evidence mode** (modal). Required before submitting a proposal: a note (free text, bilingual fields), optional photo (camera capture on iPad), and a quick-select reason (`on-site` / `aerial-confirmed` / `local-knowledge` / `corrects-prior-error`). Photo handling matches BRA discipline — hash + URL stored, bytes held under `restricted` visibility.

**Bilingual UI.** All labels in cy and en; toggleable; defaults to cy (consistent with the Welsh-rooted positioning). Welsh status terms suggested: `wedi'i wirio` (verified), `awtomatig` (auto-snapped), `heb ei wirio` (unverified / unsnapped), `dadl` (contested), `dim post` (non-postal). North Wales register per existing project discipline.

**Field-use assumption (locked).** Online-first PWA. Assumes Tailscale (and/or 4G/5G) connectivity. Service worker scaffolded so that offline-capable mode can be added without rewrite (decision deferred per 2026-05-16 question 3).

---

## 5. Schema dependencies (v0.2 backlog additions)

Lleolydd surfaces three additions that should land in `v0.1-schema.md §10` v0.2 backlog as a new item 7:

1. **New predicate: `verified_building_toid`.** Value type: TOID (string, OS MasterMap TopographicArea identifier). Subject: building. Qualifiers: `verification_method` (one of `on-site`, `aerial`, `local-knowledge`, `documentary`), `verified_at` (date), `cache_snapshot_id` (refers to the OGL cache snapshot the verification was made against).

2. **New predicate: `location_verification_status`.** Value type: enum (`verified`, `auto-snapped`, `unsnapped`, `contested`, `non-postal`). Subject: building or UPRN. Lets the canonical view expose whether a location is curator-blessed or merely auto-snapped, which is the single most useful flag for downstream consumers (the energy study, the BRA, HMLR linkage).

3. **New qualifier vocabulary entries on the existing `geometry` predicate:**
   - `geometry_basis` enum extended with `os-open-uprn-original`, `auto-snapped-to-toid`, `curator-placed`, `curator-confirmed-original`.
   - `verification_method`, `verified_at`, `cache_snapshot_id` (as above) usable on `geometry` claims too.

These additions are **purely additive** in the v0.1-schema spirit — no breaking changes. They can ship under the existing v0.2 schema work whenever it lands; until then, Lleolydd writes the predicates as `pending_schema: v0.2` proposals (same pattern BRA v2 uses for `listing` / `agent` / `sale_record`).

**Cross-domain win.** Once `location_verification_status` is in the canonical view, the energy study's `apply_dec_corrections.py` and the BRA's subject-resolution loop both gain a single boolean test for whether a UPRN can be trusted for cross-referencing. The 303 BRA drafts currently `still_ambiguous` can be filtered: any resolving to a `verified` building is safe to propose; any resolving only to `auto-snapped` waits for Lleolydd confirmation.

---

## 6. Build phasing

Slotting into the `cli-design.md` §6 build order, after Track A's `craidd-review` lands. Lleolydd is parallelisable with `craidd-fetch` / `craidd-export` / `craidd-status` — it depends on the Read API (already in use), `craidd_client.propose_claim` (built 2026-05-15), and the proposal queue (live with 4 real items as of 2026-05-15).

**Phase 0 — charter + design commit (1 session).**
Commit this document. Expand `architecture.md` §6.21 with the BRA-style versioned charter. Add to `cli-design.md` as a top-level tool. Add the three v0.2 backlog items to `v0.1-schema.md §10`. No code.

**Phase 1 — OGL bulk ingestion + cache (1–2 sessions).**
Download OS Open UPRN, OS Open TOID, OS Open Linked Identifiers, INSPIRE Index Polygons (LL40 + surrounding parishes — bound the bulk by polygon, not by national load). Build `seed/lleolydd/build-cache.py` to produce `seed/lleolydd/cache.duckdb` with spatial indexes. Compute per-UPRN status bands. Snapshot manifest with file hashes. Output an audit CSV of band distribution across Dolgellau — this is interesting in its own right and tells us how much of the rural-correction work is real.

**Phase 2 — read-only viewer (1 session).**
Backend: the three `GET` endpoints. Frontend: map view + inspector view, no override action. Bilingual labels, status colour-coding, basemap. Deploy to the Pi. Open it on the iPad and walk Bridge Street — does the picture match reality? Adjust band thresholds based on what we see. **This phase alone delivers most of the diagnostic value** — it makes the UPRN-quality problem visible in a way that a CSV can't.

**Phase 3 — override workflow (1–2 sessions).**
Drag-to-place + tap-to-snap + evidence modal. `POST /lleolydd/proposal`. Curator-identity auth header (same pattern as the rest of the curator surface). Audit CSV per session. First real test: walk the two known-wrong buildings from the 2026-05-15 finding (Bodlondeb, Ardd Fawr), place correct points, submit proposals, then run `craidd-review` to accept.

**Phase 4 — bulk-triage view (1 session).**
Once the workflow is exercised on a handful of buildings, add a list mode: all `unsnapped` and `contested` UPRNs, sortable, click-through to inspector. Lets the curator chew through the residue in batches rather than wandering the map looking for red dots.

**Phase 5 — deferred / later.**
- Offline-capable PWA (tile pre-caching, IndexedDB edit queue, sync on reconnect). Deferred per 2026-05-16 question 3.
- Aerial imagery layer (licence work; OS OpenData VMD as starting candidate).
- LIDAR overlay for ambiguous farmsteads.
- Generic multi-area mode (the standalone-tool path from question 2; only if a second Awen instance asks for it).
- Welsh tutor pass on UI strings (parallel to the existing 58-predicate Welsh-description backlog).

---

## 7. Non-negotiable disciplines (inherited)

Lleolydd inherits the same disciplines as BRA and the energy study:

- **Never writes to Craidd directly** — proposals only. `craidd-review` is the only acceptance path.
- **No self-acceptance** — a curator cannot accept a Lleolydd proposal they submitted themselves. (Pertinent: Huw is currently the sole v0 curator. Self-acceptance is forbidden at the API layer; a second curator is needed before any Lleolydd proposal can become canonical. This is a feature, not a bug — it surfaces the curator-pool size limit early.)
- **Provenance always.** Every override carries `verification_method`, `cache_snapshot_id`, evidence note, and curator identity.
- **Welsh content honest.** Bilingual UI is structural. cy is the default. No machine-translated placeholder strings.
- **Photos: hash + URL, never republish bytes** (BRA-inherited; `restricted` visibility).
- **Reproducible reasoning.** The cache snapshot id on every claim means a correction made on the 2026-05 OGL release is always traceable to that release, even after the 2026-08 release moves the underlying data.

---

## 8. Open questions — resolved 2026-05-16

All seven first-pass questions answered by Huw in the design-review pass:

a. **Name** → **Lleolydd** confirmed.

b. **Map library** → **MapLibre GL JS**, vector-tile path. Aligns with iPad retina rendering and TOID/polygon-native data shape.

c. **Auth model** → **Wait for `craidd-review` to settle and share its curator-identity mechanism.** Lleolydd does not stand up a parallel auth surface.

d. **Area bound** → **Whole of Gwynedd** at v1.

e. **Aerial imagery in v1?** → **TOID-only at v1.** Aerial deferred to Phase 5.

f. **Non-postal UPRNs** → **Toggle on, off by default.**

g. **`location_verification_status` derived vs stored?** → **Superseded by §12.A live-update model** — the multi-curator concurrency requirement makes this no longer just a caching question. Status now becomes part of the live broadcast layer (see §12.A), which is itself a derived view over claims plus pending placements. The "refresh on proposal acceptance / cache rebuild / on demand" trigger model still applies, with the addition of "refresh on every pending-placement broadcast tick".

---

## 9. What this unblocks

Listed for the record, because the value case is concrete:

- **The 303 `still_ambiguous` BRA drafts** become triageable rather than blocked. Many will resolve once their candidate buildings have `verified` location.
- **HMLR cross-references** (the 2,195 Price Paid sales, OCOD foreign-owned properties, INSPIRE parcels) can be reliably joined to canonical building entities for the first time.
- **The energy study's UPRN-lookup uniqueness audit** flagged on 2026-05-15 becomes a working session in front of the map rather than a CSV scrub.
- **Listed-building register linkage** (the dual-listing Tŷ Newyddion / Glyndwr Milk Bar problem) becomes spatially obvious — one polygon, two Cadw IDs — rather than only being catchable by careful reading.
- **The Awen public face** gains a visible, walk-up-able tool. The "place-based trust" pitch is much easier to land when there's a Pi-hosted iPad you can stand next to on Bridge Street and tap.

---

## 10. Companion artefacts to produce alongside this commit

When this design lands, sibling work to do in the same session or the next:

- `architecture.md` §6.21 — six-question Lleolydd charter (using the material in §2 above).
- `cli-design.md` — new top-level tool entry (CLI for the data-prep side: `lleolydd-cache build`, `lleolydd-cache snapshot`, `lleolydd-serve`).
- `v0.1-schema.md §10` — new item 7 covering the three predicate/qualifier additions.
- `seed/lleolydd/README.md` — explains the cache build, the snapshot discipline, and how the audit CSVs are named.
- `config/lleolydd/area-bounds.geojson` — the polygon defining the v1 cache extent.

---

## 11. Closing note

The briefing identifies the problem correctly and the open-data combination correctly. The remaining design work — and it's the bulk of it — is the *workflow*: how does a curator standing on Bridge Street, or sitting at the kitchen table with the iPad, walk through one building, decide, leave evidence, and trust that the next person to query the dataset will see the right answer with the right provenance? That workflow is Llys, not data. The data sources (§3) and the schema (§5) are settled; what makes Lleolydd Awen-shaped rather than just a UPRN-correction script is §4 (the bands + the inspector + the evidence modal) and §7 (the disciplines that keep it provenance-bound).

---

## 12. Second-pass additions — 2026-05-16 (post-Huw-review)

Four design issues raised in the same review pass that resolved §8. None invalidate the first-pass design; all extend it.

### 12.A Multi-curator live concurrent editing

**The ask.** "If a couple of people were doing the live checking it would be better if their updates were incorporated immediately, in case of unintentional overlaps in effort."

**Why this is not just a caching question.** The original §8(g) recommendation (derived-but-materialised status) assumed a single curator at a time. Two curators on Bridge Street simultaneously is a different problem — they need to *see each other's in-progress work* to avoid clashing on the same building, *and* they need their decisions to take effect immediately so the picture they're each working against stays current. This crosses from "what's stored where" into "what's broadcast where, and when does a placement become canonical".

**The Awen-shaped answer.** Three layers, each with an explicit constitutional posture:

1. **Live pending-placement broadcast.** A WebSocket (or Server-Sent Events — same thing, simpler) channel from `lleolydd-service` to every connected iPad. When curator A drags a pin, curator B sees a ghost-pin appear with A's initials and a "placing…" badge. When A submits, B sees the ghost-pin transition to a distinct visual (e.g., dashed outline + co-sign-prompt badge). When B accepts via co-sign (see layer 3), the pin transitions to the standard `verified` green. *This layer is purely advisory* — Craffter-shaped: it shows what's happening but contains no new claims.

2. **Per-entity soft lock.** When a curator opens a building's inspector, an "in review by [name] since [time]" badge appears for other curators. Soft, not hard — anyone can override the lock if it's stale (>5 min) or if they have a specific reason ("I'm correcting an error A just made"). Lock state is held in the broadcast layer, not in Craidd. *Constitutionally:* this is just a coordination affordance, not a new authority. Two curators can still simultaneously edit the same entity if they choose to — the lock is a polite signal, not a gate.

3. **Co-sign acceptance for field sessions.** This is the change with real architectural weight. Today's plan (§7) says "no self-acceptance" — every Lleolydd proposal needs the second-curator-via-`craidd-review` async path. For field sessions, that loop is the wrong shape: A places a pin at the front of the building, B is standing right there agreeing, and they don't want A's correction to wait three days for B to log into `craidd-review`. So Lleolydd introduces a **co-sign acceptance path**:
   - When two or more curators are in the same active field session, A's submitted placement enters a `co-sign-pending` state visible to all session participants.
   - Any other curator in the session can tap "co-sign" on A's placement. The placement becomes canonical immediately, with both signatures (and the field-session id) recorded in Prawf.
   - **No-self-acceptance still holds.** A cannot co-sign their own placement. The constraint is preserved; only the *sequence* changes (synchronous co-sign instead of asynchronous review).
   - Solo placements (one curator in the session, or no co-signer present) fall back to the standard async `craidd-review` path. Nothing changes for that case.

**Prawf treatment.** Every co-sign records both curator identities, the field-session id, the timestamps of placement and co-sign, and the OGL cache snapshot id. A future audit can reconstruct exactly who-was-where-and-agreed-with-whom for every co-signed correction. This is stronger provenance than the async path provides, not weaker.

**Schema dependency.** Adds two new claim qualifiers: `field_session_id`, `co_signed_by`. Folds into the §5 v0.2 backlog item.

**Open question (new).** What's a "field session"? Recommended definition: a server-side object the curator explicitly opens ("Start field session") and closes ("End field session") on the iPad. Holds the participant list and a session id. Claims accepted within an open session use the co-sign path; outside it, async review. Avoids implicit/heuristic session detection.

**Constitutional point worth recording.** Co-sign is *not* a relaxation of the no-self-acceptance principle. It is a new acceptance path that respects the principle while removing async friction when the human-judgement step is happening synchronously. This is the kind of distinction the constitutional framework (§2.4 of `design/constitutional-framework.md`) is meant to handle — the principle is preserved, the implementation gains a new shape.

### 12.B Creating new entities (not just correcting existing ones)

**The ask.** "There will be new buildings built which will need adding, what is the best workflow for this."

**The gap.** The proposal queue currently handles **claim** proposals only. The four real proposals on the Pi as of 2026-05-15 are all `propose_claim()` — adding facts to entities that already exist. The Tŷ Newyddion bootstrap was a hand-walked Python script (`seed/buildings/ty-newyddion/bootstrap.py`); the four new buildings on 2026-05-15 (Old Wesley House, 36 Uwch Y Maes, 3 Bodlondeb, 2 Ardd Fawr) were also bootstrapped by Code, not via a curator workflow. There is no curator-facing entity-creation flow today.

**The workflow Lleolydd needs.** Curator taps a TOID polygon that has no associated UPRN/entity, or taps "Place new entity here" on an empty patch of map (a planned building with no TOID yet). Modal opens:

- **Entity type** (radio): Building (only enabled in v1 — see §12.D for others).
- **Names**: `name_cy` and `name_en`, both with `name_type` qualifier (current_local / listed_register / historic / vernacular).
- **Address**: free-text, optional.
- **Listed status flag**: optional Cadw/Historic England reference, no validation in v1.
- **UPRN**: optional. If empty, the entity is created without a UPRN claim (legitimate for new builds before UPRN allocation; legitimate for non-UPRN entities later).
- **Geometry**: the tap point + the TOID (if tapped on a polygon) or a draggable pin (if tapped on empty map).
- **Notes**: free-text bilingual evidence note.

**Architectural change.** Lleolydd surfaces a new proposal shape — `entity_proposal` — distinct from the existing claim proposal. This needs:

- A new method `craidd_client.propose_entity(submitter, entity_type, names, source, note, evidence_uri)` returning a proposal id.
- A new validator `validate_entity_proposal()` in the schema layer.
- A new file shape `EP-<ts>-<uuid>.json` in `/srv/town-dataset/proposals/`.
- An extension to `craidd-review` so it accepts entity proposals: creating the entity, then opening any same-session claim proposals attached to that entity for review against the freshly-created subject.
- Atomicity: an entity proposal is typically submitted *together with* an initial geometry claim proposal (and often a name claim, address claim, etc.). Lleolydd should bundle these as a single curator action ("Create new building") with one Prawf-level "submission event" linking the proposal ids — even though each proposal is reviewed/accepted separately.

**This is the bigger architectural item of the second pass.** It extends the proposal queue model in a way that BRA, the energy study, and `craidd-propose` will all benefit from. Worth designing the `entity_proposal` shape carefully now, even though Lleolydd will be the first user. Charter implication: `architecture.md` §6 needs an updated description of the proposal queue to cover both proposal types.

**Co-ordination point.** This change crosses the Cowork/Code seam. The `entity_proposal` validator lives in the schema layer (Cowork-side, where the existing `validate_proposal` and `validate_entity` live); the new `propose_entity` method lives in `craidd_client.py` (Cowork-side); the `craidd-review` extension is Code's. Worth raising in the next Code session brief.

### 12.C Address/descriptor surfacing in the inspector

**The ask.** "When looking to confirm accuracy of a UPRN, a list of the address/descriptors for the property — including any estate-agent descriptor — could help the assessor on the ground."

**Why this is mostly a UI job, not a data job.** Everything the assessor would want is already in Craidd (or will be once BRA v2 lands and v0.2 ingests its drafts). The job is to surface it well in the inspector panel.

**The inspector panel gains a "Descriptors" tab.** Bilingual, scrollable, source-cited, visibility-badged. Shows for the building under inspection:

- All `name_cy` / `name_en` claims with `name_type` qualifier (current_local / listed_register / historic / vernacular). Multi-cardinality is exactly why this exists.
- All `address` claims (postal, vernacular, historic).
- Listed-building register entries (`listed_id` claims with their Cadw/BLB references and grades).
- Tenancy entities (`tenancy_of` claims) — current and historic occupants with date ranges.
- BRA v2 listing-derived content (once v0.2 lands): agent narrative description (Tier C verbatim text, `restricted` visibility — visible to the assessor in the field but not republished), floor area with basis, EPC band, bedroom/bathroom counts.
- HMLR sale/proprietorship (once v0.2 lands): most recent sale price + date, current proprietor (incl. OCOD foreign-ownership flag), title number.
- Photos (once v0.2 lands): floor-plan, front elevation. `restricted` visibility — visible to the assessor in the field but stored as hash + URL, not bytes.
- Research questions (`entity_type='research_question'` claims) — explicit known-unknowns from the source documents, useful prompts for the assessor ("source X says four storeys, source Y says three — what do you see?").

**Field-use win.** Standing in front of a building with all this on the iPad, the assessor isn't choosing between "is this UPRN at the right point?" and "is this the right *building*?" — both questions get answered together. That's a bigger uplift than the briefing implied.

**Implementation notes.** No schema additions; entirely existing predicates. Inspector queries the Read API for all claims on the entity, groups them client-side. Cache miss is fine — the inspector only opens on tap, not on every map pan.

### 12.D Future-scope: monuments, features, open spaces, and energy infrastructure

**The ask.** "There may well be monuments, features and open spaces which enrich the Town Dataset from a historical, cultural, environmental or ecological perspective… This element may also be relevant to the location of future assets for the energy modelling such as location of grid infrastructure, future heat-pump locations or PV arrays."

**Two parts to keep separate.**

**Part 1 — non-building entity types (deferred to v0.3 schema, scoped now).** The Town Dataset v1 is sharply bounded to "buildings + histories" by deliberate decision. Adding monuments / features / open spaces / energy assets stretches that bound — which is a meaningful Awen-positioning question, not just an engineering one. The pitch is "explicit boundaries"; expanding boundaries needs to be visible. The right home for this conversation is a v0.3 schema decision, not a Lleolydd design choice.

That said, Lleolydd should be designed so that **v0.3 expansion is a UI mode addition, not a rewrite**. Concrete requirements:

- The Lleolydd engine (cache, bands, drag-to-place, proposal submission, broadcast layer, co-sign path) must be entity-type-agnostic. Nothing in §4 or §12.A/B should hard-code "building".
- The v1 UI scopes the entity_type radio in §12.B's "Create new entity" modal to `building` only. Other types are listed as disabled with a "v0.3" badge so the future intent is visible to anyone using the tool.
- The inspector (§12.C) follows the same discipline: it renders whatever predicates are present on the entity, regardless of type. v0.3 entities show whatever v0.3 predicates apply.

When v0.3 lands, enabling `monument` / `feature` / `open_space` is a single-line change to the radio. The hard work is the schema decision, not the UI.

**Suggested v0.3 entity types and their natural data sources** (parking notes for the eventual schema discussion):

| Entity type | Suggested OGL/open sources | Notes |
|---|---|---|
| `monument` | Cadw scheduled monuments register; RCAHMW Coflein database; Welsh Government open data | Often co-located with buildings — needs a `relates_to_entity` or `at_location` claim back to a building or coordinate. |
| `feature` | OS Open Names; OSM (with provenance care); Welsh place-name datasets | Bridges, milestones, wells, named trees, etc. Usually point geometry. |
| `open_space` | INSPIRE polygons (already in the v1 cache); Public Open Space datasets; Natural Resources Wales designated sites | Polygon geometry. Conservation status, public-access status as claims. |
| `infrastructure_asset` (or `energy_asset`) | OS Open Greenspace doesn't cover this; National Grid open data; DNO (SP Energy Networks, ENW) where available | Substations, pylons, future heat-network routes. Includes both `existing` and `proposed` claims — Lleolydd's drag-to-place is exactly the right tool for placing proposed assets. |

**Part 2 — the energy-modelling overlap.** Huw's framing ties this directly to the energy study: Lleolydd's drag-to-place mechanism is the same primitive whether what's being placed is "the correct point for an existing UPRN" or "the proposed location for a future PV array on this rooftop". The user is different (energy modeller vs town curator), the entity type is different (`energy_asset` vs `building`), and the source is different (`proposed` vs `verified-on-site`) — but the engine is the same.

**Implication for v1.** None — defer entirely. But the v1 implementation should not paint itself into a corner. Two specific guardrails:

- The proposal shape should carry `temporal_status` qualifier-vocabulary capable of distinguishing `existing` / `proposed` / `historic` / `removed`. Folds into the §5 v0.2 backlog without a breaking change.
- The status-band vocabulary in §4 should not assume the thing being banded "exists in reality today". A `verified` band on a proposed PV array means "this is where the proposal places it", not "this is where it has been built". The visual treatment in v0.3 should make `proposed` items visually distinct (e.g., dashed outline) from `existing` ones — easy CSS work, but worth flagging now so the v1 styling tokens are extensible.

**Build implication.** Add to the §6 build-phase plan a "Phase 5 — deferred" item: *Entity-type generalisation for v0.3.* Sits behind the v0.3 schema decision. No work in v1 beyond the two guardrails above.

---

## 13. Updated build phasing (after §12)

The §6 phases stand, with the following adjustments:

- **Phase 0** now also commits the `entity_proposal` shape design (§12.B) to the schema docs, even though the implementation is later.
- **Phase 2** (read-only viewer) now also implements the §12.C inspector "Descriptors" tab. No new data needed — it's a UI consumption of existing claims.
- **Phase 3** (override workflow) now also includes:
  - The §12.A live broadcast layer (WebSocket/SSE) and per-entity soft lock.
  - The §12.A co-sign acceptance path (depends on the curator-identity layer, which depends on `craidd-review` — coordinate at Phase 3 start).
  - The §12.B new-entity creation flow (depends on `craidd_client.propose_entity` — design now, build at Phase 3).
- **Phase 5** (deferred) gains:
  - Entity-type generalisation for v0.3 (per §12.D).
  - The `temporal_status` qualifier and the `proposed`/`existing`/`historic`/`removed` visual treatment.

Total v1 build remains within the original phase budget; the additions land mostly in Phase 3, where the workflow surface is already being built.
