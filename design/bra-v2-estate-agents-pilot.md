---
title: BRA v2 — Pilot Run Findings
status: pilot output
date: 2026-05-12
companion_to: bra-v2-estate-agents-design-handover.md
sample_size: 2 live listings (1 barn conversion, 1 Grade II listed mixed-use)
provenance_note: Fetched via direct web fetch — NOT the production Nimble path. Nimble CLI was unavailable in this Cowork sandbox. Production pipeline must use nimble-agent-builder per the design.
---

# BRA v2 — Pilot run findings

Two live LL40 listings scraped and scored against the §3a field catalogue. Sample is small but contrasting enough to expose the shape of the data: one barn-conversion holiday-let, one Grade II listed mixed-use town-centre property. Both Walter Lloyd Jones & Co., both on Rightmove.

**Headline:** field catalogue holds up. The single most useful finding is that **room-by-room dimensions are stated for every room even when headline GIA is "Ask agent"** — this changes (and strengthens) the cross-domain story for the energy study.

## 1. Market context (one-search discovery)

- 10 active agents marketing 99 properties in LL40, average asking £307,593, -9.4% YoY ([Homemove summary](https://homemove.com/estate-agents/ll40-2/)).
- **Walter Lloyd Jones & Co. dominates with 68 active listings — 68.7% market share.** Established 1905, Bridge Street, Dolgellau (same street as Tŷ Newyddion).
- Second tier: Savills (rural / country estates), RG Jones (Bala-based, premium-leaning), Purplebricks (online, ~4 listings).
- Aggregators: Rightmove, OnTheMarket, Zoopla — all carry Walter Lloyd Jones stock.

**Design implication:** the agent-direct allowlist for stage-1 can be very small (perhaps just 4–6 sites) and still cover ~95% of the LL40 universe. Walter Lloyd Jones is the priority site shape.

## 2. Listings scored

### 2.1. Beudy Talywaen, LL40 1TH — £299,999, 2-bed barn conversion

Source: [Rightmove 88003134](https://www.rightmove.co.uk/properties/88003134) · Agent ref RS3253 · Walter Lloyd Jones & Co.

| Tier | Field | Available? | Value |
|---|---|---|---|
| A | Address | ✅ | Beudy Talywaen, Dolgellau LL40 1TH |
| A | Listing ID (Rightmove) | ✅ | 88003134 |
| A | Listing ID (agent) | ✅ | RS3253 |
| A | Listing status | ✅ | Live |
| A | Listing date | ✅ | Added 02/05/2026 |
| A | Asking price | ✅ | £299,999 (Offers in Region of) |
| A | Tenure | ✅ | Freehold |
| A | Agent + branch | ✅ | Walter Lloyd Jones & Co., Dolgellau (Bridge Street, LL40 1AS) |
| A | Aggregator presence | ✅ | Rightmove (this fetch); brochure link to walterlloydjones.10ninety.co.uk |
| B | Floor area (stated GIA) | ❌ | "SIZE: Ask agent" |
| B | Floor area (computed from room dims) | ✅ | ≈107 m² (sum of 10 stated room areas) |
| B | Storeys | ⚠️ | 2 + mezzanine (inferable from room list) |
| B | Bedrooms | ✅ | 2 (1 en-suite) |
| B | Bathrooms | ✅ | 2 |
| B | Reception rooms | ✅ | 1 (open-plan sitting/dining) |
| B | Garden | ✅ | "Private garden" + narrative: patio front, lawn embankment side, paved patio rear, decking |
| B | Heating fuel | ✅ | Oil |
| B | Heating system type | ✅ | Oil-fired central heating; boiler in entrance hallway cupboard |
| B | Heating description (verbatim) | ✅ | "oil-fired central heating and double glazing" |
| B | EPC band | ✅ | D |
| B | EPC score | ❌ | Not surfaced |
| B | Council tax band | ⚠️ | Exempt (holiday-let status) — important caveat |
| B | Tenure restriction | ✅ | **Holiday let only — primary residence prohibited** (planning restriction) |
| B | Construction notes | ⚠️ | Implicit: barn conversion, exposed beams, double glazing |
| C | Full description text | ✅ | ~600 words verbatim |
| C | Room-by-room with dimensions | ✅✅ | 10 rooms, each with metric dimensions and feature list |
| C | Special features | ✅ | Exposed beams, far-reaching views, window seats, slate tiled floor, granite worktops |
| C | Front-elevation photo URL | ✅ | media.rightmove.co.uk/property-photo/3d0c96a68/88003134/3d0c96a68c8f59bc3adb4f4d768bec53.jpeg |
| C | Floor plan URL | ✅ | media.rightmove.co.uk/dir/property-floorplan/6ad71f751/88003134/6ad71f7510666a749b66773d5c8c3a79_max_296x197.jpeg |
| C | Total photo count | ✅ | 30 |
| C | Brochure (agent PDF) | ✅ | walterlloydjones.10ninety.co.uk/PublicProperty/DisplayBrochure/4084 |

### 2.2. 2-3 Heol y Bont, LL40 1AU — £499,995, Grade II Listed, 6-bed mixed-use

Source: [Rightmove 153526076](https://www.rightmove.co.uk/properties/153526076) · Agent ref RS3007 · Walter Lloyd Jones & Co.

| Tier | Field | Available? | Value |
|---|---|---|---|
| A | Address | ✅ | 2-3 Heol y Bont, Dolgellau LL40 1AU |
| A | Listing ID | ✅ | 153526076 / RS3007 |
| A | Listing status | ✅ | Live, reduced on 05/11/2025 |
| A | Status-change capture | ✅ | "Reduced on" — captures a lifecycle event |
| A | Asking price | ✅ | £499,995 (Offers Over) |
| A | Tenure | ✅ | Freehold |
| A | Use class | ✅ | "Commercial - holiday let" |
| B | Floor area (stated GIA) | ❌ | "Ask agent" |
| B | Floor area (computed from room dims) | ✅ | ≈365 m² across three sub-units (shop + 2-bed cottage + 4-bed bunkhouse) |
| B | Storeys | ✅ | 3 (per detailed room-list structure) |
| B | Bedrooms total | ✅ | 6 (2 cottage + 4 bunkhouse) |
| B | Bathrooms | ✅ | 4 |
| B | Garden | ✅ | "Yes" + narrative (paved patio area, parking for 8 vehicles) |
| B | Parking | ✅ | "Yes" — explicit ground-floor car park |
| B | Heating fuel | ✅ | Gas |
| B | Heating system type | ✅ | Gas-fired central heating, Worcester combi boiler (named) |
| B | Mains services | ✅ | Electric, Water, Drainage, Gas |
| B | EPC band | ⚠️ | Exempt (Listed Building) — a useful claim in itself |
| B | Council tax band | ✅ | A (£1,443.37) |
| B | Listed grade | ✅ | **Grade II Listed** (mentioned in key features and narrative) |
| B | Period | ✅ | "late 1700's" |
| C | Full description | ✅ | ~400 words verbatim + ~20 rooms with dimensions and feature lists |
| C | Special features | ✅✅ | Exposed beams & A frames, Inglenook fireplace, window seats, exposed floorboards, painted pitch pine panelling, slate flagged flooring, ornamental fireplaces, stained glass |
| C | Heritage features (gold for Awen) | ✅✅✅ | All character features explicitly enumerated — directly usable as building-history claims with quote-with-citation |
| C | Photos | ✅ | 32 photos |
| C | Floor plan | ✅ | 1 |
| C | Listing on Airbnb (cross-platform signal) | ✅ | Narrative explicitly states the property is also on Airbnb |

## 3. What the pilot proves

### 3.1. The field catalogue is sound — with two adjustments

1. **`floor_area_m2` extraction strategy changes.** Headline GIA is missing on both listings. But **room-by-room dimensions are stated for every room** with metric values. The right extraction path is: parse the room list, sum room areas, store as `floor_area_m2` with a new basis qualifier `computed-from-room-dimensions`. This is actually richer than agent-stated GIA — it reveals layout and is harder to round up. Add to the §3a Tier B floor area entry.
2. **`planning_restriction` predicate confirmed needed.** Beudy Talywaen's holiday-let-only restriction is structurally important — it materially affects use class, council tax, and saleability. Promote from "v0.2 candidate" to explicit v0.2 predicate.
3. **`epc_exempt` flag.** Listed buildings show EPC as exempt and the listing surfaces this as a positive feature. The Craidd should be able to record `epc_exempt: true` with reason (`reason: listed_building` / `reason: holiday_let`) — not just an absent EPC band.

### 3.2. Cross-domain win for the energy study — re-framed

Original §6.5 framing: BRA v2 supplies agent-stated GIA to displace the TM46 default-floor-area placeholder.

Pilot finding: BRA v2 supplies **computed-from-room-dimensions internal floor area**, which is more reliable than agent-stated GIA (less prone to rounding-up) and reveals layout. For Beudy Talywaen the computed total is ≈107 m² — well inside TM46's 100–200 m² default range but a real measurement, not a placeholder. For 2-3 Heol y Bont the computed total is ≈365 m² across three sub-units, dramatically larger than any default would have assumed for a Grade II listed mixed-use property.

This is genuinely useful to the energy study's tier-4 ("TM46 + default floor area placeholder") segment-correction work. **Story strengthens, not weakens.**

### 3.3. Surprises worth recording

1. **Walter Lloyd Jones runs a 10ninety-platform agent site** (walterlloydjones.10ninety.co.uk) that carries downloadable brochure PDFs. These brochures are likely richer than the Rightmove rendering and the URL pattern is predictable. **The site-shape manifest for Walter Lloyd Jones should target the 10ninety platform directly, not Rightmove** — same content, no aggregator ToS friction.
2. **Aggregator-direct gives status-change history "for free".** Rightmove labels listings "Added on..." vs "Reduced on..." — capturing this gives a free lifecycle event log for the listing entity. Worth a `listing_event` sub-entity inside the v0.2 `listing` type.
3. **Rightmove footer explicitly states "Rightmove prohibits the scraping of its content"** — confirms the agent-direct-first design decision. Aggregator inclusion (open question (b) in the design) probably stays "No" by default.
4. **Agent-side references (RS3007, RS3253) are stable** while aggregator IDs are aggregator-scoped. The `agent_listing_ref` predicate on the v0.2 `listing` entity should carry the agent's reference, not the aggregator's, as canonical.
5. **Photo and floor-plan URL patterns are predictable** on Rightmove: `media.rightmove.co.uk/property-photo/<hash>/<id>/<hash>.jpeg` and `media.rightmove.co.uk/dir/property-floorplan/<hash>/<id>/<hash>_max_296x197.jpeg`. Enumerable, hashable.
6. **The Grade II listing's narrative is straight-up Awen-grade source material** — quote-with-citation worthy for character features, period dating, mixed-use history (18-year shop tenancy, bunkhouse income, Airbnb listing). This is exactly the content the curator would otherwise compile by hand for a building-history record.
7. **Volume is genuinely small** — 99 active listings across the entire LL40 universe. A full weekly refresh would be tens of listings new/changed, not hundreds. Cost and load are negligible.

### 3.4. What's missing or hard

- **GIA headline** — workaround above; not a blocker.
- **EPC numeric score** — only the band surfaces; score requires the linked EPC certificate, which is a separate fetch via the EPC API (already in seed scripts).
- **Year built / build date** — only loosely stated ("late 1700's"). Listed Building entry on Cadw remains canonical; the listing is corroborative at best.
- **Construction materials** — surfaced via narrative ("slate flagged flooring", "painted pitch pine panelling") but not as structured fields. Stays Tier C / quote-with-citation.
- **Bedroom-per-floor breakdown** — inferable from room-list ordering but not explicit. Would require parsing the indented structure.

## 4. Recommendations folded into the design

Updates to commit into `bra-v2-estate-agents.md`:

1. §3a Tier B floor area entry: add `floor_area_basis: computed-from-room-dimensions` as a valid basis. Mark this as the *primary* extraction strategy for Rightmove/Walter-Lloyd-Jones-shaped listings.
2. §3a Tier B add: `planning_restriction` (string + structured enum `holiday_let_only` / `agricultural_tie` / `affordable_housing_only` / `none`); `epc_exempt` boolean + reason enum.
3. §3a Tier C add: `listing_events` array (each entry: `event_type: added/reduced/sold-stc/sold/withdrawn` + `event_date`) — captured trivially from aggregator state labels.
4. §6 schema implications: confirm `planning_restriction` and `epc_exempt` predicates needed in v0.2.
5. §6.5 cross-domain win: re-frame around computed-from-room-dimensions floor area, not stated GIA. Strengthens the story.
6. §3 stage-2 build order: **prioritise the walterlloydjones.10ninety.co.uk site shape first**, not Rightmove. Same content, no ToS friction, and it covers ~68% of LL40 stock in a single manifest.
7. §8 open question (b) "aggregator inclusion": pilot evidence supports the default-no answer. Aggregators stay opportunistic-only.

## 5. What I did not do in this pilot

- **Did not use the Nimble CLI** — unavailable in this Cowork sandbox. Used direct web fetch. The production path remains `nimble-agent-builder` per the design.
- **Did not snapshot to disk with hashing** — pilot is for richness-scoring, not evidence capture. The design's snapshot-with-sha256 discipline still stands for production.
- **Did not test the Walter Lloyd Jones direct site** (walterlloydjones.10ninety.co.uk) — second fetch hit Rightmove rate-limiting and time was short. Highly recommended next pilot target.
- **Did not test sold-archive pages** — both samples are live listings. Sold-archive richness is the next pilot scope.
- **Did not test rental listings** — same.

## 6. Sources

- [Beudy Talywaen on Rightmove](https://www.rightmove.co.uk/properties/88003134) — fetched 2026-05-12
- [2-3 Heol y Bont on Rightmove](https://www.rightmove.co.uk/properties/153526076) — fetched 2026-05-12
- [Homemove LL40 agent summary](https://homemove.com/estate-agents/ll40-2/) — for market context
- [Walter Lloyd Jones brochure platform](https://walterlloydjones.10ninety.co.uk/) — referenced from listing; not fetched this round
