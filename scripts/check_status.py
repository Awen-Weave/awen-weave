#!/usr/bin/env python3
"""
check_status.py — heuristic STATUS.md staleness detector.

Parses STATUS.md sections (Ready for Code, Ready for Cowork, Blocked) and
fuzzy-matches each row against recently-merged PR titles. Warns on possible
completions that may not have been removed.

Designed to run in `bash scripts/check.sh --full` mode. **Warn-only** — never
fails CI or blocks merges. Output is operator-facing: "verify and act."

Heuristic and noisy by design. The value is catching obvious cases (a row
whose subject closely matches a PR title is almost certainly the row that
PR closed). False positives are cheap to dismiss; the staleness it catches
is what bit IDR-006 on 2026-05-17.

Usage:
  gh pr list --state merged --limit 30 --json title,number,mergedAt \\
    | python3 scripts/check_status.py --prs-json -

  # Or with a saved PR list:
  gh pr list --state merged --limit 30 --json title,number,mergedAt > /tmp/prs.json
  python3 scripts/check_status.py --prs-json /tmp/prs.json

  # Or against a specific STATUS.md (defaults to ./STATUS.md):
  python3 scripts/check_status.py --status-md path/to/STATUS.md --prs-json -

Exit codes:
  0 — always (warn-only by design). Output is the signal.

Future work (v2):
  - Detect resolved-blocker case: parse "Blocked on" cells, check if
    the named blocker matches a recent PR (means the dependent may now
    be unblocked).
  - Detect resolved-decision case: scan Recent decisions log for entries
    matching open architectural decisions; warn if open-decisions row
    matches a recent log entry's keywords.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

# Words that don't carry meaning for matching — common in PR titles + STATUS.md rows.
STOPWORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "for", "on", "and", "or", "with",
    "is", "be", "by", "at", "as", "from", "this", "that", "into",
    "pr", "fix", "add", "update", "build", "land", "ship", "implement",
    "code", "cowork", "work", "task", "v1", "v2", "v0", "via",
})

MATCH_THRESHOLD = 0.5  # Jaccard similarity threshold for "strong match"


def normalise_words(text: str) -> set[str]:
    """Lowercase, strip punctuation, drop stopwords, return word set."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |a ∩ b| / |a ∪ b|. Returns 0 if both empty."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def parse_status_md_sections(text: str, section_names: list[str]) -> dict[str, list[str]]:
    """Parse STATUS.md, extract rows from each named section.

    Returns dict mapping section_name -> list of row subjects (first
    table cell, stripped). Sections found via "## <name>" headers.
    """
    out = {name: [] for name in section_names}
    lines = text.splitlines()

    current_section = None
    for line in lines:
        stripped = line.strip()
        # Section header?
        m = re.match(r"^##\s+(.+?)\s*$", stripped)
        if m:
            heading = m.group(1)
            current_section = None
            for name in section_names:
                if heading.lower().startswith(name.lower()):
                    current_section = name
                    break
            continue
        # In a target section, look for table rows
        if current_section and stripped.startswith("|") and not stripped.startswith("|---"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not cells:
                continue
            subject = cells[0]
            # Skip header rows (where first cell looks like a header)
            if subject.lower() in ("item", "name", "task", "subject"):
                continue
            # Skip empty / placeholder rows
            if not subject or subject.startswith("_(") or subject == "—":
                continue
            out[current_section].append(subject)
    return out


def load_prs(prs_json_arg: str) -> list[dict]:
    """Load PR list from --prs-json (file path or '-' for stdin)."""
    if prs_json_arg == "-":
        data = json.load(sys.stdin)
    else:
        with open(prs_json_arg) as f:
            data = json.load(f)
    # gh outputs a list; normalise the field names we use
    return data if isinstance(data, list) else data.get("prs", [])


def check_section(
    section_name: str, rows: list[str], prs: list[dict], threshold: float
) -> list[str]:
    """Return list of warning strings for rows in this section."""
    warnings = []
    for row_subject in rows:
        row_words = normalise_words(row_subject)
        if not row_words:
            continue
        for pr in prs:
            pr_title = pr.get("title", "")
            pr_words = normalise_words(pr_title)
            score = jaccard(row_words, pr_words)
            if score >= threshold:
                pr_num = pr.get("number", "?")
                pr_date = pr.get("mergedAt", "")[:10] if pr.get("mergedAt") else ""
                date_str = f" ({pr_date})" if pr_date else ""
                warnings.append(
                    f"  {section_name}: '{row_subject}'\n"
                    f"    may be completed by PR #{pr_num}: '{pr_title}'{date_str}\n"
                    f"    similarity: {score:.2f}\n"
                    f"    → verify and remove from STATUS.md if applicable"
                )
                break  # one warning per row
    return warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Heuristic STATUS.md staleness detector. Warn-only."
    )
    parser.add_argument(
        "--status-md", default="STATUS.md",
        help="Path to STATUS.md (default: ./STATUS.md)"
    )
    parser.add_argument(
        "--prs-json", required=True,
        help="Path to JSON file with recent merged PRs, or '-' for stdin. "
             "Expected format: list of {title, number, mergedAt}."
    )
    parser.add_argument(
        "--threshold", type=float, default=MATCH_THRESHOLD,
        help=f"Jaccard similarity threshold (0.0–1.0, default {MATCH_THRESHOLD})"
    )
    args = parser.parse_args(argv[1:])

    status_path = Path(args.status_md)
    if not status_path.exists():
        print(f"check_status: {status_path} not found", file=sys.stderr)
        return 0  # warn-only; missing file is not an error

    text = status_path.read_text(encoding="utf-8")
    sections = parse_status_md_sections(
        text, ["Ready for Code", "Ready for Cowork", "Blocked"]
    )
    prs = load_prs(args.prs_json)

    all_warnings = []
    for section_name, rows in sections.items():
        all_warnings.extend(check_section(section_name, rows, prs, args.threshold))

    if all_warnings:
        print("WARN [status]: STATUS.md may have stale rows:")
        for w in all_warnings:
            print(w)
        print(f"\n[{len(all_warnings)} warnings; warn-only, see foundation §3.1 for the mutate-on-PR discipline]")
    else:
        print("OK [status]: no obvious staleness against the recent PR list.")

    return 0  # always warn-only


if __name__ == "__main__":
    sys.exit(main(sys.argv))
