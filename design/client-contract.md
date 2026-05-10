# Town Dataset client contract — v0

**Status:** the contract between the Town Dataset Craidd and its external clients (the Dolgellau Energy Study being the first). v0 is file-backed; v1 will replace files with HTTP API calls but the function signatures clients call will not change.
**Date:** 2026-05-10
**Companion docs:** `architecture.md` (component register), `v0.1-schema.md` (data shape), `cli-design.md` (CLI design for curator review).

---

## 1. Why a contract exists

The Town Dataset is a Craidd — bounded, place-based, provenance-bound. The energy study and future clients depend on a stable view of what's a building, what its identifier is, and where to look up that information. Without a contract, every client invents its own building list and the Town Dataset's authority dissolves.

The contract is the durable thing. Implementations come and go beneath it. The energy study should call the same `Craidd` object methods whether the transport is files (today) or HTTPS-and-mTLS (when the Pi is running).

## 2. The two halves of the contract

**Reads.** Clients can request canonical reference data (currently: the UPRN lookup table that maps each Dolgellau-surveyed building to its UPRN with provenance). v1 will expose the same data via the Read API on the Pi at port 8080. The data shape doesn't change.

**Writes (proposals).** Clients can *propose* new claims for the Craidd. They cannot directly write to it. Each proposal carries a subject (or a hint to identify the subject), a predicate, a value, a source citation, a confidence band, and an optional note + evidence pointer. Proposals enter a queue; a curator reviews them; accepted proposals become canonical claims in the Craidd; rejected proposals are recorded with reason. Every action is logged in Prawf.

## 3. v0 file-backed implementation

### 3.1 Reads — canonical files in `seed/output/`

The Town Dataset's `seed/output/` directory holds the canonical reference data. Currently:

- `uprn-lookup.csv` — one row per surveyed Dolgellau building, with UPRN where resolved and a provenance trail (`match_source`, `match_confidence`, `match_score`, `matched_at`, `notes`).

As the dataset grows, more files will appear here. Clients should treat this directory as **read-only**; mutations of the canonical reference data go through proposals, not through direct file edits.

### 3.2 Writes — proposal JSON files in `proposals-out/`

Clients write proposal claims as JSON files to a `proposals-out/` directory in their own working folder (for the energy study, that's `~/Awen/handovers/dolgellau-energy-study/proposals-out/`). Each proposal is one file, named with a generated proposal ID.

Proposal JSON schema:

```json
{
  "proposal_id": "P-20260510-203015-a3f7b9c2",
  "schema_version": "v0.1",
  "submitter": "dolgellau-energy-study",
  "submitted_at": "2026-05-10T20:30:15+00:00",
  "subject": "TDS-DOL-B-NNNNNN",
  "subject_hint": {
    "uprn": 10070355430,
    "segment_id": 1,
    "property_name": "Dylanwad"
  },
  "predicate": "floor_area_m2",
  "value": 227.0,
  "source": {
    "id": "TDS-DOL-SRC-DOLGELLAU-ENERGY-STUDY",
    "title_en": "Dolgellau Energy Study, May 2026",
    "organisation": "Arloesi Dolgellau CIC"
  },
  "confidence": "medium",
  "evidence_uri": "file://handovers/dolgellau-energy-study/data/Dolgellau_buildings_demand.csv#row=12",
  "note": "Floor area from EPC match audit; fuzzy match 100.",
  "status": "pending"
}
```

Field rules:

- **subject** OR **subject_hint** must be present (typically `subject_hint` in v0 because most building entities don't exist yet in the Craidd — the curator resolves hints to entity_ids at acceptance time).
- **predicate** must be in the v0.1 starter set (see `v0.1-schema.md` §3.5).
- **value** type must match the predicate's `value_type`.
- **source** must identify a source entity by `id`, with enough metadata for the curator to verify (title, organisation, optionally url + accessed_at).
- **confidence** is `high` | `medium` | `low`. Secondary sources default to `medium`. Be honest — over-confident proposals slow down review.
- **evidence_uri** points at the raw evidence (a file in the client's working folder, an archived URL, or similar). The curator should be able to verify the claim from the URI without re-running the client.
- **status** is always `pending` at submission. Curator review changes it.

### 3.3 The client library

`client/craidd_client.py` in this repo is the canonical Python interface. Clients import it and use the `Craidd` object. v0 reads files; v1 will swap in HTTP. The energy study should depend on the interface, not on the file paths.

## 4. Integration recipe for the Dolgellau Energy Study

From an energy-study Python script, the basic shape is:

```python
import sys
sys.path.insert(0, "/Users/withaw/Awen/town-dataset")  # find the client lib
from client.craidd_client import Craidd

craidd = Craidd()

# Read: get the canonical UPRN lookup
uprn_table = craidd.uprn_lookup()
print(f"{len(uprn_table)} buildings, {uprn_table['uprn'].notna().sum()} with UPRNs")

# Read: look up a specific building by survey identity
row = craidd.find_by_survey(segment=1, property_name="Dylanwad")
print(f"UPRN: {row['uprn']}, confidence: {row['match_confidence']}")

# Write: propose a claim back to the Town Dataset
craidd.propose_claim(
    submitter="dolgellau-energy-study",
    subject_hint={"uprn": int(row["uprn"]), "segment_id": 1, "property_name": "Dylanwad"},
    predicate="floor_area_m2",
    value=227.0,
    source={
        "id": "TDS-DOL-SRC-DOLGELLAU-ENERGY-STUDY",
        "title_en": "Dolgellau Energy Study, May 2026",
        "organisation": "Arloesi Dolgellau CIC",
    },
    confidence="medium",
    note="Floor area from EPC match audit; fuzzy match 100.",
    evidence_uri="file://Users/withaw/Awen/handovers/dolgellau-energy-study/data/Dolgellau_epc_match_audit.csv#row=2",
)
```

That's the whole loop. Reads inform analyses; analyses run as before in the energy study; anything the analyses surface that the Town Dataset should know becomes a proposal.

## 5. What the curator does with the proposals

Periodically (weekly is the right rhythm for v0), the curator walks the `proposals-out/` directory, reviews each JSON file, and:

- **Accepts** — the proposal becomes a live claim in the Town Dataset's canonical store. (In v0, the curator currently does this by hand: read the proposal, decide it's correct, append it to the relevant data file with full provenance. In v1, `craidd-review` automates this.)
- **Accepts as competing** — the proposal becomes a new claim alongside any existing claim with the same `(subject, predicate)`. The contradiction stays visible; the canonical view picks the highest-confidence one.
- **Disputes** — the existing claim is marked `disputed`; the proposal becomes a new `active` claim.
- **Rejects** — the proposal is moved to `proposals-out/rejected/` with a reason in the file.

Every action is recorded in Prawf (v1) or in a curator-review log (v0). The proposal JSON itself is the audit artefact and stays preserved.

## 6. Predicates the energy study is likely to propose

Based on the energy-study data we have:

- **floor_area_m2** — from EPC matches. High volume, generally high confidence where EPC matched.
- **uprn** — already harvested for ~1,071 buildings; gaps to fill with future passes.
- **geometry** — currently postcode-centroid; the energy study has nothing better. Will improve when OS Open UPRN bulk is ingested as a separate proposal source.
- **listed_id / listed_grade** — the energy study pulled Cadw data; cross-reference matches could be proposed.
- **conservation_area** — the energy study has DataMapWales SNPA polygons; building-in-CA flag is computed.

The energy study should **not** propose energy-specific predicates (heat demand, EPC energy rating, segment heat density). Those stay in the energy study — they're downstream analyses *of* the Craidd, not facts the Craidd records about buildings.

## 7. What v1 changes

When the Read API and Write API are live on the Pi:

- `Craidd()` constructs differently — it knows the API base URL and the client's mTLS certificate.
- `craidd.uprn_lookup()` makes an HTTP GET against `/export/buildings.json`.
- `craidd.find_by_survey(...)` makes an HTTP GET against `/buildings?...`.
- `craidd.propose_claim(...)` makes an HTTP POST against `/proposals` with the proposal JSON.
- The proposal JSON shape doesn't change.
- The proposal review flow doesn't change — `craidd-review` walks the queue the same way; it's just on the Pi now.

The energy study sees none of this. Its script doesn't need to change beyond the `Craidd(...)` constructor call.

## 8. Component charter

Per `architecture.md` §5, every component has a charter. The client library:

- **Awen role:** Llys (client side).
- **Why it exists:** so external clients (energy study, future research projects, third parties) have a single stable interface to read from and propose to the Craidd.
- **What it consumes:** v0 — filesystem paths under `seed/output/` and `proposals-out/`. v1 — Read API and Write API endpoints plus mTLS certificates.
- **What it produces:** typed Python objects for reads, validated proposal JSON files (v0) or proposal POST bodies (v1) for writes.
- **Explicit non-goals:** cannot accept its own proposals; does not retry on schema errors (fail fast with a clear message); does not cache writes; does not run curator review (that's `craidd-review`); does not maintain identity state (that's the curator-identity layer).
- **What would change if removed:** every client reimplements transport and validation; the contract drifts; the energy study's eventual switch from files to API becomes a per-client migration rather than a single-library upgrade.
