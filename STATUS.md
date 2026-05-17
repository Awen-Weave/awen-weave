# Awen Weave — STATUS

**Last updated:** 2026-05-17 (Brief 3 complete; town-dataset successfully consuming)

## What works
- Framework extracted (Brief 1 ✓)
- **v0.1.0 published to PyPI** ✓ — `pip install awen-weave`
- CI check workflow green ✓
- **First downstream consumer (Dolgellau Town Dataset) now running on v0.1.0** ✓ — Pi at Arloesi Dolgellau pulled the migrated repo, installed awen-weave==0.1.0, framework imports resolve from site-packages, all 3 entry-point scripts work, operational data (51 claims / 12 entities / 60 predicates) intact through the migration.

## What doesn't yet
- Namespace restructure (Option β proper) deferred to v0.2.
- BRA refactor + extraction (Brief 4) — `src/bra/` stays in town-dataset until instance-specific constants are lifted into config.

## Next
- v0.2 work — design questions parked: namespace restructure, BRA refactor + extraction.
- Welsh tutor session (week of 2026-05-19) — predicate translations target this repo directly per the 2026-05-17 decision (`src/craidd/schema/predicates.py`).

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
