# `craidd-propose` — detailed spec

**Status:** detailed specification for the `craidd-propose` CLI. Built 2026-05-15; this document is the design of record. Promotes the short charter in `cli-design.md` §4.2 to a full spec, in the pattern of `cli-design.md` §2 (`craidd-fetch`) and §3 (`craidd-review`).
**Date:** 2026-05-15
**Companion docs:** `cli-design.md` (the CLI family and build order), `architecture.md` §3 (the component register row), `v0.1-schema.md` §3 (the data model the validation enforces), `client-contract.md` (the proposal format `craidd_client.py` shares).

---

## 1. Charter

**Awen role.** Llys. A curator action that adds to the proposal queue; not a Craidd component itself.

**Why it exists.** The curator, and client code such as the energy study, need a single validated way to put a candidate claim into the queue. Hand-writing proposal JSON is error-prone and skips the schema check that should happen at submit time, not review time.

**What it consumes.** A candidate claim, from one of three input modes: a JSON or YAML file, command-line flags, or interactive prompts. A submitter identity.

**What it produces.** A schema-conformant proposal JSON file under `<data-dir>/proposals/`, in the same format `client/craidd_client.py` emits — so `craidd-review` reads one format regardless of origin.

**What it explicitly does not do.** It does not accept, review, or fetch. It does not touch the canonical database — proposals are files until `craidd-review` reads them. It does not resolve a `subject_hint` to an entity. It does not — yet — write a Prawf entry (see §3, note on Prawf).

**What would change if removed.** Proposals could only be made by hand-writing JSON or by client code calling the library directly; the curator would have no validated manual entry point, and the schema-validation-at-submit guarantee would be lost.

## 2. Command shape

```
craidd-propose --from-file <path>                    # JSON or YAML proposal
craidd-propose --subject <id> | --subject-hint <k=v>...
               --predicate <name>
               --value <v> | --value-cy <t> --value-en <t>
               --source-id <id> --confidence <high|medium|low>
               [--qualifier <k=v>]... [--note <text>] [--evidence-uri <uri>]
craidd-propose                                       # interactive — prompts

Options (all modes):
  --submitter <id>     who is submitting (default: the --actor value)
  --actor <name>       curator/client identity (default: "craidd-propose")
  --data-dir <path>    proposals written to <path>/proposals/
                       (default: /srv/town-dataset)
  --dry-run            assemble and validate; write nothing
  --json               machine-readable output
```

Mode is chosen by what is given: `--from-file` selects file mode; otherwise `--predicate` selects flag mode; otherwise the tool prompts interactively. Bilingual values come from `--value-cy` / `--value-en` in flag mode, or paired prompts interactively. In flag mode the value is coerced to the predicate's `value_type` (an integer predicate given a non-numeric `--value` fails as an input error); file and interactive modes carry whatever type the source supplies, and `validate_proposal` checks it.

## 3. Behaviour, step by step

1. **Assemble.** Build a proposal dict from the chosen input mode. A `--from-file` proposal may already carry `submitter`, `submitted_at`, or `proposal_id`; these are restamped in step 2 so every queued proposal is consistent.
2. **Finalise.** Stamp the proposal with a fresh `proposal_id` (`P-<YYYYMMDD-HHMMSS>-<uuid8>`), the current `schema_version`, the resolved `submitter`, an ISO `submitted_at`, an empty-or-supplied `qualifiers` mapping, and `status: "pending"`. Key order matches `craidd_client.py` output, with `qualifiers` as the one additional key.
3. **Validate.** Run `craidd.schema.validate_proposal`. Any errors stop the run — exit 1, nothing written.
4. **Dry run.** With `--dry-run`, print the validated proposal and stop — exit 0, nothing written.
5. **Write.** Create `<data-dir>/proposals/` if absent and write `<proposal_id>.json`. Print a one-screen summary — exit 0.

**Note on Prawf.** The `architecture.md` §3 register row for `craidd-propose` reads "Proposal file in `proposals/` + Prawf entry." The Prawf logger (`architecture.md` §6.11) is not built. `craidd-propose` therefore makes the same honest deferral `craidd-init` made for its genesis entry: the proposal file records `submitter` and `submitted_at` inside itself, and the Prawf entry is deferred until the Prawf logger ships. This is a known deferral recorded here and in the CLI's docstring, not a silent gap. The register row stands as a statement of charter, not of current build state (`architecture.md` §8).

## 4. Validation scope

`craidd-propose` validates through `craidd.schema.validate_proposal`, a pure function in the schema layer (so validation logic stays where `architecture.md` §4 boundary 4 requires it). A proposal is the looser pre-claim shape — a single untyped `value`, and a subject that may be a `subject_hint` rather than a resolved entity — so `validate_claim` cannot run on it directly. `validate_proposal` checks the subset of the claim contract decidable **without the database**:

- the predicate exists in the registry and is not deprecated;
- the `value`'s Python type is consistent with the predicate's `value_type` (`bool` is not accepted as `int`; an `int` is accepted where a `real` is expected; bilingual values must be a mapping with at least one of `cy` / `en` set);
- required qualifiers are present, and every supplied qualifier is a known key with an in-domain value for closed-domain qualifiers;
- `confidence` is `high`, `medium`, or `low`;
- `source` is a mapping carrying a non-empty `id`;
- the subject is identified — either a `subject` entity_id or a non-empty `subject_hint` mapping;
- a `submitter` is present.

What it deliberately does **not** check, because these need the live store and belong to `craidd-review`: resolving a `subject_hint` to a real entity; the predicate's `applies_to` against that entity's type; and single-cardinality conflicts with existing active claims. A clean `validate_proposal` result means a proposal is well formed enough to enter the queue — it is never a guarantee of acceptance.

## 5. Errors and edge cases

- **Input cannot be assembled** — a `--from-file` path that is missing or unparseable, a YAML file when PyYAML is not installed, a malformed `K=V` flag, a non-numeric value for a numeric predicate in flag mode: exit 2, nothing written, the cause named.
- **Proposal fails validation** — any error from `validate_proposal`: exit 1, every error listed, nothing written.
- **Proposals directory not writable** — exit 2, the path and OS error named.
- **Interactive abort** — Ctrl-C during prompts exits 2 cleanly.
- **YAML support is optional** — PyYAML is imported lazily, only when a `.yaml`/`.yml` file is given; JSON-only use needs nothing beyond the standard library. PyYAML is listed in `requirements.txt`.

Exit codes mirror `craidd-init`'s spirit: `0` success or clean dry-run, `1` a clean refusal (the proposal is malformed), `2` an error (the input could not be assembled, or the environment is not writable).

## 6. Identity and authorisation

In v0 there is no Write API and no curator-identity layer, so `craidd-propose` cannot authenticate a submitter — it records the `--submitter` / `--actor` value as an honest claim of identity inside the proposal file. When the Write API and curator-identity layer (`architecture.md` §6.6, §6.10) are built, `craidd-propose` becomes a thin client that authenticates with the submitter's credential and the recorded `submitter` becomes a verified fact rather than a self-declaration. Submitting a proposal is open to both curators and contributors by design; the two-tier distinction bites at `craidd-review`, not here — anyone may propose, only a second curator may accept.

## 7. Open question

**Where the queue lives, and how the energy study's proposals reach it.** `craidd-propose` writes to `<data-dir>/proposals/`, which is what `craidd-review` is specified to read (`cli-design.md` §3.1). The energy study, using `craidd_client.py` directly, writes to its own `proposals-out/` inside its handover folder — that is the *client's* staging area, deliberately outside this repo. Reconciling the two — does the curator copy staged proposals into the Pi's `proposals/`, or does `craidd-review` learn to read more than one location? — is a `craidd-review` design question, parked here so it is not forgotten when that tool is next on deck.
