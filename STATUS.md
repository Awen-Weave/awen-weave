# Awen Weave — STATUS

**Last updated:** 2026-05-17 (post v0.1.0 release)

## What works
- Framework extracted (Brief 1 ✓)
- **v0.1.0 published to PyPI** ✓ — `pip install awen-weave`
- Smoke install + import verified ✓
- CI check workflow green ✓

## What doesn't yet
- town-dataset still has framework code duplicated (Brief 3 will slim it)
- Namespace restructure deferred to v0.2

## Next
- Brief 3: town-dataset slim + rewire to consume awen-weave from PyPI + Pi deploy.

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
