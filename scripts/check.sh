#!/usr/bin/env bash
# scripts/check.sh — discipline-check harness (cli-design.md, architecture.md
# §7 fitness checks, test-infrastructure brief §1.3).
#
# Wraps the manual audits Code has been running by hand since Phase 0:
#   1. Cross-ref resolution — every §N.M in design/ resolves to a real
#      heading in one of the design files.
#   2. Charter completeness — every architecture.md §6.x carries all six
#      charter questions.
#   3. Register/intro count consistency — the "twenty/twenty-one components"
#      intro matches the actual register row count.
#   4. Stale-brief check — warns about cowork-to-code-*.md briefs older
#      than 14 days with no matching PR. Warn-only, --full mode only.
#   5. STATUS.md staleness check — fuzzy-matches Ready-for-X rows
#      against recently-merged PR titles. Warn-only, --full mode only.
#      Requires `gh` CLI.
#
# Default (no flags): runs checks 1–3 and exits non-zero on any failure.
# --full mode also runs checks 4 + 5 (warn-only — never fails CI).
#
# Run from the repo root.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2

FAILED=0
MODE="${1:-default}"

echo "== Discipline checks =="

# Check 1 — Cross-ref resolution (blocks merge)
echo ""
python3 scripts/check_crossrefs.py design/ || FAILED=1

# Check 2 — Charter completeness (blocks merge)
echo ""
python3 scripts/check_charters.py design/architecture.md || FAILED=1

# Check 3 — Register / intro count consistency (blocks merge)
echo ""
python3 scripts/check_register_count.py design/architecture.md || FAILED=1

# Check 4 — Stale-brief check (warn-only, --full mode)
if [[ "$MODE" == "--full" ]]; then
    echo ""
    python3 scripts/check_stale_briefs.py || true
fi

# Check 5 — STATUS.md staleness (warn-only, --full mode, needs gh)
if [[ "$MODE" == "--full" ]]; then
    echo ""
    echo "-- STATUS.md staleness (warn-only) --"
    if command -v gh &>/dev/null; then
        gh pr list --state merged --limit 30 \
            --json title,number,mergedAt \
          | python3 scripts/check_status.py --prs-json - || true
    else
        echo "  skipped: gh CLI not available"
    fi
fi

echo ""
if [[ $FAILED -ne 0 ]]; then
    echo "Discipline checks FAILED. See errors above."
    exit 1
fi
echo "All discipline checks passed."
