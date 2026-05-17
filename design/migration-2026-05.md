# Awen Weave framework migration — design

**Status:** design draft, 2026-05-17. Captures the architecture for migrating framework code from `arloesidolgellau/town-dataset` to `Huw-Lab/awen-weave`. Execution via subsequent Code briefs.

**Intended target paths in repos:**
- This document: `design/migration-2026-05.md` in `Huw-Lab/awen-weave` once the new repo exists.
- Cross-referenced in `arloesidolgellau/town-dataset/design/` so the instance's design history is intact.

---

## 1. Why this migration

The IDR-006 work has established (through licensing + brand architecture decisions 2026-05-17) that **Awen Weave is a pattern; Town Dataset is an instance applying the pattern**. The current repo layout doesn't reflect this — framework code + instance-specific code + Dolgellau content all live together in `arloesidolgellau/town-dataset`.

Migration aligns the repo structure with the brand and license architecture:

| Concept | Current repo | Post-migration repo | Owner | License |
|---|---|---|---|---|
| The framework (Awen Weave) | `arloesidolgellau/town-dataset` (mixed) | **`Huw-Lab/awen-weave`** | Huw-Lab | AGPLv3 + commercial dual |
| The instance (Dolgellau) | `arloesidolgellau/town-dataset` (mixed) | `arloesidolgellau/town-dataset` (instance-only) | arloesidolgellau (community) | OGL for content; AGPL for instance-specific code |
| The public docs | n/a | `Huw-Lab/awenweave-site` (already exists) | Huw-Lab | CC-BY-SA |
| The working patterns | n/a | `Huw-Lab/working-patterns` (already exists) | Huw-Lab | (informal; personal) |

This is the **load-bearing alignment** — code license, brand architecture, repo structure all reinforce the same boundary. Anyone reading the structure sees the pattern-vs-instance distinction immediately.

**Timing:** must complete BEFORE the public AGPL launch of Dolgellau Town Dataset. Doing it after means a public-facing repo URL changing later — bad for inbound links, search indexing, and anyone who's bookmarked or referenced the wrong URL.

---

## 2. Decisions locked 2026-05-17

| Decision | Choice |
|---|---|
| Target repo name | **`Huw-Lab/awen-weave`** — matches brand exactly; hyphenated reads cleanly in URLs |
| Git history strategy | **Subtree split with `git filter-repo`** — preserves blame and commit history for framework code |
| Instance-consumes-framework | **PyPI publication** — `awen-weave` becomes a proper installable package; town-dataset pins a version in requirements.txt |

---

## 3. Target state — what each repo holds

### 3.1 `Huw-Lab/awen-weave` (new)

The framework. Generic, reusable across instances. AGPL+commercial dual license.

```
awen-weave/
├── pyproject.toml             # PyPI packaging metadata
├── README.md                  # AGPL+commercial dual; how to install; pointer to docs
├── LICENSE                    # AGPLv3 text
├── STATUS.md                  # awen-weave's own status
├── CLAUDE.md                  # awen-weave-specific working notes
├── CONTRIBUTING.md            # CLA reference; PR conventions
├── .github/
│   ├── workflows/check.yml    # CI: pytest + scripts/check.sh
│   ├── workflows/publish.yml  # CI: publish to PyPI on tag-push
│   └── pull_request_template.md
├── src/
│   ├── craidd/                # schema, validators, predicates, storage
│   ├── cli/                   # craidd-init, craidd-propose, craidd-review, etc.
│   ├── lleolydd/              # cache, sources, bands, snapshot, CLI
│   └── awen_weave/            # package entrypoint (re-exports + version)
├── client/                    # craidd_client.py (or move under src/?)
├── tests/                     # framework tests
├── scripts/                   # check.sh + check_*.py discipline harness
├── design/                    # framework design notes (architecture, charters, etc.)
└── seed/                      # GENERIC framework seed/scaffolding (NOT Dolgellau-specific)
    └── lleolydd/              # OGL cache infrastructure (framework code expects this shape)
```

### 3.2 `arloesidolgellau/town-dataset` (existing, slimmed down)

The instance. Dolgellau-specific. Inherits framework from awen-weave package.

```
town-dataset/
├── README.md                  # Dolgellau Town Dataset; built on Awen Weave
├── LICENSE                    # OGL for content; AGPL for instance-specific code
├── STATUS.md                  # town-dataset's own status
├── CLAUDE.md                  # town-dataset-specific working notes
├── requirements.txt           # pins awen-weave==X.Y.Z from PyPI
├── .github/
│   └── workflows/check.yml    # CI specific to instance
├── src/
│   └── bra/                   # Dolgellau-tuned BRA (or split: framework-side vs instance-side)
├── config/
│   ├── agents/                # Dolgellau-specific agent manifests
│   └── lleolydd/area-bounds.geojson   # Dolgellau-specific Gwynedd polygon
├── tests/                     # instance-specific tests
├── scripts/
│   ├── check.sh               # delegates most checks to awen-weave version; adds instance-specific
│   ├── sync-to-pi.sh          # Dolgellau Pi-specific deployment
│   └── check_*.py             # instance-specific discipline checks if any
├── design/                    # Dolgellau-specific design notes (energy study integration, etc.)
└── seed/                      # Dolgellau content + sources
    ├── buildings/             # Dolgellau-specific seed buildings
    ├── output/                # Dolgellau-specific cached outputs
    └── pricepaid/             # Dolgellau HMLR Price Paid data
```

### 3.3 Operational state (stays on Pi, not in either repo)

```
/srv/town-dataset/  (on the Pi)
├── craidd.duckdb              # canonical data store
├── prawf.duckdb               # Prawf log
├── proposals/                 # operational queue
├── seed/lleolydd/cache.duckdb # Lleolydd OGL cache
└── seed/lleolydd/snapshots/   # OGL release snapshots (large)
```

---

## 4. What specifically moves vs stays — the categorisation

### 4.1 Clear "move to awen-weave"

| Current path | Reason |
|---|---|
| `src/craidd/` (schema, validators, predicates, storage, ddl) | Pure framework. Schema is the load-bearing framework primitive. |
| `src/cli/craidd_*.py` (craidd-init, craidd-propose, craidd-review when built, craidd-fetch when built, craidd-export when built, craidd-status when built) | All framework CLIs. Tier 1 contractors using awen-weave will use these. |
| `client/craidd_client.py` | Framework client library; consumed by any instance. |
| `src/lleolydd/cache/` (build, bands, snapshot, sources/*) | Lleolydd-as-framework. Any place-based instance might use this. |
| `src/cli/lleolydd_cache.py` | Framework CLI for OGL cache management. |
| `tests/schema/`, `tests/cli/`, `tests/lleolydd/` | All framework tests. |
| `scripts/check.sh`, `scripts/check_crossrefs.py`, `scripts/check_charters.py`, `scripts/check_register_count.py`, `scripts/check_status.py` | Framework discipline harness. |
| `design/architecture.md` (with §6 register), `design/constitutional-framework.md`, `design/v0.1-schema.md` (and successor v0.2/v0.3), `design/cli-design.md`, `design/roadmap.md`, `design/entity-proposal-shape.md` | Framework design notes. |
| `design/lleolydd.md` (framework parts of Lleolydd) | Lleolydd-as-framework design. |
| `design/bra-proposal-handoff.md`, `design/bra-v2-estate-agents.md`, `design/bra-v2-estate-agents-pilot.md`, `design/building-research-agent.md` (framework parts) | BRA-as-framework design. |

### 4.2 Clear "stay in town-dataset"

| Current path | Reason |
|---|---|
| `seed/buildings/` (Tŷ Newyddion, etc.) | Dolgellau-specific entities. |
| `seed/output/` (Dolgellau cached lookups) | Dolgellau operational data. |
| `seed/pricepaid/`, `seed/ocod/`, `seed/agents/` (Dolgellau-tuned agent manifests + audit CSVs) | Dolgellau-specific sources + audit trail. |
| `seed/lleolydd/area-bounds.geojson`, `seed/lleolydd/snapshots/` | Dolgellau-specific clipped bounds + cached releases. |
| `config/agents/walter-lloyd-jones-co.yaml` (and any other Dolgellau-specific agent manifests) | Dolgellau-instance configuration. |
| `design/pilot-ty-newyddion.md`, `design/ty-newyddion-review-2026-05-10.json`, `design/reviews/*` | Dolgellau-specific curator reviews. |
| `design/sources-backlog.md` | Dolgellau-specific sources catalogue. |
| `handovers/dolgellau-energy-study/` (if still present) | Dolgellau-specific energy study handover. |
| `proposals-out/P-20260511-batch-001/` | Dolgellau DEC-correction proposals batch. |
| `scripts/sync-to-pi.sh` | Pi-specific to Arloesi Dolgellau. |
| `scripts/filter-*.py` for HMLR / OCOD / EPC | Some are Dolgellau-tuned (LL40 filtering); some are generic (the filter logic). Probably both move with the generic logic refactored into awen-weave and the Dolgellau-specific runner staying in town-dataset. |

### 4.3 Genuine grey areas — careful thought required

**BRA (Building Research Agent).** The agent shell + Nimble integration + proposal-writing loop is framework. The specific allowlist (WLJ + RG Jones + Savills) and per-agent manifests are instance config. Split: `src/bra/` (framework shell + Nimble integration + generic claim drafting) moves to awen-weave; `config/agents/` (per-agent manifests) stays in town-dataset.

**Energy study client + DEC-correction proposals.** The client-contract pattern (`design/client-contract.md`) is framework. The energy-study-specific implementation that wrote 11 DEC-correction proposals is instance work. Probably client-contract.md moves; the energy-study-specific scripts (if any are in-repo) stay.

**README.md.** Both repos need their own. awen-weave's: "the framework for weaving together knowledge / place / data / human insight... pip install awen-weave; for instances see..."; town-dataset's: "Dolgellau Town Dataset, built on Awen Weave... pip install -r requirements.txt; runs against awen-weave==X.Y.Z..."

**CLAUDE.md / STATUS.md.** Both repos need their own. awen-weave inherits the working-patterns conventions; town-dataset references both working-patterns and awen-weave (because it depends on both).

---

## 5. Migration mechanics

### 5.1 Phase 1 — Subtree split (preserves history)

Use `git filter-repo` to extract framework files into a new repo with history preserved.

```bash
# Starting point: clean clone of arloesidolgellau/town-dataset
git clone https://github.com/arloesidolgellau/town-dataset.git awen-weave-extraction
cd awen-weave-extraction

# Extract: keep only the framework paths, with their full history
git filter-repo \
    --path src/craidd/ \
    --path src/cli/craidd_init.py \
    --path src/cli/craidd_propose.py \
    --path src/cli/lleolydd_cache.py \
    --path src/lleolydd/ \
    --path client/ \
    --path tests/schema/ \
    --path tests/cli/ \
    --path tests/lleolydd/ \
    --path scripts/check.sh \
    --path scripts/check_crossrefs.py \
    --path scripts/check_charters.py \
    --path scripts/check_register_count.py \
    --path scripts/check_status.py \
    --path scripts/check_stale_briefs.py \
    --path design/architecture.md \
    --path design/constitutional-framework.md \
    --path design/v0.1-schema.md \
    --path design/cli-design.md \
    --path design/roadmap.md \
    --path design/entity-proposal-shape.md \
    --path design/lleolydd.md \
    --path design/building-research-agent.md \
    --path design/bra-v2-estate-agents.md \
    --path design/bra-v2-estate-agents-pilot.md \
    --path design/bra-proposal-handoff.md \
    --path design/client-contract.md \
    --path design/craidd-foundation-handover.md \
    --path design/craidd-propose-spec.md
    # ... add any other framework paths

# (Specific paths to extract are codified during execution after a final
# audit pass against the live repo; this list is the working draft.)
```

After extraction, push the cleaned history to `Huw-Lab/awen-weave`:

```bash
cd ../awen-weave-extraction
git remote remove origin
git remote add origin https://github.com/Huw-Lab/awen-weave.git
git push -u origin main
```

### 5.2 Phase 2 — Slim town-dataset

In a *separate* clone (so the original isn't damaged), remove the framework paths:

```bash
git clone https://github.com/arloesidolgellau/town-dataset.git town-dataset-slim
cd town-dataset-slim

git filter-repo \
    --invert-paths \
    --path src/craidd/ \
    --path src/cli/craidd_init.py \
    # ... (same list as above)
```

Then:
- Add `requirements.txt` pinning `awen-weave==0.1.0` from PyPI (once published).
- Update existing imports from `from craidd.schema import ...` to `from awen_weave.craidd.schema import ...` (or however the public package surface is shaped — see §6).
- Update tests to use the installed package.
- Push as a force-push to a migration branch first; review; merge to main when validated.

### 5.3 Phase 3 — PyPI packaging

Add `pyproject.toml` to awen-weave:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "awen-weave"
version = "0.1.0"
description = "Awen Weave — a pattern for weaving together knowledge, relationships, place, data and human insight into coherent living systems."
readme = "README.md"
license = { text = "AGPL-3.0-or-later" }
authors = [{ name = "Huw Thomas", email = "ihuw@me.com" }]
requires-python = ">=3.10"
dependencies = [
    "duckdb>=0.10",
    "pandas>=2.0",
    "pyyaml>=6.0",
    "shapely>=2.1",
    "pyogrio>=0.12",
    "requests>=2.30",
]
keywords = ["AI governance", "civic data", "place-based knowledge", "provenance"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
    "Programming Language :: Python :: 3",
    "Topic :: Scientific/Engineering :: GIS",
]

[project.urls]
Homepage = "https://awenweave.com"
Repository = "https://github.com/Huw-Lab/awen-weave"
Documentation = "https://awenweave.com"

[project.scripts]
craidd-init = "cli.craidd_init:main"
craidd-propose = "cli.craidd_propose:main"
lleolydd-cache = "cli.lleolydd_cache:main"
# ... etc

[tool.hatch.build.targets.wheel]
packages = ["src/craidd", "src/cli", "src/lleolydd", "client"]
```

### 5.4 Phase 4 — PyPI publishing setup

- Create PyPI account for Huw-Lab (or use Huw's existing).
- Configure GitHub Actions Trusted Publisher (no API tokens needed; OIDC-based).
- Add `.github/workflows/publish.yml` that triggers on tag push (`v*`) and publishes to PyPI.
- First release: tag `v0.1.0`, push, watch publish go green, confirm package live at https://pypi.org/project/awen-weave/.

### 5.5 Phase 5 — Pi reconfiguration

The Pi currently has `arloesidolgellau/town-dataset` as a git checkout at `/srv/town-dataset/`. Post-migration:
- Pi keeps `town-dataset` as git checkout (still gets the instance code + content via `git pull`).
- Pi gets `awen-weave` from PyPI in its venv: `pip install awen-weave==0.1.0`.
- Update venv setup; rerun `craidd-init` if predicate registry changed (it shouldn't have for this migration — pure structural change).
- Verify all CLIs still work; smoke tests still pass.

---

## 6. Cross-repo dependency: import path strategy

Decision needed during execution: what does the public package surface look like?

Option α — flat re-exports at `awen_weave` namespace:
```python
from awen_weave import Craidd, validate_claim, PredicateDef
from awen_weave.cli import craidd_init, craidd_propose
```

Option β — preserve current paths under `awen_weave`:
```python
from awen_weave.craidd.schema import Predicate, validate_claim
from awen_weave.craidd.storage import connect_craidd
from awen_weave.cli.craidd_init import main
```

Option β preserves existing import patterns (just adds `awen_weave.` prefix); migration is mechanical search-and-replace in town-dataset. Option α gives cleaner public API but requires designing the surface deliberately.

**Recommendation: Option β for v1, refactor toward α later.** Migration becomes much simpler; the eventual cleaner-API decision is a v0.2 packaging concern.

---

## 7. Sequencing

Phases run sequentially; each Code session has clear boundaries.

```
Phase 1: Cowork drafts this design + Code briefs (this session + maybe one follow-up)
Phase 2: Code performs subtree split → awen-weave repo with extracted history
         (~2 hours Code session)
Phase 3: Code adds pyproject.toml + PyPI publishing workflow
         (~30 min Code session)
Phase 4: Huw creates PyPI account + configures Trusted Publisher
         Code tags v0.1.0; first PyPI publish
         (~30 min Code session + Huw's ~15 min PyPI setup)
Phase 5: Code slims town-dataset (--invert-paths filter) → migration branch
         Updates imports, requirements.txt, tests
         (~2 hours Code session)
Phase 6: Validation — full test suite green; CIs green; Pi smoke tests
         (~30 min Code session)
Phase 7: Merge town-dataset migration branch to main
         Pi deploy of updated town-dataset + awen-weave install
         (~30 min Code + Huw at Pi terminal)
```

Total: ~5-6 Code sessions across the week. Substantial but well-scoped.

**Sequencing constraint:** the migration should complete BEFORE the public AGPL launch of Dolgellau Town Dataset. Public launch is currently informal (awenweave.com site is live; Dolgellau repo isn't yet public). The window between now and "go public" is the right window for this migration.

---

## 8. Risk management

**Risk 1 — Broken imports in town-dataset post-migration.** Mitigation: validate phase (Phase 6) before merging the migration branch; full test suite must pass; CI green. If imports break, fix on the branch; don't merge until clean.

**Risk 2 — Git history confusion.** Two repos now share ancestry (both descended from arloesidolgellau/town-dataset's history). Mitigation: design note (this document) explains the relationship; commit messages in awen-weave's first restructure-commit explain "extracted from arloesidolgellau/town-dataset via subtree split 2026-05-XX."

**Risk 3 — PyPI publishing setup hiccups.** Mitigation: Trusted Publisher is well-documented; if it fails, fall back to API-token-based publishing as a v1 workaround.

**Risk 4 — Pi deployment regression.** Mitigation: keep rsync-state-backup like 2026-05-16 Pi deploy did; pre-deploy snapshot of `/srv/town-dataset/`.

**Risk 5 — Inbound link rot.** Mitigation: keep the original arloesidolgellau/town-dataset repo at the same URL; just slim its contents. People who linked to specific files (e.g., a design note that moved to awen-weave) hit 404 — manageable cost, GitHub redirects file-renames within a single repo, but cross-repo moves break links. Worth noting publicly when migration lands.

**Risk 6 — Pre-migration PR conflict.** Mitigation: pause new PRs in town-dataset during the migration execution window (Phases 2-7). Run during a quiet operational window.

---

## 9. What this enables

- **Brand-license-repo alignment** — three independently-coherent structures all pointing the same way.
- **Awen Weave as installable framework** — `pip install awen-weave` becomes the standard way for any new instance to use the pattern.
- **Commercial licensee onboarding** — Richard / Evan / future customers receive a clean `pip install` + commercial license rather than "fork this big mixed repo."
- **Future instance creation** — third-sector / construction / additional civic-data instances bootstrap from `pip install awen-weave` + their own instance repo + their own content.
- **Cleaner contributor experience** — framework contributors work in `awen-weave`; instance contributors work in `town-dataset`. Clear separation of concerns.

---

## 10. What this does NOT include (parked for follow-up)

- **Public API redesign (Option α flat re-exports).** Migrate Option β first; refactor later.
- **PyPI organization vs personal account.** Use Huw's personal PyPI account for v0.1.0; transfer to an org account if commercially indicated later.
- **Semantic versioning policy.** v0.x for now; bump to v1.0.0 when the framework's API stabilises enough for commercial-customer dependency contracts.
- **Documentation for awen-weave on PyPI / readthedocs.** awenweave.com is the docs surface; pyproject.toml's URL fields point at it.
- **Decisions about which Huw-Lab/working-patterns content moves to awen-weave's design folder.** Some working-patterns content (charter discipline, forward-additive) is genuinely framework-shaped; some is project-management (STATUS.md conventions). Keep all in working-patterns for now; revisit if anything specifically needs to be in awen-weave's design.

---

## 11. Code briefs that follow this design

Three Code briefs needed to execute. Each is its own ~2-hour Code session.

1. **`cowork-to-code-awen-weave-subtree-split.md`** (Phases 2-3) — create Huw-Lab/awen-weave repo; subtree-split extraction; pyproject.toml + publishing workflow.
2. **`cowork-to-code-awen-weave-first-pypi-release.md`** (Phase 4) — Huw configures PyPI Trusted Publisher; Code tags v0.1.0; first publish.
3. **`cowork-to-code-town-dataset-slim-and-rewire.md`** (Phases 5-6-7) — slim town-dataset; update imports + requirements; full validation; Pi deploy.

To draft after this design is reviewed and approved. Probably one Cowork session per brief, sequential.

---

## 12. Open questions parked for execution

a. **Final extraction path list.** §5.1's list is the working draft; Code does a careful audit against the live repo state at execution time and adjusts.

b. **Exact public API for Option β imports.** Decide whether to expose `awen_weave.craidd.schema.Predicate` vs `awen_weave.schema.Predicate` (i.e., flatten the `craidd.` layer) during Phase 2.

c. **Whether to keep `client/` at top level or move under `src/`.** Existing layout has `client/` outside `src/`; for PyPI packaging, may be cleaner to move it under `src/awen_weave/client/`. Decide at packaging time.

d. **Welsh tutor pass timing relative to migration.** Welsh predicate translations land in awen-weave/src/craidd/schema/predicates.py. If tutor session (Tuesday 2026-05-19) happens before migration completes, the predicate updates land in town-dataset and need re-applying in awen-weave; if after, they land cleanly in the new repo. Probably target migration completion before tutor pass merges, OR sequence tutor pass to land in awen-weave directly.
