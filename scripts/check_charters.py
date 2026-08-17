#!/usr/bin/env python3
"""
Charter completeness check — scripts/check.sh check 2.

For every §6.x heading in design/architecture.md, asserts the section
contains all six charter questions (Awen role, Why it exists, Consumes,
Produces, Explicit non-goals, What would change if removed). The §6.8
"six CLIs" group is exempt — it's a shared-charter pointer, not a single
component.

The phrases are matched loosely against the section text: a literal
sub-heading like "#### Awen role" counts, as does prose containing
"Awen role." or "Role: Llys" at the start of a sentence. The check is
forgiving on form, strict on substance.

Exit codes:
  0  all §6.x charters complete
  1  one or more missing a question
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# The six charter questions, with matchable phrases. Each tuple is
# (label, regex) — the section text must match at least one regex for
# each question.
CHARTER_QUESTIONS: list[tuple[str, re.Pattern[str]]] = [
    ("Awen role",
     re.compile(r"\bawen role\b|^\s*role\s*[:\.]|\brole\s*[:\.]\s*\w+",
                re.IGNORECASE | re.MULTILINE)),
    ("Why it exists",
     re.compile(r"\bwhy it exists\b|\bwhy[:\.]\s|\bwhy\s+(?:this )?exists\b",
                re.IGNORECASE)),
    ("Consumes",
     re.compile(r"\bconsumes?\b\s*[:\.]|####\s*consumes",
                re.IGNORECASE)),
    ("Produces",
     re.compile(r"\bproduces?\b\s*[:\.]|####\s*produces",
                re.IGNORECASE)),
    ("Explicit non-goals",
     re.compile(r"\bnon[-\s]?goals?\b|\bdoes\s*not\s*do\b|"
                r"####\s*explicit non-goals", re.IGNORECASE)),
    ("What would change if removed",
     re.compile(r"\bif removed\b|\bwhat would change\b|"
                r"\bremoved[:\.]", re.IGNORECASE)),
]

# Sections in §6 that aren't single-component charters and are exempt.
#
# A bare §-number is not a safe exemption. The number is a position, not an
# identity: renumber §6 and "6.8" silently transfers the exemption to
# whatever component now sits in that slot, which then skips all six
# charter questions and still prints OK. So each exemption is bound to a
# fragment of the heading it is meant to excuse, and the binding is
# asserted against architecture.md before any section is skipped.
EXEMPT_SECTIONS: dict[str, str] = {
    "6.8": "six clis",  # "The six CLIs" — shared charter pointer to cli-design.md
}

HEADING_RE = re.compile(r"^###\s*(?:§)?(?P<num>\d+\.\d+(?:\.\d+)?)\s*(?P<title>.*?)\s*$")


def _section_titles(text: str) -> dict[str, str]:
    """§6.x number -> heading title, straight from architecture.md."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m and m.group("num").startswith("6."):
            out[m.group("num")] = m.group("title")
    return out


def assert_exemptions(titles: dict[str, str]) -> list[str]:
    """EXEMPT_SECTIONS is a hard-coded vocabulary; the §6.x headings in
    architecture.md are the schema that defines it. Assert every exemption
    still resolves to the section it was written for — SUBSET of the live
    headings, matched on identity, not merely present."""
    errors: list[str] = []
    for num, expected in EXEMPT_SECTIONS.items():
        if num not in titles:
            errors.append(
                f"EXEMPT_SECTIONS excuses §{num}, but architecture.md has no "
                f"§{num} heading — a dead exemption. Remove it, or restore "
                f"the section."
            )
            continue
        actual = re.sub(r"\W+", " ", titles[num].lower()).strip()
        if expected not in actual:
            errors.append(
                f"EXEMPT_SECTIONS excuses §{num} as {expected!r}, but §{num} "
                f"is now \"{titles[num]}\". The exemption has drifted onto a "
                f"different component, which would skip all six charter "
                f"questions unchecked. Re-point or remove it."
            )
    return errors


def _split_six_sections(text: str) -> list[tuple[str, str]]:
    """Slice architecture.md into (§6.x number, body) pairs."""
    sections: list[tuple[str, str]] = []
    current_num: str | None = None
    current_body: list[str] = []
    for line in text.splitlines(keepends=True):
        m = re.match(r"^###\s*(?:§)?(\d+\.\d+(?:\.\d+)?)", line)
        if m:
            if current_num is not None:
                sections.append((current_num, "".join(current_body)))
            current_num = m.group(1)
            current_body = []
        elif re.match(r"^##\s+\d+\.", line):
            # We've hit the next top-level section (e.g. ## 7. ...).
            if current_num is not None:
                sections.append((current_num, "".join(current_body)))
                current_num = None
                current_body = []
        else:
            if current_num is not None:
                current_body.append(line)
    if current_num is not None:
        sections.append((current_num, "".join(current_body)))
    return [(n, b) for n, b in sections if n.startswith("6.")]


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else "design/architecture.md")
    if not path.is_file():
        print(f"check_charters: {path} not found", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    sections = _split_six_sections(text)

    exemption_errors = assert_exemptions(_section_titles(text))
    if exemption_errors:
        print(
            "FAIL [charter]: exemption vocabulary no longer matches "
            "architecture.md — sections would be skipped unchecked:",
            file=sys.stderr,
        )
        for line in exemption_errors:
            print(f"  {line}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for num, body in sections:
        if num in EXEMPT_SECTIONS:
            continue
        missing = [label for label, regex in CHARTER_QUESTIONS
                   if not regex.search(body)]
        if missing:
            failures.append(
                f"§{num} is missing: {', '.join(missing)}"
            )

    if failures:
        print(
            f"FAIL [charter]: {len(failures)} section(s) missing charter "
            f"answers:",
            file=sys.stderr,
        )
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print(
            "  Half-finished charters must not land — see architecture.md "
            "§4 (charter discipline).",
            file=sys.stderr,
        )
        return 1

    exempt = [n for n, _ in sections if n in EXEMPT_SECTIONS]
    checked = len(sections) - len(exempt)
    print(
        f"OK [charter]: {checked} of {len(sections)} §6.x sections answer "
        f"the six charter questions."
    )
    # Not a silent cap: say which sections were skipped and on what grounds.
    if exempt:
        print(
            "   EXEMPT (not checked): "
            + ", ".join(f"§{n} ({EXEMPT_SECTIONS[n]})" for n in exempt)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
