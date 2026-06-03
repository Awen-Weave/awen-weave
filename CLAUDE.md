# CLAUDE — awen-weave working notes

This repo is the Awen Weave framework. Pattern + code maintained by Awen Weave Limited (in formation 2026-05-17).

## Working conventions

This repo follows the conventions in https://github.com/Huw-Lab/working-patterns:
- STATUS.md updated each session
- scripts/check.sh for discipline harness
- Foundation principles (charters, forward-additive, etc.) apply

## Relationship to other repos

- `arloesidolgellau/town-dataset` — the Dolgellau instance, consumes this framework via PyPI
- `Awen-Weave/awenweave-site` — public-facing docs at awenweave.com
- `Huw-Lab/working-patterns` — the working-pattern foundation this repo inherits

## Multi-account gh-auth

This repo lives under Huw-Lab. Code sessions touching it must `gh auth switch -u Huw-Lab` before pushing. See multi-account-gh-auth lesson in working-patterns.
