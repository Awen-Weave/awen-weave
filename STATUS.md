# Awen Weave — STATUS

**Last updated:** 2026-05-17 (initial extraction from arloesidolgellau/town-dataset)

## What works
- Framework code extracted via subtree split with full git history preserved.
- Package scaffolding in place (pyproject.toml, LICENSE, README).

## What doesn't yet
- Not yet published to PyPI (Brief 2 ships the first publish).
- town-dataset has not yet been slimmed; framework code still also lives there until Brief 3.

## In flight
- PyPI Trusted Publisher setup (Huw, pre-Brief 2).
- v0.1.0 tag + publish (Brief 2).

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
