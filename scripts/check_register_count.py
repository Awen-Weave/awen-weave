#!/usr/bin/env python3
"""
Register-count consistency check — scripts/check.sh check 3.

Asserts that the count word in design/architecture.md's §3 intro line
("twenty components", "twenty-one components", ...) matches the actual
row count in the §3 register table. Catches the count-drift pattern that
bit Code on 2026-05-12 when memory claimed "20th component" while the
register held 18.

Exit codes:
  0  intro count matches register row count
  1  mismatch
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Word ↔ number map. Extend as the register grows.
WORD_TO_NUMBER: dict[str, int] = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
    "twenty-one": 21, "twenty-two": 22, "twenty-three": 23,
    "twenty-four": 24, "twenty-five": 25, "twenty-six": 26,
    "twenty-seven": 27, "twenty-eight": 28, "twenty-nine": 29,
    "thirty": 30,
}
NUMBER_TO_WORD: dict[int, str] = {v: k for k, v in WORD_TO_NUMBER.items()}

INTRO_RE = re.compile(
    r"That's\s+(?P<word>[a-z-]+)\s+components",
    re.IGNORECASE,
)


def _count_register_rows(text: str) -> int:
    """Count rows in the §3 component register table.

    The table starts at '| Component | Role | ...' and ends at the first
    blank line after the header separator '|---|...|'. Each non-separator
    row contributes one component.
    """
    lines = text.splitlines()
    in_table = False
    header_seen = False
    rows = 0
    for line in lines:
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("| Component"):
                in_table = True
                header_seen = False
            continue
        if stripped == "":
            break  # end of table
        if not stripped.startswith("|"):
            break
        if not header_seen and re.match(r"^\|[\s:|\-]+\|\s*$", stripped):
            header_seen = True
            continue
        if header_seen:
            rows += 1
    return rows


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else "design/architecture.md")
    if not path.is_file():
        print(f"check_register_count: {path} not found", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")

    m = INTRO_RE.search(text)
    if m is None:
        print(
            "FAIL [register-count]: could not find the §3 intro count "
            "line (expected 'That's <word> components').",
            file=sys.stderr,
        )
        return 1

    word = m.group("word").lower()
    if word not in WORD_TO_NUMBER:
        print(
            f"FAIL [register-count]: §3 intro count word '{word}' is not "
            f"in the known WORD_TO_NUMBER map. Extend the map in "
            f"scripts/check_register_count.py.",
            file=sys.stderr,
        )
        return 1

    stated = WORD_TO_NUMBER[word]
    actual = _count_register_rows(text)

    if stated != actual:
        suggested = NUMBER_TO_WORD.get(actual, str(actual))
        print(
            f"FAIL [register-count]: §3 intro reads '{word} components' "
            f"({stated}) but the register table contains {actual} rows. "
            f"Update the intro to '{suggested} components' or correct the "
            f"register.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK [register-count]: §3 intro says '{word}' ({stated}) and "
        f"the register has {actual} rows — consistent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
