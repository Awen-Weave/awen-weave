# Building Research Agent — design

**Status:** chartered in `architecture.md` §6.14 on 2026-05-12. This document is the full design. The Agent is **not yet built**; it slots into the build order as item 5 (see `cli-design.md` §7) after the proposal queue and review loop are working manually against a small set of claims.

**Companion documents:** `architecture.md` (the discipline), `v0.1-schema.md` (data model), `cli-design.md` (the six core CLIs), `sources-backlog.md` (per-source ingestion workflow), `client-contract.md` (Craidd client interface).

**Worked examples that motivated this design:** `seed/buildings/ty-newyddion-design/pilot-ty-newyddion.md` and `seed/buildings/county-hall-dolgellau/history.md`. The Agent's output should match the shape of those documents.

---

## 1. Purpose, in plain English

For every significant building in Dolgellau (there are roughly 190 listed plus an unknown number of non-listed-but-locally-significant ones), we want a structured, sourced, bilingual record of what is known. Today, producing such a record takes one curator-evening per building — reading the Cadw listing, finding the Wikipedia article if one exists, hunting Coflein, scanning local-history pages, drafting the narrative, mapping facts to schema claims. We have done this twice (Tŷ Newyddion, County Hall) and proven the pattern works. We have also proven the pattern is the bottleneck.

The Building Research Agent automates the source-gathering and first-draft compilation, so a curator-evening becomes curator-review of a draft rather than curator-research from scratch. The curator's judgement remains the source of truth; the Agent does the heavy lifting that doesn't require judgement.

**This is the point at which the Town Dataset becomes a system that scales.**

## 2. Awen role and discipline

The Agent is a **Llys (contributor-side automation)** component. It is a client of the Craidd, not part of the canonical store. It writes proposal claims; it does not write canonical claims. It uses `craidd_client.py` for transport. Its outputs flow through the standard curator-review queue.

Three disciplines, non-negotiable:

**Every claim cites a snapshotted source.** No claim in the Agent's output exists without an `evidence_uri` pointing at a file in the per-building `evidence/` folder. The file's SHA-256 hash is recorded in the source citation. If a future audit asks "where did this fact come from?", the answer is a path to a file the Agent saved on the day it ran.

**Synthesis quotes rather than paraphrases where it matters.** The Agent's narrative composition (the `history.md` file) may paraphrase context where the meaning is shared across sources. But every load-bearing factual claim — listed grade, address, build period, designer, dates, tenancies — quotes the source text or carries a direct citation. Paraphrase blurs accountability; quotation preserves it. This is the discipline that mitigates LLM hallucination risk.

**Welsh is honest, not auto-translated.** Where a source contains a Welsh form (Cadw bilingual records, Coflein occasional Welsh text, local sources), the Agent extracts it and tags `dialect: cy-GB-north` per project convention. Where no Welsh form is present, the Welsh field stays null. The Agent never generates Welsh text by translation — that's a curator decision, made against authoritative sources, not a machine inference.

## 3. Interface

### 3.1 Invocation

The Agent runs as a command-line tool. The user-facing name is **"Building Research Agent"**; the executable name is `building-research-agent` (long form) or `bra` (short alias).

```
bra <building-identifier> [options]

Identifier forms (any one):
  --uprn <number>                  OS UPRN lookup
  --address "1 Bridge Street"      free-text address
  --cadw <listing-id>              direct Cadw listing reference
  --name "County Hall"             building name + implicit Dolgellau scope

Options:
  --output-dir <path>              override default seed/buildings/<id>/
  --skip-fetch                     use existing snapshots in evidence/; only re-synthesise
  --skip-synthesis                 only fetch snapshots; don't compose history.md or claims
  --no-propose                     write history.md and claims.draft.json only; do not
                                   submit proposals to proposals-out/
  --max-sources <n>                cap the number of source fetches (default 12)
  --dry-run                        preview the source list and synthesis plan; fetch nothing
  --resume                         pick up a partially-completed run from its state file
  --verbose                        print fetch transcripts and synthesis intermediate steps
```

### 3.2 Output

The Agent creates a folder at `seed/buildings/<id>/` where `<id>` is derived from the building identifier (e.g. `ty-newyddion`, `county-hall-dolgellau`, `b-XXXXX-uprn-form` if no clean name is available).

```
seed/buildings/<id>/
├── README.md               # what this folder is, when it was generated, by what run
├── history.md              # human-readable narrative, modelled on Tŷ Newyddion / County Hall
├── claims.draft.json       # v0.1-schema-shaped proposal claims, one per fact
├── research-questions.md   # known unknowns the Agent surfaced for curator follow-up
├── evidence/               # raw fetched source snapshots
│   ├── cadw-<id>-<date>.html
│   ├── cadw-<id>-<date>.json
│   ├── blb-<id>-<date>.html
│   ├── coflein-<id>-<date>.json
│   ├── wikipedia-<name>-<date>.html
│   ├── … one per source
│   └── manifest.json       # file → SHA-256 hash, URL, content-type, accessed_at
├── inputs/                 # optional — curator-supplied source documents added before run
└── .agent-state.json       # run metadata; used for --resume and audit
```

If `--no-propose` is not set, the Agent additionally writes a batched proposal directory at `~/Awen/handovers/dolgellau-energy-study/proposals-out/P-<date>-bra-<id>/` (mirroring the energy study's batch convention) for `craidd-review` to pick up.

### 3.3 Exit codes and reporting

```
0   success — all stages completed
1   partial — some sources failed; history.md and claims.draft.json produced from
    what was fetched; failed sources logged in .agent-state.json
2   refused — building identifier could not be resolved, or curator declined to
    proceed at a confirmation gate (e.g. when sources disagree drastically)
3   error — Nimble unreachable, schema validation failure, write error
```

Every run prints a one-screen summary at the end: building identifier resolved to, sources attempted vs succeeded, claims drafted, evidence files written, research questions surfaced. A copy of that summary is in `.agent-state.json` for audit.

## 4. Pipeline — stages of a run

### Stage 1 — Resolve the building identifier

Whatever the user supplied (UPRN, address, Cadw ID, name) must resolve to enough information to drive subsequent source fetches. The Agent tries, in order:

1. If `--cadw <id>` was given, that's the anchor — fetch the Cadw listing first and read out the canonical address and (if present) building name.
2. If `--uprn <number>` was given, look up in `seed/output/uprn-lookup.csv` (produced by `seed/uprn-from-epc.py`); if not found, fall back to OS Open UPRN data; produce an address from that.
3. If `--address "..."` was given, attempt to match in the UPRN lookup and Town Dataset existing address claims for a known building.
4. If `--name "..."` was given, attempt Cadw search (by name + "Dolgellau"), then Wikipedia search, then a broader Nimble search to find the building.

The output of this stage is a *resolved building identity*: an address, a candidate Cadw listing ID (or "none"), and a candidate UPRN (or "none"). If no resolution is possible, exit code 2 with a clear message.

### Stage 2 — Source discovery and prioritisation

Given the resolved identity, the Agent builds a list of source URLs to fetch, in priority order. The list is *predictable* — the same building always produces the same source list, so re-runs are repeatable and comparable.

Sources in priority order:

1. **Cadw listed-building API** — direct lookup by listing ID. Highest confidence; statutory source.
2. **British Listed Buildings (BLB)** — public mirror of Cadw; useful as a stable URL anchor and corroboration.
3. **Coflein (RCAHMW)** — National Monuments Record of Wales; often has architect, build date, building type beyond what Cadw records.
4. **Wikipedia** — if an article exists; useful for wider historical context.
5. **People's Collection Wales** — pre-restoration photographs, archive material.
6. **Local-history pages** — curated allowlist: dolgellau.uk, dolgellau.wales, lmrs.org.uk, freepages.rootsweb.com/~alwyn, dolgellauaafc.co.uk, others added over time.
7. **News archives** — Cambrian News, North Wales Live / Daily Post, BBC Wales, restricted to articles that name the building.
8. **Gwynedd Council planning portal** — if the building has live planning applications visible.
9. **Curator-supplied inputs** — anything in `inputs/` is read and treated as a curator-authored source of `high` confidence.

The list is capped by `--max-sources` (default 12); excess lower-priority sources are noted but not fetched in this run, becoming research-question entries instead.

### Stage 3 — Fetch and snapshot

For each source URL in the list, the Agent uses Nimble (via the Nimble CLI or MCP server) to fetch the content. Each fetch:

- Saves the raw response to `evidence/<source-id>-<date>.<ext>`.
- Computes SHA-256 of the saved file.
- Records source URL, content-type, fetch timestamp, file path, hash in `evidence/manifest.json`.
- Submits the URL to web.archive.org for redundancy (recorded as `archive_url`).

If a fetch fails (4xx, 5xx, timeout, rate-limit), the Agent retries up to 3 times with exponential backoff, then records the failure in `.agent-state.json` and moves on. A failed fetch becomes a research question, not a fatal error.

### Stage 4 — Extract candidate facts per source

For each successfully-fetched source, the Agent extracts candidate facts. This is the structured-extraction step that produces inputs to the claim-drafting step.

For Cadw and BLB (structured listing data):

- `listed_grade` — directly from the listing.
- `listed_id` — the Cadw reference and BLB mirror reference.
- `address` — from the listing's address fields, both English and (where present) Welsh.
- `build_period` — Cadw's date assignment (e.g. "c.1885").
- `building_type` — Cadw's broad class.
- `architectural_description` — Cadw's full description, quoted verbatim into a single claim (with the source URL and accessed_at).
- `conservation_area` — if mentioned in the listing context.

For Coflein:

- `architect` (if recorded) — high-value answer to a common research question.
- `build_period` — corroboration or contradiction of Cadw.
- `historical_note` — narrative content extracted as a citation.

For Wikipedia:

- `historical_note` — wider context, dated facts about the building's history.
- `notable_event` — events tied to the building.

For news archives:

- `event` — change of use, closure, sale, refurbishment.
- `tenant_name` — occupancy changes documented in news coverage.
- `period_start` / `period_end` for tenancies.

For local-history pages:

- Confidence by default `medium` — corroborates higher-confidence sources, supplements where they're silent.

Every extracted fact is recorded with:

- The source it came from.
- The exact quoted text from the source.
- A confidence band (`high` for statutory sources, `medium` for secondary, `low` for unsourced or ambiguous).
- A pointer to the snapshotted source file.

### Stage 5 — Resolve contradictions; flag genuine uncertainty

Where two sources disagree on the same fact, the Agent records *both* as separate candidate claims with their respective sources. It does not pick a winner. Per the Awen contradictions-co-exist discipline, the curator handles resolution at review time, not the Agent at synthesis time.

Where a source's text is ambiguous (e.g. "thought to be 18th century" vs "18th century"), the Agent records the claim with the ambiguity flag in the note. Where a source is silent on a question we'd expect it to address (e.g. Cadw listing with no architect named), the Agent records a research question.

### Stage 6 — Compose `history.md`

The Agent composes the narrative document. Structure follows the Tŷ Newyddion and County Hall pattern: summary, listing facts table, setting and townscape, age/design discussion, building described, occupants through time, heritage status, wider context, open research questions, sources list.

Composition discipline:

- The summary paragraph is a synthesis but cites the listing for the headline facts (Grade, build period, current use).
- The listing table is verbatim from Cadw / BLB.
- The setting section uses curator-supplied or Cadw urban-character context where available; otherwise leaves a clear gap noted.
- The age/design section quotes the listing's architectural description.
- The building-described section is verbatim from the Cadw full description.
- Occupants-through-time is composed from news archives and local-history extractions, with each fact cited inline.
- Heritage status is from the listing.
- Research questions section enumerates the gaps the Agent found.
- Sources list every snapshotted file with its URL, accessed_at, hash, and a one-line note on what it contributed.

The document is markdown, designed to be read by humans first. It is the curator's primary review surface.

### Stage 7 — Draft schema claims

The Agent translates the extracted facts into v0.1-schema-shaped proposal claims, writing them to `claims.draft.json`. Each claim:

- Targets the building entity (existing entity_id if known, otherwise `subject_hint` with the resolved identity).
- Names the predicate (per `v0.1-schema.md` §3.5 starter set).
- Carries the extracted value, with bilingual fields where applicable.
- Cites a source by ID (which must already exist as a source entity, or be proposed alongside).
- Includes the `evidence_uri` pointing at the snapshotted source file.
- Sets confidence per the source hierarchy.
- Includes a note quoting the source text or explaining the inference.
- Status is always `pending` at draft time.

Tenancies and events that the source coverage reveals get their own entity drafts in the same file. A change-of-use event in 2016 becomes a `tenancy_of` claim (old tenancy ends) + an `event` entity + a `tenancy_of` claim (new tenancy begins).

The file is JSON, structured for `craidd-review` consumption.

### Stage 8 — Compose research-questions list

Anywhere the Agent surfaced a known unknown — silent sources, partial information, ambiguities, sources that disagreed without resolution — becomes a `research_question` entity in the output. The list is in `research-questions.md` for the curator's narrative review and in `claims.draft.json` for ingestion. These match the Tŷ Newyddion §9 / County Hall §9 patterns.

### Stage 9 — Optionally submit as proposal batch

If `--no-propose` was not set, the Agent writes the drafted claims to a batched proposals directory under the conventional path. Filename pattern matches the existing `P-YYYYMMDD-bra-<building-id>/` convention. The batch manifest summarises what's in it; `craidd-review` picks it up alongside other pending proposals.

If `--no-propose` was set, the Agent produces only `history.md`, `claims.draft.json`, and the evidence pack. The curator submits manually after review.

## 5. Synthesis model and hallucination discipline

The synthesis stages (composing `history.md` and drafting claims) use LLM inference. This is the part of the Agent most prone to error — fabrication, paraphrase-drift, confident-but-wrong statements.

Six disciplines mitigate this:

**Quote-not-paraphrase for load-bearing facts.** Architectural descriptions, listing texts, dated facts — these are quoted verbatim from sources with citation, not summarised. The composition prompt instructs the model to use quotation marks and explicit citations for any specific fact.

**Citation-required for every claim.** No claim enters `claims.draft.json` without a `source` field pointing at a real snapshotted file. The Agent's output validates against this rule before being written.

**Source-text-only context.** The synthesis prompt's input is the extracted source text plus the resolution. The model is not given freedom to assert facts beyond what the sources say. "I don't know" or "the sources do not say" is a valid output, and becomes a research question.

**Multi-source corroboration where possible.** Facts that appear in two or more sources get higher confidence than single-source facts. Facts that appear in only one source carry that source's confidence band.

**Explicit-uncertainty flagging.** The synthesis prompt instructs the model to flag any fact it composes with uncertainty ("approximately", "perhaps", "thought to be"). These flag-laden facts get a `low` confidence band by default.

**Curator review is the safety net, not the only discipline.** All of the above are layered before the curator sees anything. The curator should not be the sole defence against hallucination; they should be the final verification on a draft that's already been disciplined at composition.

In v1, the synthesis can use the Anthropic Claude API (Sonnet or Opus). In future, when the Pi is operational with the Hailo accelerator, smaller local models may handle structured extraction while the API handles narrative composition. The synthesis interface is abstracted so the underlying model can be swapped without changing the pipeline shape.

## 6. Integration with existing components

The Agent fits into the existing architecture as follows:

- **`craidd_client.py`** — the Agent uses the client library for transport. Every proposal it writes goes through `craidd.propose_claim()` (when `--no-propose` is not set) or matches the same JSON shape (when proposals are emitted to a batch directory).
- **`craidd-fetch`** — the Agent's fetch stage could either call `craidd-fetch` per source or use the shared snapshot logic directly. The latter is cleaner for batched runs; the Agent and `craidd-fetch` share a common snapshot library.
- **`craidd-review`** — the Agent's batched output is just another input to the review queue. The curator runs `craidd-review` and walks the proposals as normal.
- **`craidd-status`** — should surface "N pending batches from the Building Research Agent" alongside other queue stats.
- **`sources-backlog.md`** — when the Agent discovers a new source domain not yet in the backlog, it appends a queued-source entry there. This makes the source-discovery process visible and auditable.

The Agent does *not*:

- Write to `craidd.duckdb` directly. It is a contributor, not a curator.
- Accept its own proposals. The self-acceptance rule applies — the Agent's outputs go through the curator queue like any other contributor's would.
- Run automatically on a schedule in v1. Each run is curator-initiated.

## 7. Sequencing of building runs

For v1, the Agent runs one building at a time, curator-initiated. The recommended workflow:

1. Curator picks a building (or works from a prioritised list).
2. Curator runs `bra "<name>"` from the Town Dataset repo root.
3. The Agent fetches, synthesises, drafts, and writes a research pack (10-20 minutes for a typical building, depending on source count and network).
4. Curator opens `seed/buildings/<id>/history.md`, reads the narrative, spot-checks against `evidence/`.
5. Curator either runs `craidd-review` against the auto-submitted batch (default) or edits `claims.draft.json` first.
6. Per-claim accept/dispute/reject decisions become canonical claims via the normal review loop.
7. Building's research pack is committed to the repo as an audit artefact.

A prioritised list of buildings is its own design question. Initial candidates: the 14 viable heat-network segments' anchor buildings (gives the energy project richer per-building records); the 190 Cadw listed buildings (the canonical list of heritage-significant buildings); the buildings flagged as discovered anchors by the energy study (Coleg Meirion Dwyfor, Magistrates Court, Cefn Rodyn, old Ysgol y Gader). The Agent's value compounds as the list grows.

## 8. What the Agent does not do (and what comes later)

Out of scope for v1:

- **Multi-building batched runs.** Each run handles one building. A wrapper script could iterate the Agent over a list, but the Agent itself is single-building. Multi-building parallel runs are a v1.1 feature when network and rate-limit behaviour against Nimble is well-understood.
- **Real-time updates.** The Agent runs on demand; it does not watch for source changes. If Cadw updates a listing, the Agent doesn't notice until re-run. A v2 enhancement could subscribe to source feeds where they exist.
- **Image extraction.** The Agent doesn't process photos, plans, or maps from sources. Pre-restoration photographs (a common research question) are flagged but not retrieved. Image processing is a v2 capability.
- **Inter-building relationship discovery.** "Building X is adjacent to building Y" — the Agent doesn't infer relationships across buildings beyond what individual sources state. Cross-building synthesis is a v2 IDRIS-layer function, not BRA's job.
- **Disputed-claim resolution.** When sources disagree, the Agent records both and flags. It doesn't pick a winner. Curator-only territory.
- **Welsh-language synthesis.** As noted in §2, Welsh text is extracted from sources, never generated.

These constraints make the Agent useful in v1 and prevent feature creep. Each future capability gets its own charter and design document if added.

## 9. Open questions for review

1. **CLI naming.** I've used `bra` as a short alias and `building-research-agent` as the long form. The short form is quick but cryptic; the long form is descriptive but long to type. Alternative: `craidd-research` to fit the existing CLI family naming, accepting that this tool is bigger than the other CLIs. Worth a curator decision.

2. **State of `claims.draft.json` vs auto-submitted proposals.** Should `--no-propose` be the default (curator must explicitly authorise submission to the queue)? Or should submission be the default (curator must opt out)? I lean towards "submit by default" because the proposals are still pending and require review — they don't become canonical until `craidd-review` accepts them. But a more conservative default (require explicit submit) gives the curator a clearer veto point.

3. **Source allowlist governance.** Who decides which local-history sources are added to the Agent's curated list? In v1, this is the curator's judgement. In v2 (multi-curator), a governance process would be needed.

4. **Welsh-source fetching priority.** Where bilingual Cadw records exist, the Agent fetches both `lang=en` and `lang=cy` versions. Should this be automatic, or curator-flagged? My default: automatic. Welsh content where it exists should be captured by default.

5. **Cost of synthesis.** API-based LLM synthesis has per-run cost (API tokens). At 190 buildings × ~$0.50/run, the full Cadw-listed corpus costs roughly $100 to run through. That's a one-time bootstrap cost; re-runs are typically only triggered by source updates. Worth tracking in `.agent-state.json` so the curator knows the running total.

6. **Conflict with proposals already in flight.** What does the Agent do if `proposals-out/` already contains a pending proposal for the same building? In v0, the Agent appends; the curator handles deduplication at review time. In v1, the Agent should detect and warn ("3 proposals already pending for this building's address — add to or skip?"). Genuine design question for implementation time.

7. **Provenance for the Agent's *own* outputs.** Should each Agent-produced proposal carry an extra qualifier identifying which Agent run produced it? My suggestion: yes — `qualifiers.agent_run_id` traces the proposal back to the `.agent-state.json` for the run that produced it. Useful for audit and for re-running corrections.

## 10. What this document deliberately does not do

It does not specify the implementation language (Python is implied by the rest of the project, but the Agent could equally be Node.js or Go). It does not specify the LLM provider or prompt templates — those are implementation choices below the design level. It does not list every source URL or specify regex patterns for extraction. Those belong in code and configuration, not in this design.

The Agent's *shape* — what it consumes, what it produces, how it relates to the rest of the system, what it must never do — is what this document fixes. Implementation choices stay open until the build session.

---

**Next step:** when the Pi is operational and `craidd_client.py`, `craidd-init`, `craidd-propose`, `craidd-review`, and `craidd-fetch` are working against real hardware, the Agent becomes the next thing to build. See `cli-design.md` §7 build order.
