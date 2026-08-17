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


def _current_repo() -> str | None:
    """nameWithOwner of the repo this script is running in, or None."""
    if not _gh_available():
        return None
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q",
             ".nameWithOwner"],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def _fetch_pr_titles_and_bodies(repos: list[str]) -> tuple[list[str], list[str]]:
    """Return (haystack strings, repos actually searched).

    Includes open PRs plus PRs merged within MATCH_WINDOW_DAYS, across
    every repo named. The outbox is shared by every project on the desk,
    so searching a single repo's PRs and reporting the rest as "forgotten"
    is a scope error, not a finding — the check has to say which repos it
    could see."""
    if not _gh_available():
        return [], []
    out: list[str] = []
    searched: list[str] = []
    for repo in repos:
        cmd = ["gh", "pr", "list", "--state", "all", "--limit", "100",
               "--json", "title,body,state,mergedAt"]
        if repo:
            cmd += ["--repo", repo]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        searched.append(repo)
        out.extend(_parse_prs(result.stdout))
    return out, searched


def _parse_prs(stdout: str) -> list[str]:
    """Flatten one `gh pr list --json` payload into title+body strings,
    keeping open PRs and those merged within MATCH_WINDOW_DAYS."""
    try:
        prs = json.loads(stdout)
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
    parser.add_argument("--repo", action="append", default=[], metavar="OWNER/NAME",
                        help="repo whose PRs can match a brief; repeatable. "
                             "Default: the repo this script runs in. The "
                             "outbox is shared across projects, so a brief "
                             "whose work lives in an unnamed repo cannot be "
                             "matched and is reported as unmatchable, not "
                             "forgotten.")
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

    repos: list[str] = args.repo or [r for r in [_current_repo()] if r]
    if not repos:
        print(
            f"WARN [stale-briefs]: no repo scope — gh CLI unavailable or "
            f"not in a GitHub repo. The {len(briefs)} stale brief(s) below "
            f"could not be matched against anything. This is a scan that "
            f"could not look, not a clean result:"
        )
        for p in briefs:
            print(f"  {p}")
        return 0

    pr_haystack, searched = _fetch_pr_titles_and_bodies(repos)
    if not searched:
        print(
            f"WARN [stale-briefs]: every `gh pr list` call failed for "
            f"{', '.join(repos)}; the {len(briefs)} stale brief(s) below "
            f"could not be matched. Scan failed — not a pass:"
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

    scope = (
        f"   scope: {len(pr_haystack)} PR(s) across {', '.join(searched)}. "
        f"Briefs whose work landed in a repo outside this scope cannot "
        f"match — widen with --repo before treating the list as forgotten."
    )
    if forgotten:
        print(
            f"WARN [stale-briefs]: {len(forgotten)} of {len(briefs)} "
            f"brief(s) older than {args.stale_days} days have no matching "
            f"PR in scope. Either rename to indicate supersession, archive, "
            f"open a PR, or widen the scope:"
        )
        for p in forgotten:
            age_days = (time.time() - p.stat().st_mtime) / 86400
            print(f"  {p} ({age_days:.0f} days old)")
        print(scope)
    else:
        print(
            f"OK [stale-briefs]: all {len(briefs)} stale brief(s) match "
            f"open or recently-merged PRs."
        )
        print(scope)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
