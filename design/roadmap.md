# Awen / Town Dataset — iterative roadmap

**Status:** first full draft, for second-opinion review.
**Date:** 2026-05-15
**Companion docs:** `constitutional-framework.md` (the ecosystem constitution — Track B deepens this), `architecture.md` (the Town Dataset instance — Track A implements this), `cli-design.md` §6 (the build order Track A follows), `v0.1-schema.md` §10 (the v0.2 schema backlog).

---

## 1. What this document is

This is a living roadmap for two parallel bodies of work: building the Town Dataset as a working instance, and deepening the constitution that instance conforms to. It exists because the project has reached the point where those two things genuinely diverge — there is now shipped foundation code, and there is a constitution with named open decisions — and without a single document holding them in view it would be easy to push one forward while the other quietly goes stale.

The roadmap records *sequence and dependency*, not dates. It is revised every iteration rather than run against a fixed plan. When an item lands, the next iteration's version of this document reflects what was learned, not what was forecast.

What this document is not: a schedule, a feature commitment, or a substitute for the discipline already in place. Track A items still pass through the six-question charter in `architecture.md` §5; Track B items are still named decisions in the constitution's §12 register. The roadmap sequences the work; the charter and the register govern it.

## 2. How to read this roadmap

Four reading rules.

**Two tracks, run in parallel.** Track A is Town Dataset instance implementation — the curator tooling, the APIs, the schema extensions. Track B is constitutional deepening — sharpening the framework's treatment of obligations, contradictions, uncertainty, and federation. The two are not sequential. Track B is deliberately kept alongside Track A rather than after it, because Track B is what stops Track A from hard-coding instance-specific decisions that other Awen instances will need to vary. A contradiction model invented purely for Dolgellau buildings would not survive contact with construction obligations; better to deepen the constitution in step with the instance than to retrofit it later.

**Iteration-versioned, not dated.** Items are grouped by schema iteration — v0.1, v0.2, v0.3 — aligned to the versioning the project already uses for the schema. There are no deadlines anywhere in this document, and that is intentional. The charter discipline resists building ahead of demonstrated need; a dated roadmap would quietly reintroduce exactly that pressure.

**Now / next / later.** On top of the iteration versioning, each item carries a coarse banding — **now**, **next**, or **later** — to signal intent and ordering without implying a date. "Now" means it is the active or immediately-next piece of work. "Next" means it is queued behind a clear dependency. "Later" means it is real, scoped, and deliberately deferred. The banding is a statement of focus, not a commitment to a calendar.

**Charter-gated.** Every Track A item references its `architecture.md` charter or its `cli-design.md` §6 build-order slot. Every Track B item references its entry in the constitution's §12 open-decisions register. An item that cannot point at one of those is not ready to be on the roadmap — it is still a thought, and belongs in discussion, not here.

## 3. Track A — Town Dataset instance implementation

Track A is the demonstrator becoming real. The foundation — the schema layer, the storage layer, and `craidd-init` — shipped on 2026-05-15 and runs live on the Pi at Arloesi Dolgellau, with the Tŷ Newyddion pilot record loaded and validated. What remains in Track A is everything between that foundation and a Craidd a curator can actually work in day to day, followed by the schema extensions the real data already demands.

### 3.1 v0.1 completion — finish the curator's working surface — *now / next*

The v0.1 schema is settled; what is missing is the tooling that turns it into a working system. The order below is `cli-design.md` §6, which puts the proposal-and-review loop before any automation so the workflow is learned by hand before it is scaled.

- `craidd-propose` — **now.** The next component to build, off the freshly-merged `main`. Manual proposals first; no review tool needed to start using it.
- `craidd-review` — **next.** Turns the proposal queue into canonical claims — it is where curator judgement enters the system as the source of truth.
- `craidd-fetch` — **next.** Automates source snapshotting and provenance recording. Until it exists, sources are created by hand through `craidd-propose`.
- Building Research Agent v1 — **next.** Per-building research packs. BRA v2 (estate-agent listings) is already in `src/bra/`; v1 is the per-building workflow that shifts the dataset's growth bottleneck from compilation to review.
- `craidd-export` — **later.** The signed nightly snapshot. Only matters once there is enough canonical content to be worth exporting.
- `craidd-status` — **later.** The curator's working-day dashboard. Small and useful at any point; built when the working day demands it.
- The API surface beneath the CLIs — Read API, Write API, MCP server, Prawf logger, curator-identity layer — **next.** These are charter items in `architecture.md` §6 still to be built; the CLIs are thin wrappers over them, so they land in step with the tools that need them rather than as a separate phase.
- First real proposal batch — **next.** The eleven energy-study DEC-correction proposals waiting in `proposals-out/P-20260511-batch-001/` are the first end-to-end exercise of propose → review → Prawf on real contributor data. This is a milestone, not a component: it is how we know the loop works.

### 3.2 v0.2 — schema extension — *next / later*

The v0.2 backlog in `v0.1-schema.md` §10 is driven by data the project has already gathered and by lessons from the curator review. Each item below needs its own schema-version charter before it is adopted; the schema stays additive, with v0.1 retained as a superseded artefact.

- `listing` as an entity type distinct from `building`, with a `lists` relationship — **next.** The Cadw dual-listing lesson from the Tŷ Newyddion review: physical buildings and register entries are not one-to-one, and modelling listings as buildings is structurally wrong.
- `proprietor` and `sale_record` entity types, plus HMLR predicates — **next.** The OCOD foreign-ownership records and the 2,195-row Price Paid history are ready to ingest once the schema can hold them.
- `population_snapshot` entity type — **later.** The Census 2021 and Mid-Year-Estimate overlay corpus — sixteen tables and fourteen years of data — waits on this.
- EDTF date handling — **later.** Deferred from v0.1, which uses the hybrid `value_date` plus `value_date_text` plus `date_precision` approach for now.
- Floor- and unit-level sub-entities — **later.** Deferred from v0.1, which uses the `floor_scope` qualifier on tenancy and event claims as an interim.

### 3.3 v0.3+ — instance work that touches federation — *later*

Everything in Track A at v0.3 and beyond depends on the federation model landing in Track B first — see §4.4 and the dependency spine in §6. This is deliberately left as a placeholder rather than enumerated: the shape of multi-instance instance-work cannot honestly be specified until the constitution says how instances relate. Filling this section in is itself gated on §4.4.

## 4. Track B — constitutional deepening

The meta-instruction governing Track B, taken directly from the external review of the constitutional framework, is **deepen precision, don't expand breadth.** No new roles. No new layers. The five-role model — Llys, Craidd, IDRIS, Prawf, Craffter — and the layered view of the constitution are treated as settled. Every item below sharpens something the constitution already gestures at but currently leaves coarse. Each is a named decision destined for the §12 open-decisions register, and each is tagged with the cross-sector instance it unlocks, because that is the whole reason Track B is deliberate work and not abstraction for its own sake.

### 4.1 Obligation ontology — *now*

Decompose "obligation" from a single notion into a structured one: origin, duty-holder, discharge-condition, verification-authority, escalation-state, dependency-chain, and temporal-trigger. The Town Dataset barely needs this — a building's listed status is a thin obligation at most — but it is the precondition for any instance whose domain is fundamentally about who must do what, by when, and on whose say-so.

**Unlocks:** the construction instance — NEC4 obligation parsing, golden-thread evidence classification. **Banding:** now, because it is pure precision work with no dependency on other Track B items, and because construction is the fastest-moving cross-sector opportunity. It can and should run concurrently with Track A's v0.1 completion. **Constitution ref:** §12 — decision entry to be added.

### 4.2 Contradiction taxonomy — *next*

The constitution's current principle is flat: "contradictions co-exist." True, and load-bearing, but coarse. The deepening classifies a contradiction by *kind* — evidential (the sources disagree on fact), interpretive (the sources agree on fact but differ on meaning), temporal (both were true, at different times), jurisdictional (both are true, under different authorities), semantic (the disagreement is really about definitions), or unresolved (genuinely not yet classifiable). A Craidd that can say what kind of disagreement two claims have gives the curator a far sharper review surface than one that can only flag that a disagreement exists.

**Unlocks:** third-sector organisation mapping, where overlapping, partial, and contested records are the normal case rather than the exception. **Banding:** next — it depends on nothing, but obligation ontology is the priority pull for the construction timeline. **Constitution ref:** §12 — decision entry to be added.

### 4.3 Constitutional treatment of uncertainty — *next*

Distinguish, at the constitutional level, three things the current model can blur: absence of evidence, evidence of absence, and contested evidence. The `cy_coverage` view — which exposes honest Welsh-language gaps as a public metric rather than hiding them — is already the seed of this pattern. The deepening makes honest uncertainty a first-class, governed state across the framework, not a `NULL` that happens to be exposed in one view.

A distinction the deepening must hold firmly: confidence is not uncertainty. The schema's `confidence` field is a probabilistic weight on a claim that exists; epistemic uncertainty is about whether there is a claim to weigh at all. Many systems collapse the two — the framework should keep them apart, and §4.3 is where that separation is made constitutional.

**Unlocks:** third-sector mapping again, in concert with §4.2 — and more broadly, it is what lets any Awen instance be trusted *about its own gaps*. **Banding:** next, alongside §4.2. **Constitution ref:** §12 — decision entry to be added.

### 4.4 Federation model — *later*

How multiple Awen instances interoperate with no central authority — the constitution's "authority lives in the place" principle generalised from one place to many. This is deliberately the last Track B item. It should follow §4.1 through §4.3, because federating instances whose obligation, contradiction, and uncertainty models are still coarse would simply federate the coarseness. Precision first, then generalisation.

**Unlocks:** multi-instance operation — the Town Dataset, a construction instance, and a third-sector instance co-existing as a federation rather than as three databases sharing a filesystem on the Pi. **Banding:** later, iteration v0.3+. **Constitution ref:** §12 — decision entry to be added.

## 5. Cross-sector value

Track B is the part of this roadmap that is easy to mistake for overhead, so it is worth being explicit about why it is not. Each constitutional deepening is the precondition for an Awen instance in another sector — the work in §4 is not the framework admiring itself, it is the framework earning the right to be used twice.

**Construction** is coming through fastest as an opportunity. A construction instance is fundamentally an obligation-tracking system — who owes what evidence, to whom, by when — and it cannot be honestly chartered until the obligation ontology in §4.1 exists. That dependency is the single most important line in this roadmap, and it is why §4.1 is banded **now** despite construction having no shipped code yet: the constitutional work has to lead the instance, not trail it.

**Third-sector organisation mapping** is the second opportunity in view. Its data is intrinsically messy — organisations overlap, records are partial, sources contest each other — so it needs both the contradiction taxonomy in §4.2 and the uncertainty treatment in §4.3 before an instance would be anything other than a misleadingly tidy picture of an untidy reality.

And the Pi at Arloesi Dolgellau is already scoped, in hardware terms, as the multi-domain demonstrator host rather than the Town Dataset's box. The federation model in §4.4 is what makes that scoping real: without it, "multi-domain" means three instances that happen to share a filesystem; with it, it means a genuine federation that embodies the constitution's central claim at the scale of many places, not one.

## 6. Sequencing and dependencies

The roadmap's spine, stated as dependencies rather than dates:

> **The load-bearing dependency: the construction instance charter is blocked on Track B §4.1 (obligation ontology).** This is the clearest expression of the roadmap's governance-first sequencing — the constitutional work leads the instance, it never trails it. Every other line below is ordering; this one is principle.

- Track A v0.1 completion has no Track B dependency. It proceeds now, starting with `craidd-propose`.
- Track B §4.1 (obligation ontology) also has no dependency, and is banded **now** so it runs concurrently with Track A v0.1 — the two do not compete for the same surface.
- The **construction instance charter** is blocked on §4.1. It cannot be honestly chartered before the obligation ontology exists.
- Track B §4.2 and §4.3 (contradiction taxonomy, uncertainty treatment) have no hard dependency on §4.1, but are banded **next** behind it because §4.1 carries the construction pull.
- Track A v0.2 schema work and Track B §4.1–§4.3 can run concurrently — they touch different documents and do not collide.
- Track B §4.4 (federation model) should follow §4.1–§4.3 — precision before generalisation.
- Track A v0.3+ federation-touching instance work is blocked on §4.4. Until the federation model lands, §3.3 cannot honestly be filled in.

```
Track A:  foundation ──▶ v0.1 CLIs/APIs ──▶ v0.2 schema ──────────────▶ v0.3+ instance work
             (done)        (now/next)         (next/later)                  (later) │
                                                                                    │ blocked on
Track B:  §4.1 obligation ──┬──▶ §4.2 contradiction ──┐                              │
             (now)          │      (next)             ├──▶ §4.4 federation ──────────┘
                            │   §4.3 uncertainty ─────┘       (later, v0.3+)
                            │      (next)
                            │ blocks
                            ▼
                  construction instance charter
```

## 7. Governance of the roadmap itself

Three questions about how this roadmap is owned were raised in the outline review and resolved as follows.

**Where Track B work lives.** For now, the constitution and this roadmap stay in the Town Dataset repo, alongside `architecture.md`. The constitution moves to its own repository when a second instance actually exists — at the point where it is genuinely shared infrastructure rather than this instance's context, the repository structure should reflect that, and not before.

**Who owns Track B decisions.** Huw, for now. Track B items are named constitutional decisions, and until the wider Awen commercial direction is settled with Richard Scott, the decision authority sits with Huw as project lead. This is recorded so it is a deliberate position and not an accident of who happened to be in the room.

**Iteration cadence.** This document is revised at each schema iteration boundary. The now/next/later banding is re-evaluated every revision; the iteration versioning is fixed to the schema versions and does not drift.
