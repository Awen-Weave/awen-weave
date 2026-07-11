# Federation spine — sample artefacts (S1)

A committed, diffable provenance backstop for the S1 federation spine
(`substrate-build-stages` S1). Real records from the real Dolgellau Town Dataset,
validated against the **live** `constitution.validate` gate on awen-porth
(constitution 0.1.2, tag v0.1.2) at build time. Regenerate on craidd with:

```
craidd-snapshot dolgellau-gazetteer \
  --source-root /srv/town-dataset \
  --duckdb /srv/town-dataset/craidd.duckdb \
  --out /srv/town-dataset/snapshots
```

(Locally: `python -m cli.craidd_snapshot dolgellau-gazetteer --offline …` uses the
vendored offline gate instead of porth.)

## `dolgellau-gazetteer/snapshot-20260711T000000Z/`

The first concrete output of the spine (brief §6) — the artefact CHI's
`pull_tref.py` consumes in S2:

| file | shape | contents |
|---|---|---|
| `manifest.json` | brief §5 | pins the live constitution version read from porth (0.1.2), `source_ran_at` carried verbatim from the source, counts |
| `place-anchors.json` | SCH-PLACEANCHOR-001 | 3 anchors — one per building with a resolvable UPRN (`county_gss` = Gwynedd `W06000002`; ward/community/lsoa null until Lleolydd coverage resolves them) |
| `claims.json` | SCH-CLAIM-001 | 4 federated `name_*` claims, each carrying the claim-level gate `binding=federated` + `federated_from` + `source_ran_at` |
| `stamps.json` | SCH-FEDERATION-001 | the one gazetteer provenance stamp (`ran_at_utc` ≠ `federated_utc`); `notes` declares the run-time basis — here `ran_at_utc basis: git-head-commit` (a proxy until the Town Dataset emits its own `run-manifest.json`) |

Built with `--built-utc 2026-07-11T00:00:00+00:00` so the sample is deterministic
and `git diff`-meaningful. The build fixes `built_utc`; the source `ran_at_utc` is
read from the Town Dataset's own git HEAD (verify-not-recall), never manufactured.

## `requests/`

The async request-queue directory contract (brief §5, Deliverable C). The shape
survives every transport hop; live assembly (inbox → claimed → done) is S6, but
the contract and the §6 request schema exist now so nothing changes later.

- `inbox/req-20260711-0001-chi-dolgellau.json` — an example CHI request for the
  Dolgellau gazetteer, matching the §6 schema
  (`{place, nation, wanted_layers[], requested_by, reason, emitted_at}`).
- `claimed/`, `done/` — the other two stages (empty; `.gitkeep`-held).
