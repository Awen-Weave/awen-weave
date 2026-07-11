# Snapshots — the committed federation delivery path

Delivery is **committed-to-repo** (resolved 2026-07-11): `craidd-snapshot` emits
a stamped, constitution-validated snapshot straight into this tracked path, and
it is pushed as `huw-awenweave`. CHI's build pulls the checkout and points
`pull_tref.py --snapshot <dir>` at the snapshot directory — no fetch endpoint
needed for the first proof (a static craidd endpoint is the later transport-hop
option).

```
snapshots/
  dolgellau-gazetteer/
    snapshot-<iso>Z/
      manifest.json        # pins the live constitution version + source_ran_at + counts
      place-anchors.json   # SCH-PLACEANCHOR-001
      claims.json          # SCH-CLAIM-001 (federated name_* carry the binding gate)
      stamps.json          # SCH-FEDERATION-001 (notes declare the ran_at_utc basis)
```

## Regenerate on craidd (where the source + porth are reachable)

```
git pull && pip install -e .
craidd-snapshot dolgellau-gazetteer      # --out defaults here: snapshots/dolgellau-gazetteer/
git add snapshots/ && git commit && git push   # as huw-awenweave
```

`craidd-snapshot` validates every record against the **live** porth
`constitution.validate` gate before writing (fail-loud, no partial snapshot) and
pins the live constitution version in the manifest. `--out` defaults to this
committed path, computed from the running checkout — so a live re-emit lands
here, ready to commit, with nothing to copy in.

## `dolgellau-gazetteer/snapshot-20260711T000000Z/`

The first concrete artefact (brief §6), built from **real** Town Dataset data on
craidd and validated against live porth (constitution 0.1.2): 3 place-anchors
(one per building with a resolved UPRN; `county_gss` = Gwynedd `W06000002`;
ward/community/lsoa null until Lleolydd coverage), 4 federated `name_*` claims,
1 gazetteer stamp (`notes: ran_at_utc basis: git-head-commit`). Built with a
fixed `--built-utc` so it is deterministic and `git diff`-meaningful. This is the
snapshot CHI proves the S2 loop against.
