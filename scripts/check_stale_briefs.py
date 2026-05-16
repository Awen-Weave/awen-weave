#!/usr/bin/env python3
"""
Stale-brief check — scripts/check.sh check 4 (warn-only, --full mode).

For each `cowork-to-code-*.md` file in `~/CoworkOutbox/IDR-006 Awen/`
older than N days (default 14) with no matching PR — open, or merged
within the last 30 days — emit a warning. Stale briefs aren't a merge
blocker, but they signal forgotten routing work.

Requires `gh` CLI configured for repo access. If `gh` is unavailable or
the outbox directory doesn't exist locally (typical in CI), the check
prints a short note and returns 0 — warn-only is genuinely advisory.

Exit codes:
  0  always (warn-only). Stale briefs are printed but never fail CI.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_OUTBOX = Path(os.path.expanduser("~/CoworkOutbox/IDR-006 Awen"))
DEFAULT_STALE_DAYS = 14
MATCH_WINDOW_DAYS = 30


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _list_briefs(outbox: Path, stale_days: int) -> list[Path]:
    if not outbox.is_dir():
        return []
    cutoff = time.time() - stale_days * 86400
    return sorted(
        p for p in outbox.glob("cowork-to-code-*.md")
        if p.is_file() and p.stat().st_mtime < cutoff
    )


def _fetch_pr_titles_and_bodies() -> list[str]:
    """Return a flat list of strings to grep for brief names. Includes
    open PRs plus PRs merged within MATCH_WINDOW_DAYS. Returns [] if gh
    isn't available or the call fails."""
    if not _gh_available():
        return []
    try:
        result = subprocess.run(
            ["gh", "pr", "list",
             "--state", "all",
             "--limit", "100",
             "--json", "title,body,state,mergedAt"],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    try:
        prs = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    cutoff = time.time() - MATCH_WINDOW_DAYS * 86400
    out: list[str] = []
    for pr in prs:
        state = pr.get("state")
        merged_at = pr.get("mergedAt")
        if state == "OPEN":
            keep = True
        elif state == "MERGED" and merged_at:
            # GitHub returns RFC3339 timestamps. Parse loosely.
            try:
                import datetime as _dt
                ts = _dt.datetime.fromisoformat(
                    merged_at.replace("Z", "+00:00")
                ).timestamp()
                keep = ts >= cutoff
            except ValueError:
                keep = False
        else:
            keep = False
        if keep:
            out.append(pr.get("title", "") + "\n" + (pr.get("body") or ""))
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_stale_briefs")
    parser.add_argument("--outbox", type=Path, default=DEFAULT_OUTBOX,
                        help=f"path to outbox (default: {DEFAULT_OUTBOX})")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS,
                        help=f"stale threshold in days (default: "
                             f"{DEFAULT_STALE_DAYS})")
    args = parser.parse_args(argv[1:] if len(argv) > 1 else [])

    outbox: Path = args.outbox
    if not outbox.is_dir():
        print(
            f"check_stale_briefs: {outbox} not found — skipping "
            f"(typical in CI; the outbox is local to the curator's machine)."
        )
        return 0

    briefs = _list_briefs(outbox, args.stale_days)
    if not briefs:
        print(
            f"OK [stale-briefs]: no cowork-to-code-*.md briefs older than "
            f"{args.stale_days} days in {outbox}."
        )
        return 0

    pr_haystack = _fetch_pr_titles_and_bodies()
    if not pr_haystack:
        print(
            f"WARN [stale-briefs]: gh CLI unavailable or no PRs returned; "
            f"cannot match the {len(briefs)} stale brief(s) below against "
            f"PRs. Listing them anyway:"
        )
        for p in briefs:
            print(f"  {p}")
        return 0

    haystack = "\n---\n".join(pr_haystack)
    forgotten: list[Path] = []
    for brief in briefs:
        if brief.name in haystack or brief.stem in haystack:
            continue
        forgotten.append(brief)

    if forgotten:
        print(
            f"WARN [stale-briefs]: {len(forgotten)} brief(s) older than "
            f"{args.stale_days} days have no matching PR. Either rename to "
            f"indicate supersession, archive, or open a PR:"
        )
        for p in forgotten:
            age_days = (time.time() - p.stat().st_mtime) / 86400
            print(f"  {p} ({age_days:.0f} days old)")
    else:
        print(
            f"OK [stale-briefs]: all {len(briefs)} stale brief(s) match "
            f"open or recently-merged PRs."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
