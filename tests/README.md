# tests/ — Town Dataset test suite

Pinned smoke tests for the schema layer (`src/craidd/schema/`) and the CLIs
(`src/cli/`). The suite is deliberately small at v1 — happy path plus the
obvious error paths — because the schema-layer functions are pure and easy to
exercise, and adding tests piecemeal as new work lands is the cheaper habit
to build than retrofitting a comprehensive suite after the fact.

## How to run

From the repo root:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

`pytest.ini` sets `pythonpath = src client` so `from craidd.schema import ...`
resolves without installation.

## Layout

```
tests/
  schema/    — pure-function tests for the validation contract
  cli/       — subprocess-shaped smoke tests for the curator CLIs
```

The layout mirrors `src/` one-to-one. New schema work (e.g. v0.1-schema.md §10
item 7 — Lleolydd-driven predicates and qualifiers) adds new files in
`tests/schema/`, named for the function under test.

## Discipline checks vs unit tests

`pytest` covers the *behaviour* contracts: validators reject what the schema
says they should, CLIs produce the files they say they produce.

`scripts/check.sh` covers the *documentation* contracts: charters are
complete, cross-references resolve, the component count in `architecture.md`
§3 matches the register table.

Both run in CI (`.github/workflows/check.yml`). A PR that drifts on either
fails the check and is not merged until the drift is corrected — see
`CONTRIBUTING.md` "Discipline checks" section.

## What's not here yet

- Tests for `client/craidd_client.py` (file-backed reads). Added when that
  surface gains its first non-trivial logic.
- Tests for `src/bra/` (Building Research Agent). Some of its surface is
  network-dependent; deferred until a stable seam is identified.
- Property-based or mutation testing. Deferred — the schema layer's pure
  functions would benefit but the cost-benefit isn't there yet.
