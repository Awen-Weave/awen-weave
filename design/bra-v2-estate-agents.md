---
title: BRA v2 — Estate Agent Listings Scraper
status: design draft
date: 2026-05-12
supersedes: nothing yet — extends architecture.md §6.14 (BRA v1)
---

# BRA v2 — Estate Agent Listings Scraper

This is a design handover. The canonical repo at `/Users/withaw/Awen/town-dataset/` is not mounted in the current Cowork session, so this document is delivered here and is intended to be committed at `design/bra-v2-estate-agents.md` on the Code side, with `architecture.md` §6.14 updated to reference it.

## 1. What this is

A v2 extension of the Building Research Agent that adds the *living-market* layer to the Town Dataset. v1 BRA produces per-building research packs from authoritative sources (Cadw, BLB, RCAHMW, council records). v2 adds estate-agent sources — current sale listings, current rental listings, and sold-archive narratives — funnelled through the same proposal-queue discipline.

This was previously flagged in the v0.2 schema backlog (HMLR finding 2026-05-12) as "Estate-agent sold-archive scraping deferred to BRA v2." This document picks that up.

## 2. Six-question charter (per architecture.md §1)

**Awen role.** Llys (contributor-side automation). Identical role to BRA v1. Proposes claims; never accepts them.

**Why it exists.** The pre-ingestion corpus has historical depth (HMLR Price Paid 1995→2026, OCOD foreign-ownership, Census, MYE, energy study) but no living-market signal. Without it the dataset cannot answer "what is for sale in Dolgellau right now" or "what is the rental stock like" — and the rich narrative content that agents publish (descriptions, photos, sold-archive write-ups) is being silently lost as listings close.

**Consumes.**
- Curator-approved estate agent allowlist (output of stage 1).
- Nimble API access (search, extract, agent-builder workflows).
- `craidd_client.py` for proposal writes.
- `seed/output/uprn-lookup.csv` for subject (building) resolution.
- v0.2 schema additions (`listing`, `letting_record`, `agent`, `sale_record`) — see §6.

**Produces.**
- `seed/agents/dolgellau-agents.csv` — discovery output (stage 1).
- `seed/listings/<source>/<listing_id>/` — per-listing snapshot bundles: `snapshot.html`, `metadata.json`, `hash.txt`.
- `seed/buildings/<building_id>/claims.draft.json` — append, *only* where subject resolves with sufficient confidence.
- `seed/listings/_unresolved/queue.csv` — listings where subject binding failed, awaiting curator triage.
- `seed/listings/_runs/<timestamp>.jsonl` — Prawf-style run log.

**Non-goals.**
- Does NOT write to Craidd directly. Output is always proposals or pre-ingestion seed material.
- Does NOT auto-bind low-confidence listings to buildings. False-positive binding corrupts the building's record; the unresolved queue is the right default.
- Does NOT canonicalise photos. Photo URLs are recorded; bytes are not stored in the canonical layer. Rights are unresolved.
- Does NOT paraphrase agent narrative. Quote-with-citation, same discipline as BRA v1.
- Does NOT auto-translate Welsh. Agent narratives are almost always English-only; `cy: null` is recorded honestly.
- Does NOT compete with HMLR Price Paid as the canonical sales record. Estate-agent "sold" archive is supplementary narrative — useful for descriptions and photos, not authoritative for price.

**What would change if removed.** Loss of the living-market layer; sold-archive narratives lost permanently as agents update; the planned v0.2 `listing` entity type would have no automated feeder, leaving it manual-only.

## 3. Pipeline (two-stage)

### Stage 1 — Agent discovery (one-off, refreshed quarterly)

Query Nimble for estate agents advertising LL40 stock. Cross-reference Rightmove agent directory, Zoopla, OnTheMarket, Propertymark/NAEA membership lists, and any Welsh-agents association. Output a candidate roster: name, website, branch address, postcode coverage, agent type (sales / lettings / both), aggregator presence.

The roster lands at `seed/agents/dolgellau-agents.csv` as a draft. **Curator approval is mandatory before any agent is added to the scraping allowlist.** This is the v0 manual gate; v1 it becomes a craidd-propose pattern with `agent` entity claims.

### Stage 2 — Listings scrape per agent (recurring, default weekly)

For each agent in the curator-approved allowlist, plus filtered views on aggregators where TOS permits, run a per-agent `nimble-agent-builder` workflow. The agent-builder approach is deliberate: it produces durable, reusable extraction agents per site shape, in line with the skill's intended use ("build a reusable scraper" / "extract from this site regularly"). Each site shape is one named Nimble agent.

Per listing:

1. Fetch index → enumerate listing URLs.
2. Fetch each listing → take a snapshot (raw HTML), hash (sha256), record retrieval timestamp.
3. Diff against prior snapshot — unchanged listings short-circuit.
4. Extract structured fields per the field catalogue in §3a.
5. Quote narrative description verbatim into evidence — do not extract structured claims from prose. The synopsis description is itself an evidence record, queryable but never paraphrased.
6. Download image assets (front-elevation photo, floor plans, EPC graphic if present) into `seed/listings/<source>/<listing_id>/images/` with hashes. Image bytes are treated as `restricted` visibility — never republished by the read API, but available to curators for canonical-record decision-making.
7. Subject resolution: normalise address; attempt match against `seed/output/uprn-lookup.csv`. Acceptance thresholds reuse the OS Places work: top match ≥ 0.85 AND margin over second ≥ 0.10. Pass → bind `building_id` and produce draft claims. Fail → write to `_unresolved/queue.csv`.
8. Write run log entry.

### 3a. Field catalogue — what is captured per listing

Three tiers. Tier-A is mechanical extraction (low ambiguity, propose-as-claim). Tier-B is structured but agent-stated (propose as claim with `confidence: medium` and explicit `source: agent_listing`). Tier-C is narrative / image evidence (capture verbatim, no structured claims — curator decides).

**Tier A — mechanical (high confidence):**
- Address (line 1, locality, postcode)
- Listing ID (per agent / per aggregator)
- Listing status (for sale / sold STC / sold / under offer / withdrawn / to let / let agreed / let)
- Asking price OR monthly rent
- Tenure (freehold / leasehold / share of freehold)
- Listing date / status-change date
- Agent name + branch
- Aggregator presence flag (also on Rightmove / Zoopla / OnTheMarket)

**Tier B — agent-stated structured (medium confidence; corroborate where possible):**
- **Floor area** — pilot finding (2026-05-12) is that headline GIA is usually "Ask agent", but **room-by-room dimensions are stated for every room**. Primary extraction strategy is therefore `floor_area_m2` with basis `computed-from-room-dimensions` (sum of metric room areas from the structured room list). Stated GIA, when present, captured with basis `agent-stated`. Cross-domain valuable for the energy study; see §6.5.
- **Number of storeys / floor count** — agent listings often give a clearer breakdown than EPC (e.g. "three-storey terraced house plus cellar"). Capture as count + qualitative description.
- **Number of bedrooms / bathrooms / reception rooms** — standard agent metadata.
- **Garden** — captured as `has_garden: true/false` plus free-text qualifier (front / rear / wraparound / size / aspect).
- **Heating system** — captured as `heating_system_description` (verbatim from listing) plus extracted fields where unambiguous (`heating_fuel: gas/oil/lpg/electric/heat-pump/biomass/none`, `boiler_age` if stated, `system_type: combi/conventional/district-heating/storage-heaters` if stated). High value for the energy study cross-reference.
- **EPC rating** (if surfaced on the listing) — band + score where given.
- **Council tax band** — useful proxy for value tier. Note: "Exempt — holiday let" or similar values are signals in themselves, captured verbatim with a structured `tax_band_exemption_reason` qualifier where applicable.
- **Planning restriction** (pilot-confirmed 2026-05-12) — captured as `planning_restriction` with structured enum `holiday_let_only` / `agricultural_tie` / `affordable_housing_only` / `commercial_use_class` / `none`, plus free-text. Materially affects use class, council tax, and saleability; not optional.
- **EPC exempt flag** (pilot-confirmed 2026-05-12) — `epc_exempt: true/false` with reason enum (`listed_building` / `holiday_let` / `place_of_worship` / `other`). Listed buildings show EPC as exempt and the listing surfaces this as a positive feature; recording exemption explicitly is better than recording absence.
- **Listing-status events** (pilot-confirmed 2026-05-12) — aggregators label listings "Added on ...", "Reduced on ...", "Sold STC on ..." etc. Capture as `listing_events` array on the `listing` entity (each entry: `event_type` + `event_date`). Trivial extraction; gives free lifecycle history.
- **Year built / period** — agent-stated, low confidence; corroborate against Cadw / building history.
- **Construction notes** — if stated (e.g. "stone-built", "slate roof", "double-glazed").

**Tier C — narrative and image evidence (verbatim, no structured claims):**
- **Full narrative description** — stored verbatim in `metadata.json.description_text` and as the snapshot itself. Curator can later quote-with-citation when building canonical claims.
- **Synopsis** — a one-paragraph distillation of the description text, generated by Claude during scrape via `cowork.askClaude` or equivalent, stored alongside the verbatim text in `metadata.json.synopsis`. Marked `synopsis_source: llm` with model + prompt hash for reproducibility. The synopsis is **a reading aid for the curator**, never proposed as a claim, never substituted for the verbatim text.
- **Special features** — listed in the agent narrative (period features, inglenook fireplace, exposed beams, mature gardens, outbuildings, parking, garage, planning consent in place). Captured verbatim as a list; curator decides which surface as canonical claims.
- **Front-elevation photograph** — primary external photo of the building's front. Stored as `images/front_elevation.<ext>` with sha256. Used by curators for visual verification of subject-resolution decisions.
- **Floor plans** — stored as `images/floor_plan_<n>.<ext>` with sha256. Frequently the single most informative artefact in an agent listing for building-history work — internal layout, partition history, extension footprints all become visible.
- **Other photos** — all remaining listing photos stored under `images/` with hashes. Bytes held; never republished.

All tier-C content is stored under `restricted` visibility by default. The structured claims that flow from tier A and tier B can be `public` once curator-reviewed — those are facts the agent has themselves published under their own banner.

### 3b. Image capture and rights handling

Floor plans and photographs are agent-commissioned or agent-licensed work; bytes are subject to copyright. The handling rule:

- **Capture is for evidence and curator review only** — never published via the Craidd read API, never re-served from any Awen-hosted endpoint.
- **All image bytes carry `visibility: restricted`** in the evidence record. The schema's existing visibility model (public / restricted / private — established in v0.1) already covers this; no schema change needed for the image-handling rule itself.
- **The URL and the sha256 are recorded as `public` metadata.** Where an image came from, and proof that we captured a specific version of it, are public-record facts about the listing.
- **Curator workflow:** when curating, the curator can inspect the restricted images locally and write canonical claims that *describe* what the floor plan shows ("first floor has three bedrooms with rear extension dated post-2010") with the image hash as evidence citation — the description, not the image, becomes the public claim.
- **Hard rule:** the read API and any public dashboard must refuse to serve image bytes from `restricted` evidence records. Belt-and-braces: file naming convention `restricted_*.jpg` so accidental publication is visible at glance.

## 4. Site-shape manifests

Each agent / aggregator has a manifest at `config/agents/<agent_id>.yaml` declaring the site shape — selectors for fields, listing index URL pattern, sold-archive URL pattern (if any), TOS classification, last-verified date. When a site changes shape, only the manifest changes. The Nimble agent itself is generated/refined from the manifest using nimble-agent-builder.

This separates "what the site looks like" (manifest, source-controlled, curator-readable) from "how we extract it" (Nimble agent, refined via the agent-builder skill).

## 5. Provenance discipline (mandatory)

Inherits BRA v1's discipline; adds estate-agent-specific rules:

- Every scraped page is snapshotted with `retrieved_at`, `source_url`, `sha256`, `agent_id`, `site_shape_version`.
- Every claim cites the snapshot (immutable), not the live URL (decays).
- Quote-don't-paraphrase: agent narratives stored verbatim, never reduced to "the building has X".
- Multi-source corroboration: if Rightmove and the agent's own site both list a property, both are recorded as competing claims, not synthesised into one.
- Visibility: snapshot HTML is `restricted` until curator clears (rights / TOS unknown by default). Extracted structured claims (price, postcode, listing date, agent name) can be `public` — they are facts published by the agent under their own banner.

## 6. Schema implications (v0.2 ask)

BRA v2 surfaces requirements that the current v0.1 schema cannot satisfy cleanly. Adding to the v0.2 backlog:

| Entity type | Purpose | Why needed |
|---|---|---|
| `listing` | One marketed offering of a property, with a lifecycle (live / sold-stc / sold / withdrawn / let-agreed / let). | A building has many listings over time; modelling listings as building-claims loses lifecycle and cross-source identity. |
| `letting_record` | Completed letting transaction analogue to `sale_record`. | Rental side is structurally different from sales (recurring, no HMLR canonical equivalent). |
| `agent` | The estate agent as an entity. | Listings carry their agent's identity; agents change ownership; agent claims are first-class for sale_record provenance. |
| `sale_record` | Already in v0.2 backlog from HMLR work. Confirmed needed. | Cross-source corroboration: HMLR PPD record + agent sold-archive record corroborate or contradict. |

New predicates surfaced by the field catalogue (§3a). These extend the v0.1 vocabulary additively — same approach as the v0.1 additions over v0:

| Predicate | Type | Notes |
|---|---|---|
| `floor_area_m2` | numeric | Requires `floor_area_basis` qualifier: `gia` / `nia` / `from-epc` / `agent-stated` / **`computed-from-room-dimensions`** / `measured-survey`. Multi-source — listings, EPC, energy study, council records all contribute. The `computed-from-room-dimensions` basis was pilot-confirmed (2026-05-12) as the most reliable basis for Rightmove/Walter-Lloyd-Jones-shaped listings, since headline GIA is usually "Ask agent" but room-by-room dimensions are uniformly stated. |
| `planning_restriction` | enum + string | `holiday_let_only` / `agricultural_tie` / `affordable_housing_only` / `commercial_use_class` / `none` + verbatim restriction text. |
| `epc_exempt` | boolean + reason | Reasons: `listed_building` / `holiday_let` / `place_of_worship` / `other`. |
| `has_garden` | boolean | Qualifier free-text for orientation / type. |
| `heating_fuel` | enum | `gas` / `oil` / `lpg` / `electric` / `heat-pump` / `biomass` / `district-heating` / `none` / `unknown`. |
| `heating_system_type` | enum | `combi-boiler` / `conventional-boiler` / `system-boiler` / `heat-pump-ash` / `heat-pump-gsh` / `storage-heaters` / `district-heating` / `open-fire-only` / `none` / `unknown`. |
| `heating_system_description` | string | Verbatim agent text; predicate-level evidence for the enum extractions above. |
| `epc_band` | enum | A/B/C/D/E/F/G. Already implicit in energy study; making explicit as Craidd predicate. |
| `epc_score` | numeric | 1–100. |
| `council_tax_band` | enum | A–I (Wales has I). |
| `tenure` | enum | `freehold` / `leasehold` / `share-of-freehold` / `commonhold`. |
| `bedrooms` / `bathrooms` / `reception_rooms` | numeric | Standard agent metadata; treat as agent-stated (medium confidence). |
| `listing_status` | enum | (Belongs on `listing` entity not `building` — listed for completeness.) |

Until v0.2 ships, BRA v2 should:

- **Build stage 1 (discovery) and the snapshot+evidence half of stage 2 now.** Hashed evidence is schema-agnostic. Image bytes and verbatim descriptions are captured under `restricted` visibility per §3b regardless of schema state.
- **Hold draft claims in `claims.draft.json` marked `pending_schema: v0.2`.** Curator review picks them up once v0.2 lands.
- **Avoid claim extraction against v0.1 predicates** beyond what already works (address, postcode) — don't force-fit listings into building-claims.

Result: BRA v2 is partially shippable immediately (discovery + evidence capture, including image and synopsis capture) and fully shippable once v0.2 lands.

### 6.5. Cross-domain value: floor area feeds the energy study

The DEC-correction round on 2026-05-11 surfaced that anchor-load demand in the energy study dashboard was ~30× understated because TM46 benchmarks had been applied with 100–200 m² default floor area wherever the EPC API returned no match. The four-tier confidence hierarchy that came out of that work explicitly named "TM46 + default floor area" as tier 4, so it could be targeted by future corrections.

**Pilot finding 2026-05-12 reshapes this story (for the better).** Headline GIA is missing on both pilot listings ("Ask agent"), but **room-by-room dimensions are stated for every room** with metric values. Summing room areas gives a reliable internal floor area — actually *more* trustworthy than agent-stated GIA, which is often rounded up. For Beudy Talywaen the computed sum is ≈107 m²; for the Grade II listed 2-3 Heol y Bont it is ≈365 m² across three sub-units.

This means **BRA v2's `floor_area_m2` claims (basis `computed-from-room-dimensions`) become a new tier-3 source for the energy study's default-floor-area placeholder rows**, via the existing proposal queue. Agent-stated GIA, when present, is captured as a secondary corroborating claim.

Flow: BRA v2 scrapes listing → parses structured room list → sums metric room areas → extracts `floor_area_m2` with basis `computed-from-room-dimensions` → resolves subject to existing building → drafts proposal → curator reviews → on accept, claim lands in Craidd → energy study's `craidd_client.find_by_uprn()` reads it → `apply_dec_corrections.py` (or its successor) coalesces it over the default-area placeholder → segment viability bands recompute.

No code change to the energy study side is strictly needed beyond what's already in place — the read API contract is already there. BRA v2 becomes another contributor to the same proposal pipeline that the energy study uses. This is the architectural point of the Llys/Craidd separation working in practice across domains.

## 7. Risks

1. **Aggregator TOS.** Rightmove, Zoopla, OnTheMarket explicitly prohibit scraping. Agent-direct sites are safer (most have no robots.txt restriction; many publish listings under explicit "for circulation" terms). Default policy: **agent-direct first, aggregators only with explicit per-aggregator justification recorded in the manifest.** This is one of the open questions below.
2. **Photo and floor-plan rights.** Bytes are captured for curator review only, never republished. Handling specified in §3b: `restricted` visibility on all image evidence, URLs and hashes public, descriptive text (what the floor plan shows) is what becomes canonical, not the image itself. The read API must refuse to serve restricted-visibility bytes.
3. **Subject-resolution false positives.** Auto-binding a listing to the wrong building corrupts the canonical record. Strictness over recall — the unresolved queue is the right default, not a failure mode.
4. **Schema lag.** Proposing claims into a schema that can't yet model them is sterile. Stage 1 is safe; stage 2 claim-extraction waits for v0.2.
5. **Welsh-language gap.** Agent narratives are almost always English-only. Honest `cy: null` is the correct default — no placeholder, no machine translation.
6. **Volume.** LL40 market is small (~30–100 sales/yr from HMLR data plus rental stock). Tens of listings, not thousands. Cost and load are negligible.

## 8. Open questions — resolved 2026-05-12 (Code side, step 5 of build)

All five open questions were closed during the Code-side production-pilot session on 2026-05-12. Recording the resolutions here; the unresolved framing of each item is preserved as a strikethrough comment for the audit trail.

- **(a) Cadence.** ~~Weekly default proposed. Sold-archive pages probably need only monthly; new-listing detection benefits from daily. Should runs be configurable per agent in the manifest?~~ **Decided 2026-05-12: yes, per-agent cadence in the manifest.** The `config/agents/<id>.yaml` carries a `cadence` field with per-page-type granularity, e.g. `cadence: {listings: weekly, sold_archive: monthly, rentals: weekly}`. Curator can tune per agent. Matches the design intent that each agent's site-shape — including its refresh discipline — lives in its manifest.
- **(b) Aggregator inclusion.** ~~Default: agent-direct only. Pilot (2026-05-12) confirmed this is the right call — Rightmove's footer explicitly states "Rightmove prohibits the scraping of its content", and **Walter Lloyd Jones alone covers ~68.7% of LL40 stock** through its own 10ninety platform (walterlloydjones.10ninety.co.uk), with downloadable PDF brochures likely richer than the Rightmove rendering. Recommendation upgraded to firm: agent-direct only; aggregators stay opportunistic / out-of-scope unless a specific business case is signed off later.~~ **Decided 2026-05-12 (Cowork pilot, locked by Code-side robots.txt finding): agent-direct only.** Aggregators are out-of-scope. Furthermore, the production-pilot robots.txt check (see §11) extended the restriction to the back-office 10ninety subdomain itself — the Nimble agent runs only against the public-site host `www.walterlloydjones.co.uk`. Aggregator inclusion stays opportunistic-only behind a future per-aggregator business case.
- **(c) CLI placement.** ~~The cli-design.md memo holds the line at six narrow `craidd-*` CLIs and **no BRA CLI exists yet**. Options: (i') create a new top-level `bra` CLI with sub-commands (`bra listings` now, `bra history` when v1 ships); (ii) extend `craidd-fetch` to accept a `--source=listings` mode, keeping six CLIs but stretching `craidd-fetch`'s meaning beyond "fetch evidence for a known subject"; (iii) standalone `bra-listings` CLI with no umbrella. Recommendation revised: **(i')** — accept a seventh top-level CLI on the grounds that BRA is a coherent workflow unit (research → propose), not a fetch primitive. Justified seventh CLI, not a sprawl.~~ **Decided 2026-05-12: (i') new top-level `bra` CLI with sub-commands.** `bra listings` ships for v2; `bra history` slots in cleanly when v1 ships. Already recorded in `design/architecture.md` §6.14 as part of the BRA charter. The seventh CLI is justified — BRA is a coherent workflow, not a Craidd primitive — and the six-CLI line in `cli-design.md` was about avoiding sprawl, not a hard ceiling.
- **(d) Agent identity.** ~~Should `agent` be a v0.2 Craidd entity type, or remain config-only allowlist? Recommendation: entity. Agents change ownership; agent identity matters for `sale_record` provenance; the discipline of treating sources as entities (already established in v0.1 §10) extends naturally.~~ **Decided 2026-05-12: `agent` is a v0.2 Craidd entity type.** Agents become first-class entities with their own claims (name, branch, address, founded_year, parent_company, etc.). Agent identity is provenance for `sale_record` and listing claims. Build-order note: v0 / v0.1 use the config-only allowlist (per the existing `seed/agents/dolgellau-agents.csv` draft → curator-approval workflow) as the interim. Promote to entity in v0.2 when schema lands. Add to the v0.2 backlog in `design/v0.1-schema.md` §10 alongside the existing item 4.
- **(e) Build order.** ~~Stage 1 (discovery) ships first. Stage 2-evidence ships next. Stage 2-claims waits for v0.2. Confirm.~~ **Decided 2026-05-12: confirmed.** Stage 1 (discovery script + curator allowlist) ships first. Stage 2-evidence (per-agent manifest + Nimble extraction + snapshot/hash, no claim writes) ships next. Stage 2-claims (proposal generation + subject resolution + `craidd-propose` calls) waits for v0.2 schema. This Code-side session ships stage 1 and the first manifest before stopping for review.

## 9. Proposed build order

1. **Stage 1 discovery script.** Nimble-driven candidate-agent enumeration → `seed/agents/dolgellau-agents.csv` draft. Pilot already surfaced 10 active LL40 agents with Walter Lloyd Jones at 68.7% market share.
2. **Curator review of allowlist.** Manual approval for v0; promoted to a craidd-propose pattern in v1 once `agent` entity type exists.
3. **Site-shape manifest authoring**, **starting with `walterlloydjones.10ninety.co.uk`** (the agent-direct site for the dominant agent — single manifest covers ~68% of LL40 stock and has no aggregator ToS friction). Then Savills, RG Jones, Purplebricks, and any others surfaced by discovery.
4. **Per-agent Nimble extraction workflows** generated via `nimble-agent-builder`. Snapshot + hash + minimal-metadata only.
5. **Parallel: v0.2 schema work** to land `listing`, `letting_record`, `agent`, finalise `sale_record`.
6. **Claim extraction + subject resolution + proposal-queue writes** once v0.2 ships.
7. **Scheduled tasks** for weekly per-agent refresh, with the run log feeding a status dashboard analogous to the Tŷ Newyddion review page.

## 10. Where this lives in the repo

```
design/
  bra-v2-estate-agents.md          # this document
src/
  bra/
    listings/                       # new package, sibling of bra/history
      discover.py
      scrape.py
      resolve.py
      proposals.py
config/
  agents/
    <agent_id>.yaml                 # one manifest per site shape
seed/
  agents/
    dolgellau-agents.csv            # discovery output
  listings/
    <source>/<listing_id>/          # snapshots
    _unresolved/queue.csv
    _runs/<timestamp>.jsonl
```

`architecture.md` updates needed at commit time:
- **Write a new §6.14 BRA charter.** As of the 2026-05-12 commit history the register holds 18 components and BRA has never been chartered — an earlier memory note that "BRA is the 20th component, chartered at §6.14" was a design-session snapshot that never made it into a repo commit. The correction is to write one new §6.14 BRA charter framed as a single component with versioned scope: v1 historic-source research packs + v2 estate-agent listings, **v2 as the active scope**. Register count goes 18 → 19, not 19 → 20.
- This document (`design/bra-v2-estate-agents.md`) becomes the canonical BRA design doc. No separate `design/building-research-agent.md` is needed; a v1 design doc can land later if/when v1 ships.

(Architectural choice: single charter, versioned scope. Keeps BRA as one component, not two with overlapping charters.)

---

*End of original Cowork handover. The Code-side production Nimble pilot ran later the same day and surfaced corrections — see §11 below.*

## 11. Addendum — production-pilot findings (2026-05-12, Code side)

After this design was sealed, the production Nimble pilot (step 4 of the BRA v2 build, Code side) probed the real site and surfaced corrections that supersede some literal claims in the body of this document. Treat this addendum as authoritative; the body above is preserved as the original Cowork handover.

**Host correction.** The public estate-agent site is `www.walterlloydjones.co.uk` — a server-rendered ASP.NET front-end. The `walterlloydjones.10ninety.co.uk` host (referenced in §8 open-q (b) and §9 build order) is the **10ninety back-office portal**, which 302-redirects unauthenticated visitors to a login page. Brochure PDFs and image assets are served from the 10ninety subdomain at `/PublicProperty/DisplayBrochure/{id}` and `/PublicPropertyMedia/DisplayImage/{id}` without auth, but see the robots.txt note below.

**robots.txt finding.** `www.walterlloydjones.co.uk/robots.txt` returns 404 (no stated restrictions on the public site). However, `walterlloydjones.10ninety.co.uk/robots.txt` is explicit:

```
User-agent: *
Allow: /DiaryFeed
Disallow: /

User-agent: facebookexternalhit
Allow: /PortalExports/DisplayImage
```

General crawlers are disallowed from the entire 10ninety subdomain. The asset endpoints the Cowork pilot anticipated using (brochures, high-res images) are within the disallowed scope.

**Decision (curator, 2026-05-12).** Respect the 10ninety robots.txt absolutely. The Nimble agent extracts only from `www.walterlloydjones.co.uk` and treats brochure-PDF and 10ninety-hosted media URLs as out-of-scope. We lose richer brochure capture; we keep the verbatim narrative, room-by-room dimensions, and whatever inline images the public site itself serves. This is the cleanest posture for a place-based trust dataset whose first BRA v2 action should not be a robots.txt breach. If/when explicit consent is obtained from Walter Lloyd Jones & Co. (Bridge Street, Dolgellau — same street as Tŷ Newyddion), the 10ninety asset endpoints can come back into scope as a manifest update.

**URL patterns confirmed by production pilot:**

- Listing index (sales): `https://www.walterlloydjones.co.uk/properties/?page={N}&pageSize=50&propInd=S&businessCategoryId=1&searchType=list` — swap `propInd=L` for lettings.
- Detail page: `https://www.walterlloydjones.co.uk/property/?Id={numeric_id}&propInd=S` — case-sensitive `Id`. The numeric id is the 10ninety internal property id and is the URL key; the agent reference `RS####` (the §3a Tier A `listing ID (agent)` field) lives in the page body as `Reference: RS####`.
- No JS rendering required — the site is server-rendered ASP.NET.
- No structured `listing_events` exposed on the detail page — `listing_events` capture (per v0.2 backlog item 4) requires the BRA v2 pipeline's own delta-on-recurring-crawl, not direct extraction.

**Field-availability deltas from §3a (production pilot, RS3220 / Id=4058 used as canonical sample):**

- Confirmed present on the public site: address; agent ref (`RS3220`); asking price; tenure; branch; bedrooms/bathrooms inferable from room labels; **room-by-room metric dimensions** (the primary basis for `floor_area_m2` per §6.5 — confirmed at production scale); garden details; heating fuel + verbatim heating description; council tax band; parking, accessibility, rights, broadband, water, sewerage as bullet-point fields; EPC band (letter only); full narrative description; lat/lng coordinates; full RICS measurement disclaimer.
- Confirmed absent from the page (must come from elsewhere or remain null): headline GIA (confirms the §3a primary-extraction strategy is correct); EPC numeric score (only band letter visible — score requires a separate EPC API fetch); year built / period as a structured field; `planning_restriction` as a structured field; `epc_exempt` as a structured field; storeys as a structured field (inferable from "GROUND FLOOR" / "FIRST FLOOR" room-label sections only); listing-events history.

The structured absences are honest gaps. The narrative text often contains those facts; the §3a Tier C verbatim-capture discipline is what preserves them. The Tier A/B catalogue stands; some fields will be sparsely populated when extracted from this site shape and will need to be enriched from other sources (Cadw for listed-building status, EPC API for numeric score, etc.).
