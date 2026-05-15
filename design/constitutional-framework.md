# Craidd Constitutional Reference Framework

**Status:** v0.1 — working position. The ecosystem-level constitution for the Awen framework: the governance and epistemic principles that every Awen instance conforms to, independent of domain or runtime.
**Date:** 2026-05-15.
**Companion documents:** `architecture.md` (the Dolgellau Town Dataset's instance architecture, which conforms to this document); `v0.1-schema.md` (that instance's data model); `cli-design.md` (that instance's curator tools).

---

## 0. Status, and relationship to `architecture.md`

This document is the **ecosystem-level constitution** for the Awen framework. It defines the governance and epistemic principles — computable trust, bounded authority, contradiction handling, supersession, longitudinal coherence — that hold across every Awen instance.

`architecture.md` is **not** superseded by this document. It is the **instance architecture** for the first Awen instance, the Dolgellau Town Dataset: it names that instance's concrete components, their charters, and the boundaries between them. Future instances (§7) will each have their own instance architecture, conforming to this constitution.

The division of labour:

- **This constitution** governs cross-instance principles: what a claim is, what authority means, how contradiction persists, how supersession is recorded, how legitimacy is established. It names no components and specifies no implementation.
- **An instance architecture** governs one instance's components: storage, schema, CLIs, APIs — what each consumes, produces, and must not do.

The **Awen role map** — Llys, Craidd, IDRIS, Prawf, Craffter — is shared between this document and every instance architecture. It is defined here (§2) and applied there.

**Resolution rule.** Where an instance architecture and this constitution appear to disagree, the disagreement is a defect to be resolved deliberately, not silently worked around. The constitution holds on matters of governance principle; the instance architecture holds on matters of that instance's concrete component design. A genuine principle-level conflict is settled by amending this document through the process in §12. This mirrors `architecture.md`'s own discipline: a contradiction between foundational documents is a bug, fixed in the open.

---

## 1. Constitutional position

### 1.1 Foundational principle

The Awen framework does not seek to replace existing ontology foundations, construction semantics, or civic data models. It introduces a **governance and epistemic layer** that operates *across* existing semantic substrates, to support computable trust, provenance, bounded authority, obligation management, supersession, contradiction handling, longitudinal coherence, explainability, and auditability.

The intention is not to create a new universal ontology. It is to create constitutional mechanisms capable of **governing assertions made across multiple ontological systems**.

### 1.2 The core distinction

Most ontology and digital-twin systems focus on what entities exist, how they relate, how lifecycle information is exchanged, how semantics interoperate.

The Awen governance layer focuses on a different set of questions: who may assert a claim; under what authority; with what evidential basis; how a claim is challenged; how obligations propagate; how contradictions coexist; how supersession occurs; how legitimacy is established; how longitudinal trust is maintained.

This distinction is fundamental. The novel contribution is not semantic representation — it is **governance over semantics**.

### 1.3 Constitutional orientation

The system is: governance-first, provenance-aware, longitudinal, append-conscious, inspectable, bounded, human-accountable, federated, interoperable.

The system is **not**, and is not intended to become: a replacement BIM platform; a universal data model; a replacement common data environment; a fully autonomous reasoning engine; an opaque optimisation layer.

It operates as a constitutional and governance layer across existing systems — never as their replacement.

---

## 2. Layered architecture, the Awen role map, and runtime independence

### 2.1 The layer model

The constitutional architecture separates concerns into distinct layers, so that implementation detail never hard-codes governance assumption:

| Layer | Purpose |
|---|---|
| Semantic substrate | Existing ontologies and standards (PROV-O, CCO, ISO 19650, …) |
| Governance | Authority, legitimacy, contradiction, supersession |
| Evidence and proof | Evidence chains and their verification |
| Reasoning | Interpretation and orchestration over governed claims |
| Policy and orchestration | Cross-cutting governance policy |
| Runtime | DuckDB, APIs, ingestion, interfaces |

### 2.2 The Awen role map

The Awen framework also has a **role map** — five roles, each a distinct function:

- **Llys** — interaction, governance, accountability. How the system is talked to and the rules that govern change.
- **Craidd** — the place-based trust core. The canonical store of claims and the schema that shapes them.
- **IDRIS** — reasoning and orchestration over Craidd and Prawf.
- **Prawf** — obligation and proof. The append-only, hash-chained record of process.
- **Craffter** — advisory, pattern-level learning. Observation that never mutates the canonical record.

### 2.3 How layers and roles relate

The layer model (§2.1) and the role map (§2.2) are **two orthogonal views of the same system, not rivals.** Layers describe *stratification* — what sits on what. Roles describe *function* — what each part is for. A given component occupies one layer and performs exactly one role.

The cross-walk:

| Layer | Awen role(s) it expresses |
|---|---|
| Semantic substrate | External — no Awen role; substrates are inherited, not built |
| Governance | **Craidd** (the schema and store) and **Llys** (the authority and review machinery acting on it) |
| Evidence and proof | **Prawf** |
| Reasoning | **IDRIS** |
| Policy and orchestration | **Llys** |
| Runtime | No Awen role — runtime is implementation (§2.5) |

**Llys appears in two layers** — governance, and policy-and-orchestration — because Llys is the interaction-and-governance role, and governance is exercised at more than one stratum. This is not a category error; it is the consequence of layers and roles being orthogonal cuts. An instance architecture resolves it concretely: in the Town Dataset, the Write API and curator-identity layer (governance-stratum Llys) and the Read API and MCP server (interaction-stratum Llys) are distinct components, each performing the single Llys role at its own stratum.

### 2.4 Craffter under the constitution

Craffter is the one role that does **not** appear in the layer model — deliberately. Craffter is advisory pattern-level learning: it *reads* the governed record and emits separate advisory artefacts. It never writes to Craidd or Prawf, never carries authority, and is never part of the canonical record's lineage.

Craffter's constitutional status is therefore precisely that it is **bounded out** of the trust core. That boundary is itself a constitutional rule — one of the strongest the framework has — so Craffter belongs in this document not as a layer but as a **named exclusion**. An instance that allowed advisory learning to write to its canonical store would be in breach of the constitution, not merely of its own architecture.

### 2.5 Runtime independence

The constitutional layer must remain conceptually independent of the runtime: the DuckDB schema, the Python implementation, the ingestion tooling, the API structures, vector-retrieval systems, local-LLM infrastructure.

Runtime systems may evolve. The constitutional layer should remain stable.

This is the home of decisions such as DuckDB versus Parquet substrates, Python versus another language, whether and when to add vector retrieval or a local LLM. Those are **runtime questions** — taken on runtime merits — not constitutional ones. A change of storage engine or language does not change what a claim is, what authority means, or how contradiction persists. If a proposed change *would* alter those things, it is not a runtime change; it is a constitutional amendment, handled through §12.

---

## 3. Foundational ontology references

The framework inherits from and aligns with existing ontology and provenance work wherever practical, to avoid unnecessary reinvention while preserving interoperability. Each reference below carries a **constitutional position** — how the framework relates to it.

**Scoping note.** Of the references below, **PROV-O is the one directly relevant to the Town Dataset instance today** — it is a provenance ontology, and the Town Dataset's claim/source/Prawf model is, in effect, a provenance model. The construction-domain references (BFO, CCO, ISO 19650, IAO) are ecosystem-level and construction-instance-facing; they become load-bearing when the construction instance (§7) exists, and should not accrete onto the Town Dataset before then.

### 3.1 PROV-O — Provenance Ontology

Provenance semantics for entities, agents, activities, derivation, attribution, generation, invalidation. Aligns strongly with claims, evidence chains, authority attribution, supersession, derivation history.

**Constitutional position:** treated as a provenance *substrate*. The Awen governance layer extends provenance into governance — PROV-O describes *how something came to be*; the governance layer adds *who was permitted to assert it, on what authority, and how it may be challenged*.

W3C PROV-O — https://www.w3.org/TR/prov-o/

### 3.2 Basic Formal Ontology (BFO)

Upper-ontology discipline — continuants, occurrents, processes, roles, temporal existence.

**Constitutional position:** not formally adopted. Its distinctions are recognised as conceptual guidance for avoiding category confusion. Formal adoption is an open decision (§12).

https://basic-formal-ontology.org/ · https://basic-formal-ontology.org/bfo-2020.html

### 3.3 Common Core Ontologies (CCO)

Reusable mid-level structures — artifacts, facilities, information entities, roles, processes, agents.

**Constitutional position:** a reusable semantic substrate where practical — primarily for the construction instance.

https://commoncoreontology.github.io/cco-webpage/ · https://www.ontologyrepository.com/

### 3.4 ISO 19650 and digital-construction ontologies

Lifecycle and information-management semantics for construction — information containers, federated models, appointments, project roles, information exchanges.

**Constitutional position:** the framework does not seek to replace ISO 19650 semantics. Governance and evidential logic operate *across* those structures. Construction-instance-facing.

https://www.iso.org/standard/68078.html · https://digitalconstruction.github.io/

### 3.5 Information Artifact Ontology (IAO)

Information content entities — documents, data artefacts, information-bearing entities.

**Constitutional position:** a candidate substrate for modelling claims, specifications, reports, and evidence packages as information entities. Construction-instance-facing; relevance to the Town Dataset is unassessed (§12).

https://ncorwiki.buffalo.edu/index.php/BFO-Based_Data_and_Information_Ontologies

---

## 4. Constitutional lexicon

These are the governance primitives. The definitions are deliberately **domain-neutral** — they hold across every instance. Each is annotated with how it is **realised in the Town Dataset v0.1** today, so the lexicon stays grounded in working software rather than abstraction.

### 4.1 Claim

A bounded assertion regarding reality, interpretation, status, condition, obligation, or relationship. A claim may be supported, challenged, superseded, remain unresolved, or coexist with contradictory claims. **A claim is not equivalent to truth.**

*v0.1:* the `claim` table — every row carries `subject_id`, `predicate`, a typed value, `source_id`, `recorded_by`, `confidence`, and `status`.

### 4.2 Evidence

Material capable of supporting, contextualising, or challenging a claim — documents, measurements, imagery, sensor outputs, inspection records, contractual references, testimony, derived analysis. **Evidence does not guarantee validity.**

*v0.1:* `claim.evidence_uri` and the `evidence/` store; source entities carry the citation and visibility.

### 4.3 Authority

A bounded entity permitted to originate, validate, challenge, or govern claims within defined scopes. Authority is contextual, constrained, temporal, and challengeable. **Authority does not imply universal correctness.**

*v0.1:* the two-tier curator/contributor model; `claim.recorded_by`; the curator-identity layer (chartered, not yet built).

### 4.4 Obligation

A required condition, action, verification, or outcome arising from contractual, statutory, operational, or governance structures. Obligations may propagate, transfer, escalate, remain unresolved, or require evidence for discharge.

*v0.1:* **not modelled.** The Town Dataset is buildings and histories; it has no obligation logic. Obligation is anticipated for the construction instance (§7), where NEC4 and statutory duties make it central.

### 4.5 Provenance

The traceable lineage of how a claim, evidence item, or decision came into existence — origin, derivation, modification, attribution, validation, supersession history.

*v0.1:* `source_id` on every claim; the append-only `prawf_log`; source entities as first-class.

### 4.6 Supersession

The governed replacement of one claim by another. Supersession preserves historical continuity — superseded claims are not erased.

*v0.1:* `claim.superseded_by` and `status='superseded'`; the `current_claim` view filters to live claims without discarding the rest.

### 4.7 Contradiction

The coexistence of incompatible claims. Contradictions may persist legitimately until resolution or governance intervention. The system preserves contradiction visibility.

*v0.1:* `status='disputed'`; "contradictions co-exist" is an `architecture.md` principle — a curator nominates a canonical claim but does not silence the competing one.

### 4.8 Curator

A human steward responsible for the integrity, admissibility, and governance quality of a bounded knowledge domain. **Curators are not universal arbiters of truth.**

*v0.1:* Huw is the v0 sole curator; self-acceptance is forbidden at the write layer, which is why a second curator is structurally required.

### 4.9 Scope

The explicit boundary within which a claim, authority, or obligation is valid — spatial, temporal, contractual, organisational, regulatory, or semantic.

*v0.1:* `predicate.applies_to_types` (semantic scope); the bounded-domain discipline; the Town Dataset itself is a scoped instance.

### 4.10 Temporal validity

The period during which a claim, authority, or obligation is active or applicable. Temporal validity may overlap, expire, supersede, or remain disputed.

*v0.1:* `period_start` / `period_end` on tenancy and event entities; `value_date` with the `date_precision` qualifier.

---

## 5. Governance innovation boundary

This separates inherited semantics from governance-layer innovation, and constrains unnecessary ontology reinvention.

| Area | Constitutional position |
|---|---|
| Provenance semantics | Reused and extended |
| Lifecycle semantics | Reused |
| Construction semantics | Reused where practical |
| Information entities | Reused |
| Governance semantics | **Novel contribution** |
| Obligation ontology | **Novel contribution** |
| Evidence sufficiency | **Novel contribution** |
| Negotiated contradiction | **Novel contribution** |
| Bounded authority | **Novel contribution** |
| Longitudinal legitimacy | **Novel contribution** |
| Supersession governance | **Novel contribution** |

---

## 6. Cross-reference mapping layer

Conceptual mappings between external ontology concepts and Awen governance concepts. This is a **live section** — it evolves incrementally. The PROV-O rows are active for the Town Dataset today; the others are seeded for the instances that will need them.

| External concept | Awen equivalent | Reuse position | Notes |
|---|---|---|---|
| `prov:Entity` | Claim / Evidence | Partial reuse | governance extension required |
| `prov:Agent` | Authority / Curator | Partial reuse | bounded authority added |
| `prov:Activity` | Verification / Assertion | Reused | governance overlays |
| `cco:Artifact` | Built asset | Reused | direct reuse likely |
| `cco:InformationContentEntity` | Claim | Extended | bounded-assertion semantics |
| ISO information container | Governed information scope | Extended | governance semantics added |
| BFO role | Authority role | Extended | temporal governance added |

---

## 7. Anticipated instances

The Awen framework is multi-instance by design. Each instance is a bounded domain with its own instance architecture, conforming to this constitution. Naming the anticipated instances here is not a roadmap commitment — it is evidence that the constitution is **instance-general**, and a guard against the framework drifting into the shape of whichever instance happens to be built first.

| Instance | Status | Governance primitives exercised | Semantic substrate |
|---|---|---|---|
| **Dolgellau Town Dataset** | Active — foundation built and deployed | Claim, Evidence, Authority, Provenance, Supersession, Contradiction, Curator, Scope, Temporal validity | PROV-O (provenance) |
| **Construction governance** | Near-term opportunity | All of the above, with **Obligation** central | PROV-O, CCO, ISO 19650, IAO, BFO |
| **Third-sector organisation mapping** | Emerging | Claim, Authority, Scope, Contradiction, Temporal validity — "what organisations say they do versus how they actually work together" | PROV-O (provenance); minimal domain ontology |

The third-sector instance is a useful case precisely because it exercises the governance primitives while needing almost none of the construction-domain ontology apparatus. It is a clean test that the **governance layer is the portable foundation** and the domain ontologies are instance-specific — which is the framework's central thesis.

---

## 8. Canonical scenario methodology

The framework develops a library of canonical scenarios — small, manually curated cases that expose hidden assumptions and test governance behaviour: supersession handling, authority boundaries, contradiction persistence, evidential sufficiency. Scenarios start small and stay manually curated.

**Scenario #1 — Tŷ Newyddion (Town Dataset, 2026-05).** The first canonical scenario already exists. The Tŷ Newyddion building record exercised: multi-cardinality naming under a `name_type` qualifier (one building, several names in active use); the dual-listing case (one physical building, two Cadw register entries); a tenancy timeline across multiple occupants; the source-visibility ladder. It was hand-walked through the validation contract into the live Craidd — 4 entities, 27 claims, 0 validation errors — and stands as the worked proof that the governance primitives hold on real data.

**Candidate scenarios** (forward-looking, construction-instance-facing): fire-stopping inspection conflict; planning condition discharge; NEC compensation event; product substitution approval; Building Safety Act dutyholder transition; sensor-derived environmental alert; construction quality non-conformance; O&M documentation discrepancy.

---

## 9. Claim decomposition methodology

The framework does not treat documents as opaque files. A source is decomposed into claims, obligations, evidence, authority relationships, supersession chains, and contradiction structures.

This differs fundamentally from conventional retrieval-augmented-generation chunking. The objective is not retrieval — it is **governed semantic decomposition**. For each source: what claims are asserted; who has authority to assert them; what obligations arise; what evidence is referenced; what contradictions exist; what temporal scope applies; what supersession conditions exist; what governance boundaries apply.

This is consistent with the discipline the Building Research Agent already follows — quote-with-citation, never paraphrase; every claim cites a snapshotted source; honest `cy: null` where no Welsh evidence exists.

---

## 10. Runtime direction

The current runtime is DuckDB-based, Python-first, governance-led, append-conscious, provenance-aware, and edge-deployable. Future runtime evolution may include Parquet substrates, vector retrieval, local-LLM integration, semantic-graph overlays, and federated governance nodes.

Per §2.5, these are **implementation concerns, not constitutional foundations.** They are taken on runtime merits. The constitution does not mandate a runtime; it requires only that whatever runtime is chosen preserves the governance semantics defined here.

---

## 11. Strategic position

The Awen framework is not a BIM platform, a digital-twin platform, a universal ontology, or an optimisation engine. It is:

**A constitutional governance architecture for computable trust, operating across semantic systems.**

The central innovation is not semantic representation. It is governance over semantics — computable legitimacy, bounded authority, obligation governance, longitudinal trust, contradiction persistence, evidential sufficiency, inspectable provenance, governed supersession. This distinction guides every implementation and ontology decision.

---

## 12. Open constitutional decisions

The framework carries its own register of unresolved decisions, so that constitutional questions are tracked and settled deliberately — never drifted past. This mirrors `architecture.md`'s discipline: open questions are named, not buried.

1. **Instance-versus-constitution amendment process.** §0 states the resolution rule in principle; the concrete process for amending the constitution when an instance surfaces a genuine principle-level conflict is not yet specified.
2. **Formal BFO adoption.** §3.2 holds BFO as conceptual guidance. Whether to adopt it formally — and at which instance — is open.
3. **IAO relevance to the Town Dataset.** §3.5 marks IAO construction-instance-facing. Whether the Town Dataset's claims and source entities benefit from IAO's information-content-entity modelling is unassessed.
4. **The construction instance's ISO 19650 relationship.** Named in §7; the concrete governance-across-ISO-19650 boundary is undefined until that instance begins.
5. **Cross-reference mapping completeness.** §6 is seeded, not complete. It evolves as instances exercise the substrates.
