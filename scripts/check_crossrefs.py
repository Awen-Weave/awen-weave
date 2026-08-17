#!/usr/bin/env python3
"""
Cross-reference resolver — scripts/check.sh's most valuable check.

Scans design/*.md for references of the shape:
  - §N.M                       (e.g. §6.21, §6.10)
  - §N.M (named description)   (e.g. §6.10 (proposal queue))
  - §N item M                  (e.g. §10 item 7)

For each reference, resolves the target across the family of design
files (architecture.md, v0.1-schema.md, cli-design.md, roadmap.md,
constitutional-framework.md, ...): if any of them has a heading numbered
§N.M, the reference resolves. This is the refinement of the Cowork
prototype (`outbox/crossref-resolver-prototype.py`) that the
test-infrastructure brief §1.3a invites — the prototype routed all
non-§10 references to architecture.md and produced 56 false positives on
first run against the current design tree.

For references with a (parenthetical), the check fires only when the
parenthetical looks like a section name (not editorial annotation like
"new component, register count 19 → 20") AND has zero content-word
overlap with the resolved heading. The Phase 0 §6.10 mismatch case —
"(proposal queue)" against "Curator-identity layer" — is exactly what
this is designed to catch.

Exit codes:
  0  all references resolve cleanly
  1  one or more failed; details on stderr
"""
from __future__ import annotations
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# --- reference patterns ----------------------------------------------------
REF_DOTTED = re.compile(
    r"§(?P<sec>\d+)\.(?P<sub>\d+(?:\.\d+)?)(?:\s*\((?P<name>[^)]+)\))?"
)
REF_ITEM = re.compile(
    r"§(?P<sec>\d+)\s+item\s+(?P<item>\d+(?:\.\d+)?)"
)

# --- routing ---------------------------------------------------------------
# Files the resolver knows about. A §N.M reference resolves cleanly if any
# of these carries a §N.M heading. The list is the natural place to grow as
# the doc surface expands — add the next file here and the resolver picks it up.
KNOWN_FILES: tuple[str, ...] = (
    "architecture.md",
    "v0.1-schema.md",
    "cli-design.md",
    "roadmap.md",
    "constitutional-framework.md",
    "lleolydd.md",
    "entity-proposal-shape.md",
    "client-contract.md",
    "craidd-foundation-handover.md",
    "craidd-propose-spec.md",
    "bra-proposal-handoff.md",
    "building-research-agent.md",
    "bra-v2-estate-agents.md",
    "bra-v2-estate-agents-pilot.md",
    "v0-schema.md",
    "migration-2026-05.md",
)


def assert_vocabulary(design_dir: Path) -> list[str]:
    """KNOWN_FILES is a hard-coded vocabulary; design/*.md is the schema
    that defines it. Assert the two are the same set — SUBSET in both
    directions, not a non-empty intersection.

    A name in KNOWN_FILES that no longer exists is a router entry that can
    never resolve: `idx.get()` returns [] and the resolver walks past it in
    silence. A file on disk that isn't in KNOWN_FILES is worse — its
    headings are never a resolution target from anywhere, and references
    originating in it lose self-first routing, so a §N.M defined only there
    either fails or resolves against a same-numbered heading in an
    unrelated file. Both are the "scan that could not look" failure: the
    run reports OK because it never looked, not because it found nothing.
    """
    on_disk = {p.name for p in design_dir.glob("*.md")}
    vocabulary = set(KNOWN_FILES)
    errors: list[str] = []
    for dead in sorted(vocabulary - on_disk):
        errors.append(
            f"KNOWN_FILES lists '{dead}' but no such file exists in "
            f"{design_dir}/ — a routing entry that can never resolve. "
            f"Remove it, or restore the file."
        )
    for unrouted in sorted(on_disk - vocabulary):
        errors.append(
            f"{design_dir}/{unrouted} exists but is not in KNOWN_FILES — "
            f"its headings can never be a resolution target and its own "
            f"references lose self-first routing. Add it to KNOWN_FILES."
        )
    return errors

# A parenthetical that begins with one of these tokens, or contains one
# of the ANNOTATION_MARKERS, is editorial annotation about the reference
# itself rather than a section name. We skip the name-match check.
ANNOTATION_LEADERS: frozenset[str] = frozenset({
    "new", "pending", "tbd", "wip", "draft",
    "added", "now", "removed", "renamed", "see",
})

ANNOTATION_MARKERS: tuple[str, ...] = (
    "→", "->", "register count", "new component", "deprecated",
    "renamed from", "moved from", "see also",
)

# Stopwords for content-overlap matching. Editorial fluff that shouldn't
# count as evidence that a parenthetical describes the section.
STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "and", "or", "to", "for", "in", "on",
    "pending", "draft", "tbd", "wip", "v1", "v2", "new", "register",
    "count", "component", "now", "next", "later", "with",
})


# --- heading indexing ------------------------------------------------------
@dataclass
class Heading:
    file: str
    line: int
    level: int
    number: str      # "6.21" or "10" or "7.6"
    name: str        # "Lleolydd — UPRN..."

HEADING_RE = re.compile(
    r"^(#{1,6})\s*(?:§)?(?P<num>\d+(?:\.\d+)?(?:\.\d+)?)\s*[—\-:.]?\s*(?P<name>.*?)\s*$"
)


def index_headings(design_dir: Path) -> dict[str, list[Heading]]:
    idx: dict[str, list[Heading]] = defaultdict(list)
    for md in sorted(design_dir.glob("*.md")):
        with md.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.rstrip("\n")
                if not line.startswith("#"):
                    continue
                m = HEADING_RE.match(line)
                if not m:
                    continue
                level = len(line) - len(line.lstrip("#"))
                idx[md.name].append(Heading(
                    file=md.name,
                    line=lineno,
                    level=level,
                    number=m.group("num"),
                    name=m.group("name").strip(),
                ))
    return idx


# --- reference extraction --------------------------------------------------
@dataclass
class Reference:
    file: str
    line: int
    raw: str
    kind: str            # 'section' or 'item'
    number: str          # "6.10", "7.6", or item-only "7"
    expected_name: str | None
    major: str | None = None   # item refs only: the §N in "§N item M"


def extract_refs(design_dir: Path) -> list[Reference]:
    refs: list[Reference] = []
    for md in sorted(design_dir.glob("*.md")):
        with md.open(encoding="utf-8") as f:
            in_code_block = False
            for lineno, line in enumerate(f, start=1):
                # Track fenced code blocks loosely — references inside
                # code samples are documentation snippets, not live refs.
                if line.lstrip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    continue
                if line.startswith("#"):
                    continue  # headings are the targets, not refs

                for m in REF_DOTTED.finditer(line):
                    sec, sub = m.group("sec"), m.group("sub")
                    name = m.group("name")
                    refs.append(Reference(
                        file=md.name,
                        line=lineno,
                        raw=m.group(0),
                        kind="section",
                        number=f"{sec}.{sub}",
                        expected_name=name.strip() if name else None,
                    ))
                for m in REF_ITEM.finditer(line):
                    sec, item = m.group("sec"), m.group("item")
                    refs.append(Reference(
                        file=md.name,
                        line=lineno,
                        raw=m.group(0),
                        kind="item",
                        number=item,
                        expected_name=None,
                        major=sec,
                    ))
    return refs


# --- resolution ------------------------------------------------------------
def _normalise(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def _is_annotation(parenthetical: str) -> bool:
    """Editorial annotation vs section-name description?"""
    lowered = parenthetical.lower()
    for marker in ANNOTATION_MARKERS:
        if marker in lowered:
            return True
    first_word = (_normalise(parenthetical).split() or [""])[0]
    return first_word in ANNOTATION_LEADERS


def _content_words(s: str) -> set[str]:
    return {
        w for w in _normalise(s).split()
        if w and w not in STOPWORDS and not w.isdigit()
    }


def _candidate_files(ref: Reference) -> list[str]:
    """Files that could plausibly host this reference's target. The
    reference's own file is checked first — many docs self-reference their
    own §-numbered sections (roadmap.md §4.x, lleolydd.md §12.x, etc.) and
    those should resolve before the resolver looks elsewhere."""
    if ref.file in KNOWN_FILES:
        return [ref.file] + [f for f in KNOWN_FILES if f != ref.file]
    return list(KNOWN_FILES)


ITEM_MARKER = re.compile(r"^(?P<num>\d+)\.\s+\S")


def index_items(design_dir: Path) -> dict[str, dict[str, set[str]]]:
    """Map file -> §N -> {top-level ordered-list item numbers under §N}.

    This is the schema that defines the item vocabulary. §10 of
    v0.1-schema.md carries its eight open questions as a numbered list
    rather than as nested headings, so `§10 item 7` has to be checked
    against the list, not against a §10.7 heading that was never going to
    exist. Only column-0 markers count — indented `1.` inside an item's
    own sub-list belongs to that item, not to §N.
    """
    out: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for md in sorted(design_dir.glob("*.md")):
        current: str | None = None
        for line in md.read_text(encoding="utf-8").splitlines():
            head = re.match(r"^##\s*(?:§)?(?P<num>\d+)\.?\s", line)
            if head:
                current = head.group("num")
                continue
            if line.startswith("#"):
                continue
            if current is None:
                continue
            m = ITEM_MARKER.match(line)
            if m:
                out[md.name][current].add(m.group("num"))
    return {f: dict(secs) for f, secs in out.items()}


def resolve(
    ref: Reference,
    idx: dict[str, list[Heading]],
    item_idx: dict[str, dict[str, set[str]]] | None = None,
) -> list[str]:
    """Return a list of error messages — empty when the reference is clean."""
    errors: list[str] = []
    item_idx = item_idx if item_idx is not None else {}

    if ref.kind == "item":
        major = ref.major or "10"
        top = ref.number.split(".")[0]
        candidates = _candidate_files(ref)

        # Find the file that actually carries §<major>, then assert the
        # item number against the ordered list under it. The previous
        # implementation returned clean whenever *any* candidate carried a
        # bare §10 heading — which made every item reference vacuous:
        # "§10 item 999" and "§7 item 3" both passed, because the §-number
        # was discarded and membership was never tested.
        host: str | None = None
        for target in candidates:
            if any(h.number == major for h in idx.get(target, [])):
                host = target
                break
        if host is None:
            errors.append(
                f"{ref.file}:{ref.line} references '{ref.raw}' but no "
                f"candidate file carries a §{major} heading at all."
            )
            return errors

        available = item_idx.get(host, {}).get(major, set())
        if not available:
            errors.append(
                f"{ref.file}:{ref.line} references '{ref.raw}' and {host} "
                f"§{major} exists, but no ordered list could be parsed "
                f"under it — the item number cannot be checked. Give §{major} "
                f"a numbered list, or stop referencing it by item."
            )
            return errors
        if top not in available:
            errors.append(
                f"{ref.file}:{ref.line} references '{ref.raw}' but {host} "
                f"§{major} has items "
                f"{', '.join(sorted(available, key=int))} — no item {top}."
            )
        return errors

    # §N.M dotted reference. Walk candidate files for the first match.
    candidates = _candidate_files(ref)
    target_heading: Heading | None = None
    target_file: str | None = None
    for fname in candidates:
        match = next(
            (h for h in idx.get(fname, []) if h.number == ref.number),
            None,
        )
        if match is not None:
            target_heading = match
            target_file = fname
            break

    if target_heading is None:
        major = ref.number.split(".")[0]
        siblings: list[tuple[str, str]] = []
        for fname in candidates:
            for h in idx.get(fname, []):
                if h.number.startswith(major + "."):
                    siblings.append((fname, h.number))
        siblings_str = (
            "  Existing §" + major + ".x: "
            + ", ".join(f"{f}:{n}" for f, n in siblings[:8])
            + ("..." if len(siblings) > 8 else "")
            if siblings else ""
        )
        errors.append(
            f"{ref.file}:{ref.line} references '{ref.raw}' but no candidate "
            f"file carries §{ref.number}.{siblings_str}"
        )
        return errors

    # Reference resolves. Check the parenthetical only when it looks like
    # a section-name description, not editorial annotation.
    if ref.expected_name and not _is_annotation(ref.expected_name):
        expected_words = _content_words(ref.expected_name)
        actual_words = _content_words(target_heading.name)
        if expected_words and actual_words and not (expected_words & actual_words):
            errors.append(
                f"{ref.file}:{ref.line} references '{ref.raw}' but "
                f"{target_file} §{target_heading.number} is actually "
                f"\"{target_heading.name}\". Did you mean a different "
                f"§-number, or update the description?"
            )
    return errors


# --- entrypoint ------------------------------------------------------------
def main(argv: list[str]) -> int:
    design_dir = Path(argv[1] if len(argv) > 1 else "design")
    if not design_dir.is_dir():
        print(f"check_crossrefs: {design_dir} not found", file=sys.stderr)
        return 2

    vocab_errors = assert_vocabulary(design_dir)
    if vocab_errors:
        print(
            f"FAIL [cross-ref]: KNOWN_FILES does not match {design_dir}/ — "
            f"the resolver is not looking where it claims to look:",
            file=sys.stderr,
        )
        for err in vocab_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    idx = index_headings(design_dir)
    item_idx = index_items(design_dir)
    refs = extract_refs(design_dir)

    errors: list[str] = []
    for ref in refs:
        errors.extend(resolve(ref, idx, item_idx))

    if errors:
        print(
            f"FAIL [cross-ref]: {len(errors)} unresolved reference(s):",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    items = [r for r in refs if r.kind == "item"]
    subparts = [r for r in items if "." in r.number]
    print(
        f"OK [cross-ref]: {len(refs)} references across "
        f"{sum(1 for f, headings in idx.items() if headings)} files "
        f"all resolve."
    )
    print(
        f"   vocabulary: KNOWN_FILES ({len(KNOWN_FILES)}) == design/*.md "
        f"({len(list(design_dir.glob('*.md')))}); "
        f"{len(items)} item-reference(s) checked against parsed lists."
    )
    if subparts:
        # Not a silent cap: sub-parts like "item 7.1" are prose inside the
        # parent item, not enumerated structure. Only the parent is checked.
        print(
            f"   NOT CHECKED: {len(subparts)} item-reference(s) name a "
            f"sub-part the corpus does not enumerate — parent item only: "
            + ", ".join(sorted({r.raw for r in subparts}))
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
