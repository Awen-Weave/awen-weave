# Federation spine — sample artefacts (S1)

The async request-queue contract example. (The committed gazetteer **snapshot**
moved to the delivery path [`snapshots/dolgellau-gazetteer/`](../snapshots/) when
delivery was resolved as committed-to-repo — see `snapshots/README.md`.)

## `requests/`

The async request-queue directory contract (brief §5, Deliverable C). Deliberately
just directories and JSON so the shape survives every transport hop; live assembly
(inbox → claimed → done) is S6, but the contract and the §6 request schema exist
now so nothing changes later.

- `inbox/req-20260711-0001-chi-dolgellau.json` — an example CHI request for the
  Dolgellau gazetteer, matching the §6 schema
  (`{place, nation, wanted_layers[], requested_by, reason, emitted_at}`).
- `claimed/`, `done/` — the other two stages (empty; `.gitkeep`-held).
