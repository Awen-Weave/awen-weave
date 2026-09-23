# Proposed schemas — NOT constitution, NOT vendored, NOT released

Schemas here are **proposals**. They are not in `awen-constitution`, not in
`src/craidd/constitution_vendor/`, and not shipped in the wheel (`design/` is
outside `[tool.hatch.build.targets.wheel] packages`). Writing into
`awen-constitution` is a **release act** and belongs to Llys alone; a schema
leaves this directory only when Llys names it.

## `prawf-batch-commitment.schema.json` — proposed `SCH-BATCH-001`

- **Rule id PROPOSED, NOT ALLOCATED.** Llys names schemas.
- **Landed by ruling:** Huw as Llys, 23/09/2026, `IDR-006-9D914F` — "validate
  both schema drafts against the live 0.1.7 grammar first, then land the
  batch-commitment structure". Carried by Dispatch 381.
- **Verbatim.** Byte-for-byte the 15/09/2026 draft from
  `~/CoworkOutbox/IDR-006 Awen/SCH-DEVICE-001-PROPOSAL-2026-09-15/`,
  sha256 `47a22329600096c1d74269f4f5dc87ce503a423c402e181b6d40aa71da98c379`.
  Its own `x-awen-status` still reads "NOT RECONCILED … v0.1.4" because this
  landing did not edit it; the reconciliation result is recorded below and
  the digest is pinned by `tests/schema/test_batch_commitment_proposal.py`,
  so any edit is a visible, deliberate act.

### Why it lands ahead of everything else

A record sealed after the fact can only be proven unchanged since sealing,
never since creation. Every reading the first sensor produces before this
structure exists is permanently second-class as evidence. Prawf records
governance events, not readings, plus periodic batch commitments over them;
readings live in time-series or object storage; claims carry only the
published assertions.

### Reconciled against the live v0.1.7 grammar (23/09/2026)

The batch schema has **no dependency on the claim grammar** — it references
no `SCH-CLAIM-001` field or enum. The claim-level gate the sensor design
relies on was measured through `validate_claim`
(`src/craidd/schema/validation.py`, origin/main `88e88f0`, vendored
constitution 0.1.7) and the served porth `constitution.validate`
(v0.1.7, commit `9112ce0`):

| Claim probe | validate_claim | porth 0.1.7 |
|---|---|---|
| `binding=measured`, `verification_method=on-site` | valid | valid |
| `binding=measured`, `verification_method=sensor-measured` | **refused** (enum) | **refused** (enum) |
| witnessing reuse: `field_session_id`+`co_signed_by`+`verified_at` | valid | valid |

So the claim delta at 0.1.7 is still **exactly one enum value**
(`verification_method` gains `sensor-measured`). That delta is **not** landed
here — it is a constitution change and rides on its own time.

### Three design points the tests hold

1. **Integrity is split** — `verification_tally` counts per-reading
   outcomes (`verified` / `unverified` / `failed`); device capability lives on
   the stamp.
2. **Every device resolves against the stamp version in force at observation
   time** — `devices[].stamp_id` and `devices[].stamp_version` are required;
   omitting the version is refused. This is the field that cannot be
   backfilled.
3. **An empty window is recordable as itself** — `observation_count: 0` with
   no witness and no trusted time validates.

### Deliberately NOT here

- `device-stamp.schema.json` (proposed `SCH-DEVICE-001`) stays in the Outbox
  proposal folder. It waits on the `geometry_basis` card (a Llys decision)
  and carries one finding from the 0.1.7 measurement: its
  `commissioning.co_signed_by` "mirrors the SCH-CLAIM-001 qualifier" but does
  not mirror the claim grammar's `co_signed_by ⇒ field_session_id`
  dependency, which both `validate_claim` and porth 0.1.7 enforce. Recorded,
  not repaired.
- The inferred class, `ADJ-SENSE-001`, `POL-SENSE-001`, the CONFORMANCE
  assurance-profile block and the first `SCH-USECASE-001` profiles.
