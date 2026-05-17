# Awen Weave — STATUS

**Last updated:** 2026-05-17 (v0.1.0 release)

## What works
- Framework code extracted via subtree split (Brief 1 complete).
- Package scaffolding in place.
- **v0.1.0 published to PyPI** — `pip install awen-weave`

## What doesn't yet
- town-dataset has not yet been slimmed; framework code still also lives there until Brief 3 lands.
- Namespace restructure (Option β proper) deferred to v0.2.

## In flight
- Brief 3 (town-dataset slim + Pi deploy) — pending.

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
