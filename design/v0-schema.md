# Dolgellau Town Dataset — v0 Claim Schema

> **Superseded by v0.1** (`v0.1-schema.md`) on 2026-05-10. Kept for audit per
> Awen principle: superseded design artefacts stay visible. Refer to v0.1 for
> the current schema. Decisions and worked examples in this file remain valid
> as they were at the v0 horizon; v0.1 is purely additive over v0.

**Status:** draft for review. Nothing implemented yet. Mark up freely.
**Date:** 2026-05-10
**Author:** Claude, drafting against Huw's brief.

---

## 1. Purpose and principles

The Town Dataset is the Craidd of the Awen demonstrator: a bounded, place-based, provenance-bound store of what is known about Dolgellau. v1 covers buildings and their histories.

Three principles are non-negotiable and shape the schema directly:

1. **Records are claims, not values.** A building's listed grade is not a fact; it is a *claim by Cadw, recorded on a date, with a citation*. Every row in the canonical store is structured this way.
2. **Contradictions co-exist.** Two sources can disagree about a building's date. The Craidd records both, marks them as competing, and lets a curator nominate (but not silence) the canonical one.
3. **Authority lives in the place, not the repo.** The Pi at Arloesi Dolgellau is the canonical store. GitHub holds schema, code, and design docs. If they disagree, the Pi wins.

What the Craidd is *not*: an analytical workbench. The energy study computes heat demand, segments, and grant tags — none of which live in the Craidd. The Craidd answers "what is the listed status of this building?" not "is this segment viable for a heat network?" The latter is a downstream view *of* the Craidd, not part of it.

## 2. Topology — where things live

```
┌─────────────────────────────────────────────┐
│ Pi at Arloesi Dolgellau    (canonical)      │
│   /srv/town-dataset/                        │
│     craidd.duckdb     ← claims + sources    │
│     prawf.duckdb      ← append-only log     │
│     proposals/        ← pending claims      │
│     evidence/         ← raw source files    │
│   Read API  :8080  (public, no auth)        │
│   Write API :8443  (curator auth, mTLS)     │
│   MCP server :8081  (read-only)             │
└─────────────────────────────────────────────┘
              ▲                ▲
              │ read           │ propose
              │                │
   ┌──────────┴────┐   ┌───────┴──────────┐
   │ Town Dataset  │   │ Energy study     │
   │ dev (laptop)  │   │ (laptop / repo)  │
   │ Cursor + Code │   │ continues as is  │
   └───────────────┘   └──────────────────┘

   GitHub: arloesidolgellau/town-dataset (private)
     ├── schema/       ← DDL, predicate registry
     ├── api/          ← FastAPI read + write services
     ├── client/       ← craidd_client.py (used by energy study + others)
     ├── design/       ← this doc and successors
     └── seed/         ← scripts to bootstrap from open sources
```

**Energy study explicitly stays where it is.** It does not move into the Town Dataset repo. It becomes a *client* of the Craidd. Two practical changes for the energy study over time:

- Where it currently reads `working/Dolgellau_buildings_clean.csv`, it gradually migrates to calling `craidd_client.list_buildings()`. The CSV stays as an interim cache.
- Where energy work uncovers a fact about a building that the Town Dataset should know (e.g. a corrected address, a missed listed-building flag), it submits a *proposal* via `craidd_client.propose_claim(...)`. That proposal sits in a review queue. It does not enter the canonical store until a curator accepts it.

Energy-specific data (EPC consumption, heat demand, segment heat density) stays in the energy study and **never** enters the Craidd. That's the boundary: per-building *attributes* go through the Craidd; per-building *analyses* stay with the analyst.

## 3. The schema

Five tables. Conceptually small; the discipline lives in how they're used.

### 3.1 `entity` — what subjects can be talked about

```sql
CREATE TABLE entity (
  entity_id     TEXT PRIMARY KEY,        -- TDS-DOL-B-00001 (Building), -S- (Street), -A- (Area)
  entity_type   TEXT NOT NULL,           -- 'building' | 'street' | 'area' | 'source' | 'person'
  uprn          BIGINT,                  -- where applicable, OS UPRN
  toid          TEXT,                    -- where applicable, OS TOID
  created_at    TIMESTAMP NOT NULL,
  notes         TEXT
);
```

Buildings get `TDS-DOL-B-NNNNN`. Streets `TDS-DOL-S-NN`. Areas (conservation areas, wards) `TDS-DOL-A-NN`. UPRN is the preferred external anchor where available; we don't *require* it because not every building has one.

### 3.2 `claim` — the heart of the system

```sql
CREATE TABLE claim (
  claim_id        TEXT PRIMARY KEY,            -- UUIDv7
  subject_id      TEXT NOT NULL REFERENCES entity(entity_id),
  predicate       TEXT NOT NULL REFERENCES predicate(name),
  value_text      TEXT,                        -- one of these populated
  value_int       BIGINT,
  value_real      DOUBLE,
  value_date      DATE,
  value_geom      GEOMETRY,                    -- via spatial extension
  value_cy        TEXT,                        -- bilingual string fields
  value_en        TEXT,
  source_id       TEXT NOT NULL REFERENCES entity(entity_id),
  recorded_by     TEXT NOT NULL,               -- curator id
  recorded_at     TIMESTAMP NOT NULL,
  confidence      TEXT NOT NULL,               -- 'high' | 'medium' | 'low'
  evidence_uri    TEXT,                        -- file://evidence/... or https://
  superseded_by   TEXT REFERENCES claim(claim_id),
  status          TEXT NOT NULL DEFAULT 'active'
                  -- 'active' | 'superseded' | 'disputed' | 'withdrawn'
);
```

Notes:

- A claim is never deleted. Withdrawal is a status change, recorded in Prawf.
- `superseded_by` lets a later claim replace an earlier one *by the same source*. If two *different* sources disagree, both stay active and the predicate has two competing claims — that's a contradiction, not a supersession.
- A canonical view (`current_claim`) materialises one row per `(subject_id, predicate)` using ranking rules: prefer claims marked `canonical` by a curator, else highest `confidence`, else most recent. The view never silences the others; it just picks a default.

### 3.3 `predicate` — controlled vocabulary

Predicates are not free-form. Adding a new one is a deliberate act, recorded in Prawf.

```sql
CREATE TABLE predicate (
  name             TEXT PRIMARY KEY,           -- 'listed_grade', 'address', 'build_year'
  value_type       TEXT NOT NULL,              -- 'text' | 'int' | 'real' | 'date' | 'geom' | 'bilingual'
  cardinality      TEXT NOT NULL,              -- 'single' | 'multi'
  description_cy   TEXT NOT NULL,
  description_en   TEXT NOT NULL,
  constraint_json  TEXT,                       -- e.g. {"enum": ["I","II*","II"]}
  added_at         TIMESTAMP NOT NULL,
  added_by         TEXT NOT NULL
);
```

Starter predicate set (v0 — to be challenged):

| name | type | cardinality | meaning |
|---|---|---|---|
| `address` | bilingual | single | Postal address (cy + en) |
| `geometry` | geom | single | Building footprint or point |
| `uprn` | int | single | OS UPRN |
| `building_type` | text | single | residential / commercial / etc — controlled enum |
| `floor_area_m2` | real | single | Total internal floor area |
| `build_year` | int | single | Year built |
| `build_period` | text | single | e.g. "Late C18" — used when `build_year` unknown |
| `original_use` | bilingual | multi | Historic use(s) |
| `current_use` | bilingual | single | Today's use |
| `listed_grade` | text | single | enum: I / II* / II |
| `listed_id` | text | single | Cadw Cof Cymru reference |
| `conservation_area` | text | multi | Names of CAs the building sits within |
| `name_cy` | text | single | Welsh name (e.g. Tafarn y Gader) |
| `name_en` | text | single | English name |
| `historical_note` | bilingual | multi | Free-text historical claim, citation required |
| `dialect` | text | single | Welsh dialect tag for cy values, default `cy-GB-north` |

`multi` cardinality means a subject can carry several active claims for that predicate (e.g. multiple historical notes, multiple original uses). `single` cardinality means the canonical view picks one.

### 3.4 `source` — citations as first-class entities

A source is itself an entity (so claims can be made *about* sources — when accessed, by whom, hash check etc.). Sources go in the `entity` table with `entity_type='source'`, and carry their detail in claims like any other subject.

Suggested predicates for sources: `title_cy`, `title_en`, `citation`, `url`, `licence`, `accessed_at`, `file_hash`, `organisation`.

Worked rationale: this is recursive on purpose. It means provenance about a citation (e.g. "this Cadw record was retrieved on 2026-05-09 with hash abcd1234") uses the same machinery as every other fact. The schema doesn't grow to handle source metadata.

### 3.5 `prawf_log` — append-only proof layer

```sql
CREATE TABLE prawf_log (
  log_id         TEXT PRIMARY KEY,             -- UUIDv7
  ts             TIMESTAMP NOT NULL,
  actor          TEXT NOT NULL,                -- curator id, or system
  action         TEXT NOT NULL,                -- 'claim_added' | 'claim_superseded' | 'claim_disputed'
                                               -- | 'predicate_added' | 'proposal_accepted' | etc.
  target_id      TEXT NOT NULL,                -- claim_id, predicate name, etc.
  payload_json   TEXT NOT NULL,                -- full snapshot of what changed
  prev_hash      TEXT,                         -- hash of previous prawf_log row
  this_hash      TEXT NOT NULL                 -- hash(payload + prev_hash)
);
```

Hash chaining gives a tamper-evident log without committing to a full blockchain story (which would be silly at this scale). Anyone can verify the chain from the most recent hash backwards.

`prawf_log` is the only table that is strictly append-only at the database level (enforced by trigger or by file permissions on the WAL). Everything else is "logically append-only" — you can update `claim.status`, but the change is mirrored in `prawf_log`.

## 4. Bilingual handling

**Dialect: Gogledd Cymru / North Wales Welsh.** All Welsh content in the Dolgellau Town Dataset uses north Wales register and vocabulary — local Dolgellau usage, not standardised forms or south Wales variants. This is structural, not stylistic: place names follow local form, descriptions are written in north Wales idiom, and any AI-generated Welsh must be checked against this constraint before being accepted as a claim. Curator review explicitly catches dialect drift. A predicate `dialect` (text, default `cy-GB-north`) may be attached to bilingual claims where the source is non-local Welsh, so the deviation is recorded rather than silently translated.

Two patterns, used deliberately:

**Pattern A — paired fields on a single claim.** For things that are inherently bilingual (an address, a building name), a single claim carries both `value_cy` and `value_en`. They came from the same source at the same time and are the same fact in two languages.

**Pattern B — separate claims, paired by predicate convention.** For things where the Welsh name and English name come from different sources (e.g. local tradition vs. OS map labels), use two predicates: `name_cy` and `name_en`. Each is its own claim with its own source. This is honest about asymmetric provenance.

Default to pattern A unless you have a reason to use pattern B. The reason is usually "the cy and en versions have different evidence trails."

A query for a building returns both languages by default; the API has a `lang=cy|en|both` parameter.

## 5. Read interface

A small read-only HTTP API on the Pi at port 8080, public, no auth. Read calls are not logged in Prawf — that's noise, not provenance.

```
GET  /buildings/{id}                # current canonical view
GET  /buildings/{id}/claims         # all active + superseded + disputed claims
GET  /buildings/{id}/provenance     # full source chain
GET  /buildings?listed_grade=I      # query by predicate
GET  /streets/{id}
GET  /sources/{id}
GET  /search?q=...&lang=cy
GET  /predicates                    # list controlled vocabulary
GET  /prawf?since=...               # public log of changes
```

Plus an MCP server on port 8081 wrapping the same endpoints, so Claude can be asked questions in Welsh or English and resolve them through the API.

The read API is the *only* way the energy study (or anyone else) sees Craidd data. No direct DB access from outside the Pi. This keeps the contract tight and means the storage engine could be swapped without breaking clients.

A `craidd_client.py` library wraps the read API for Python users:

```python
from craidd_client import Craidd
craidd = Craidd("https://craidd.dolgellau.local")

building = craidd.building("TDS-DOL-B-00027")
print(building.address.cy)          # "Sgwâr Eldon 12"
print(building.listed_grade)        # "II"
print(building.listed_grade.source) # cited source object
print(building.listed_grade.recorded_at)
```

## 6. Write interface — proposals and review

Direct writes to the canonical store are restricted to **curators** with mTLS certificates. **Contributors** also hold mTLS certs but theirs only authorise proposal submission, not acceptance — they cannot run `craidd-review`. The two-tier split is enforced by which actions the cert is allowed to sign, not by social norms. Contributors include the energy study's authenticated agent, future partner organisations, and named individuals; curators in v0 means Huw, with named additions recorded in the `entity` table.

A contributor cannot accept their own proposal even if elevated to curator later — the proposal carries the original submitter, and `proposal_accepted_by_self` is rejected at the API layer. This is the only place where the schema imposes a process rule rather than recording one; the rule exists because it is the entire point of the two-tier model.

The mechanism in both cases is the same — a **proposal queue**.

```python
craidd.propose_claim(
    subject_id   = "TDS-DOL-B-00027",
    predicate    = "listed_grade",
    value_text   = "II*",
    source       = {
        "title_en": "Dolgellau Energy Study, segment 27 site visit",
        "organisation": "Arloesi Dolgellau CIC",
        "accessed_at": "2026-04-12",
    },
    confidence   = "medium",
    evidence_uri = "file://evidence/seg27_visit_photo_042.jpg",
    note         = "Cadw record shows II but interior carving suggests II*. Worth checking.",
)
```

What happens:

1. The proposal is written to `proposals/` on the Pi (a JSON file, not a DB row — easy to inspect, easy to back up).
2. An entry goes into Prawf: `proposal_submitted`.
3. A curator periodically runs `craidd-review`, which walks the queue. For each proposal the curator can:
   - **Accept as canonical** — claim is inserted, possibly superseding existing; Prawf logs `proposal_accepted`.
   - **Accept as competing** — claim is inserted alongside the existing one; both stay active; the predicate now has a contradiction. Prawf logs `proposal_accepted_competing`.
   - **Dispute the existing claim** — adds a `disputed` marker on the existing claim, the proposal goes in as a new claim with status `active`. Prawf logs `claim_disputed`.
   - **Reject** — proposal moved to `proposals/rejected/` with reason. Prawf logs `proposal_rejected`. Submitter is told.
4. Every action is signed by the curator's key.

This is deliberately slow. That's the point. Awen's pitch is that authority is human and visible; the proposal queue is where that gets demonstrated. A claim entering the canonical store is never accidental.

For the energy study specifically: I'd suggest two patterns of proposal will dominate.

- **Geometry corrections** ("this building is 4 m north of where the postcode centroid puts it"). High-volume, low-controversy. Curator can batch-accept these with a single command if the source is the same.
- **Heritage exceptions** ("this building isn't on Cadw but is clearly listed/should be flagged"). Lower-volume, higher-stakes. Each gets individual review, often with a follow-up to Cadw.

A weekly review session on a Sunday evening probably handles the queue indefinitely.

## 7. Worked example — Building TDS-DOL-B-00027 (notional, segment 27 anchor)

This shows the same building represented as claims, with the energy study's data flowing in through proposals. Simplified, not all fields shown.

```yaml
# entity
- entity_id: TDS-DOL-B-00027
  entity_type: building
  uprn: 100100012345
  created_at: 2026-05-15T19:00:00Z

# active claims (current view)
- claim_id: 0190f3...
  subject: TDS-DOL-B-00027
  predicate: address
  value_cy: "Sgwâr Eldon 12, Dolgellau"
  value_en: "12 Eldon Square, Dolgellau"
  source: TDS-DOL-SRC-OS-NAMES
  recorded_by: hwt
  recorded_at: 2026-05-15T19:00:00Z
  confidence: high

- claim_id: 0190f4...
  subject: TDS-DOL-B-00027
  predicate: listed_grade
  value_text: "II"
  source: TDS-DOL-SRC-CADW-COFCYMRU
  recorded_at: 2026-05-15T19:00:00Z
  confidence: high
  evidence_uri: "file://evidence/cadw_2026_05_09.json#item=BL-1234"

- claim_id: 0190f5...
  subject: TDS-DOL-B-00027
  predicate: build_period
  value_text: "Early C19"
  source: TDS-DOL-SRC-RCAHMW-COFLEIN
  recorded_at: 2026-05-15T19:00:00Z
  confidence: medium
  note: "Coflein narrative says 'probably c. 1810–1830'"

# proposal from energy study, awaiting review
- proposal_id: P-0190f9...
  submitter: arloesi-dolgellau-energy-study
  subject: TDS-DOL-B-00027
  predicate: floor_area_m2
  value_real: 142.6
  source:
    title_en: "Dolgellau Energy Study EPC match"
    organisation: "Arloesi Dolgellau CIC"
    accessed_at: "2026-04-12"
  confidence: medium
  evidence_uri: "file://evidence/epc_match_audit_seg27_b27.json"
  status: pending
```

When the curator reviews and accepts this proposal, the floor area becomes a live claim with the energy study cited as the source. The Town Dataset doesn't store *heat demand* — that's the energy study's. But it does, after curator review, store *floor area*, with provenance back to the EPC match audit file.

## 8. Decisions and open questions

### 8.1 Decisions taken (2026-05-10)

**Welsh content policy: honest coverage.** The schema does *not* require `value_cy` to be non-null on bilingual claims. Welsh is stored when known, left null when no Welsh evidence yet exists. A `cy_coverage` view exposes the percentage of bilingual claims with Welsh populated, surfaced as a public metric on the read API. This is the Awen-coherent answer: be honest about gaps rather than invite placeholder Welsh.

**Welsh dialect: Gogledd Cymru / North Wales register** (see §4). Curator guidance includes a short north-Wales style note. Non-local Welsh sources are tagged with `dialect ≠ cy-GB-north` rather than silently retranslated.

**Geometry policy: ingest postcode centroids as low-confidence, supersede later.** Postcode-centroid points from the energy study enter the Craidd as `geometry` claims with `confidence: low`, citing the energy study as source. When better evidence arrives (OS Open UPRN building points, GPS from site visits, or hand-placed points from aerial imagery), the better claim supersedes the centroid one. This is also the schema's first real demonstration of supersession in practice.

**Prawf scope: fully public.** The hash-chained Prawf log is exposed in full on the public read API at `/prawf`. Every claim addition, supersession, dispute, proposal acceptance, predicate addition, and curator action is visible to anyone. Curator activity is itself a public good in the Awen model — the openness *is* the pitch.

**Curator identity: two-tier (curators + contributors).** Curators have full powers: accept, dispute, supersede, retire predicates. Contributors can submit proposals and attach evidence but cannot accept their own proposals — the proposal queue is the only path their claims take to canonical. Maps cleanly to the existing proposal/review mechanism; prevents self-approval drift without imposing a heavier role hierarchy. v0 starts with Huw as curator; contributors are added by name, recorded in `entity` table with `entity_type='person'`.

### 8.2 Still open — for v0.1

1. **Energy study's read pattern.** Pull-on-demand via API, or nightly snapshot dump? API is cleaner; nightly dump is faster for batch analysis. Probably both, with the dump being a derived public artefact. Decide once the API is running.
2. **Predicate evolution.** Adding a predicate is deliberate. *Removing* one is harder — what happens to existing claims using a retired predicate? Soft-retire (mark as `deprecated`, keep claims queryable) is the likely answer, but v0.1 should write it down explicitly.

## 9. SQL appendix — DDL for v0

```sql
-- DuckDB-compatible. SpatiaLite needs minor adjustment.

CREATE TABLE entity (
  entity_id     VARCHAR PRIMARY KEY,
  entity_type   VARCHAR NOT NULL,
  uprn          BIGINT,
  toid          VARCHAR,
  created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
  notes         TEXT
);

CREATE TABLE predicate (
  name             VARCHAR PRIMARY KEY,
  value_type       VARCHAR NOT NULL CHECK (value_type IN ('text','int','real','date','geom','bilingual')),
  cardinality      VARCHAR NOT NULL CHECK (cardinality IN ('single','multi')),
  description_cy   VARCHAR NOT NULL,
  description_en   VARCHAR NOT NULL,
  constraint_json  VARCHAR,
  added_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  added_by         VARCHAR NOT NULL
);

CREATE TABLE claim (
  claim_id        VARCHAR PRIMARY KEY,
  subject_id      VARCHAR NOT NULL REFERENCES entity(entity_id),
  predicate       VARCHAR NOT NULL REFERENCES predicate(name),
  value_text      VARCHAR,
  value_int       BIGINT,
  value_real      DOUBLE,
  value_date      DATE,
  value_geom      GEOMETRY,
  value_cy        VARCHAR,
  value_en        VARCHAR,
  source_id       VARCHAR NOT NULL REFERENCES entity(entity_id),
  recorded_by     VARCHAR NOT NULL,
  recorded_at     TIMESTAMP NOT NULL DEFAULT NOW(),
  confidence      VARCHAR NOT NULL CHECK (confidence IN ('high','medium','low')),
  evidence_uri    VARCHAR,
  superseded_by   VARCHAR REFERENCES claim(claim_id),
  status          VARCHAR NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','superseded','disputed','withdrawn'))
);

CREATE INDEX claim_subject_predicate_idx ON claim(subject_id, predicate);
CREATE INDEX claim_status_idx ON claim(status);

CREATE TABLE prawf_log (
  log_id         VARCHAR PRIMARY KEY,
  ts             TIMESTAMP NOT NULL DEFAULT NOW(),
  actor          VARCHAR NOT NULL,
  action         VARCHAR NOT NULL,
  target_id      VARCHAR NOT NULL,
  payload_json   VARCHAR NOT NULL,
  prev_hash      VARCHAR,
  this_hash      VARCHAR NOT NULL
);

CREATE VIEW current_claim AS
  SELECT * FROM claim
  WHERE status IN ('active','disputed')
  AND superseded_by IS NULL;
```

---

**Next steps after this draft is reviewed:**

1. Mark up the open questions in §8.
2. Lock the starter predicate set in §3.3.
3. Decide: bootstrap a real `town-dataset` repo on GitHub now, or stay in `town-dataset-design/` for one more design iteration.
4. Pick a single street as the pilot ingestion target and walk one building through the full pipeline by hand (Cadw + Coflein + OS + local archive), to stress-test the schema before automating.
