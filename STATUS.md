# Awen Weave — STATUS

**Last updated:** 2026-05-22 (v0.1.1 released — description_cy backfill live on PyPI; town-dataset pin bump in flight)

## What works
- Framework extracted (Brief 1 ✓)
- **v0.1.0 published to PyPI** ✓ — `pip install awen-weave`
- **v0.1.1 published to PyPI** ✓ — `pip install awen-weave==0.1.1`; clean-venv smoke test on the Dolgellau Pi (Python 3.13.5) confirms `address.description_cy == 'cyfeiriad post'` and zero remaining `CY_PENDING` across all 60 predicates
- CI check workflow green ✓
- **First downstream consumer (Dolgellau Town Dataset) now running on v0.1.0** ✓ — Pi at Arloesi Dolgellau pulled the migrated repo, installed awen-weave==0.1.0, framework imports resolve from site-packages, all 3 entry-point scripts work, operational data (51 claims / 12 entities / 60 predicates) intact through the migration. (Pi is one upgrade behind v0.1.1 — picks up the Welsh on its next `pip install --upgrade`.)

## What doesn't yet
- Namespace restructure (Option β proper) deferred to v0.2.
- BRA refactor + extraction (Brief 4) — `src/bra/` stays in town-dataset until instance-specific constants are lifted into config.

## Next
- v0.2 work — design questions parked: namespace restructure, BRA refactor + extraction.
- Brief 16 (Welsh place-names) — framework-module ingestion that targets this repo (not town-dataset) per the 2026-05-22 routing decision.

## Recent releases

- **2026-05-22 — v0.1.1** — `description_cy` backfill (additive bilingual data; no API change). All 60 predicates now carry tutor-attested Welsh from Catrin Stephens' 2026-05-19 magic-link session. PyPI: <https://pypi.org/project/awen-weave/0.1.1/>. Tag: `v0.1.1`. Workflow run: 26294896889 (success). _(cowork-to-code-awen-weave-0.1.1-cy-republish.md)_

## Deferred from initial migration

- `src/bra/` (Building Research Agent) code stays in
  arloesidolgellau/town-dataset for now. Design notes for BRA ship
  in this repo (`design/bra-*`), but the implementation requires a
  refactor to lift instance-specific constants into config before
  extraction is clean. Deferred to a follow-up brief (Brief 4)
  after the v0.1 migration arc completes.

## Routing
- Cowork: ~/CoworkOutbox/IDR-006 Awen/
- Working patterns: github.com/Huw-Lab/working-patterns
