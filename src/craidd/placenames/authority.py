"""
The lookup API for the standardised Welsh place-names authority.

The CSV is loaded once at module import and cached in module-level
dicts (`_BY_WELSH`, `_BY_ENGLISH`) for O(1) lookups. Multi-valued
entries (e.g. duplicate English names for distinct Welsh places —
two different "Tywyn" entries in Gwynedd / Conwy) are preserved as
lists; the singular lookups return the first match and a `*_all`
variant returns the full list.

NB: name normalisation
----------------------
Welsh place-names contain diacritics, hyphens, apostrophes, and
case variation. We normalise lookup keys by:
  - lowercasing
  - stripping leading/trailing whitespace
  - collapsing internal whitespace runs to single space
We do NOT strip diacritics or hyphens — those carry meaning in
Welsh and removing them would conflate distinct names. Callers
that need a softer match should canonicalise externally.
"""

from __future__ import annotations

import csv
import importlib.resources as ir
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable


# --- Provenance constants (also re-exported via __init__) -----------------

CSV_FILENAME = "standardised-welsh-place-names-2026-05-22.csv"
CSV_VINTAGE = "2026-05-22"
SOURCE_URL = (
    "https://www.welshlanguagecommissioner.wales/standard-welsh-place-names"
)
LICENCE = "OGL v3.0"
ATTRIBUTION = (
    "Source: Welsh Language Commissioner / Comisiynydd y Gymraeg — "
    "List of Standardised Welsh Place-names (Open Government Licence v3)."
)


# --- Record shape ---------------------------------------------------------

@dataclass(frozen=True)
class PlaceName:
    """One row of the standardised Welsh place-names list.

    Welsh-first because the source is Welsh-first.
    """
    welsh_name: str
    welsh_name_alt: str | None
    english_name: str | None
    grid_ref: str | None
    place_type_cy: str | None
    place_type_en: str | None
    local_authority_cy: str | None
    local_authority_en: str | None


def _normalise(name: str | None) -> str | None:
    if name is None:
        return None
    s = " ".join(str(name).strip().split())
    if not s:
        return None
    return s.lower()


# --- One-time load --------------------------------------------------------

def _load_records() -> tuple[list[PlaceName], dict[str, list[int]], dict[str, list[int]], dict[str, list[int]]]:
    """Parse the bundled CSV and return:
      (records,
       by_welsh: lower-case-Welsh-name → [record_index, ...],
       by_english: lower-case-English-name → [record_index, ...],
       by_grid_ref: grid_ref (uppercased, no spaces) → [record_index, ...])
    """
    records: list[PlaceName] = []
    by_welsh: dict[str, list[int]] = defaultdict(list)
    by_english: dict[str, list[int]] = defaultdict(list)
    by_grid: dict[str, list[int]] = defaultdict(list)
    pkg = "craidd.placenames.data"
    csv_path = ir.files(pkg).joinpath(CSV_FILENAME)
    text = csv_path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    # Source columns: 'Ffurf safonol', 'Ffurf safonol arall ', 'Ffurf Saesneg',
    # 'Cyfeirnod grid', 'Math (Cymraeg)', 'Math (Saesneg)',
    # 'Awdurdod lleol (Cymraeg)', 'Awdurdod lleol (Saesneg)'
    # Note trailing space on 'Ffurf safonol arall '.
    for raw in reader:
        # Trim whitespace from keys (defensive against the trailing space) and values
        row = {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
        welsh = row.get("Ffurf safonol")
        if not welsh:
            continue
        rec = PlaceName(
            welsh_name=welsh,
            welsh_name_alt=row.get("Ffurf safonol arall") or None,
            english_name=row.get("Ffurf Saesneg") or None,
            grid_ref=(row.get("Cyfeirnod grid") or "").upper().replace(" ", "") or None,
            place_type_cy=row.get("Math (Cymraeg)") or None,
            place_type_en=row.get("Math (Saesneg)") or None,
            local_authority_cy=row.get("Awdurdod lleol (Cymraeg)") or None,
            local_authority_en=row.get("Awdurdod lleol (Saesneg)") or None,
        )
        idx = len(records)
        records.append(rec)
        w_key = _normalise(rec.welsh_name)
        if w_key:
            by_welsh[w_key].append(idx)
        e_key = _normalise(rec.english_name)
        if e_key:
            by_english[e_key].append(idx)
        if rec.grid_ref:
            by_grid[rec.grid_ref].append(idx)
    return records, dict(by_welsh), dict(by_english), dict(by_grid)


_RECORDS, _BY_WELSH, _BY_ENGLISH, _BY_GRID = _load_records()


# --- Lookup API -----------------------------------------------------------

def lookup_by_welsh(name: str) -> PlaceName | None:
    """Return the first record matching the given Welsh standard form
    (case-insensitive, whitespace-normalised; diacritics preserved).
    None if no match."""
    key = _normalise(name)
    if not key:
        return None
    idxs = _BY_WELSH.get(key)
    if not idxs:
        return None
    return _RECORDS[idxs[0]]


def lookup_by_welsh_all(name: str) -> list[PlaceName]:
    """Multi-valued variant — return every record matching the given
    Welsh name. Useful for ambiguous names like 'Tywyn' (Gwynedd + Conwy)."""
    key = _normalise(name)
    if not key:
        return []
    return [_RECORDS[i] for i in _BY_WELSH.get(key, [])]


def lookup_by_english(name: str) -> PlaceName | None:
    """Return the first record matching the given English form. None if
    no match."""
    key = _normalise(name)
    if not key:
        return None
    idxs = _BY_ENGLISH.get(key)
    if not idxs:
        return None
    return _RECORDS[idxs[0]]


def lookup_by_english_all(name: str) -> list[PlaceName]:
    key = _normalise(name)
    if not key:
        return []
    return [_RECORDS[i] for i in _BY_ENGLISH.get(key, [])]


def lookup_by_grid_ref(grid_ref: str) -> list[PlaceName]:
    """Return all records carrying the given OS grid reference (e.g.
    'SH7217' for Dolgellau). Empty list if none."""
    key = (grid_ref or "").upper().replace(" ", "")
    if not key:
        return []
    return [_RECORDS[i] for i in _BY_GRID.get(key, [])]


@lru_cache(maxsize=32)
def subset_by_local_authority(la_en: str) -> tuple[PlaceName, ...]:
    """Return all records whose English-form local authority matches.
    Cached because the typical caller asks for the same LA repeatedly."""
    target = _normalise(la_en)
    if not target:
        return ()
    return tuple(r for r in _RECORDS
                 if _normalise(r.local_authority_en) == target)


def all_records() -> list[PlaceName]:
    """The full loaded list. Read-only — callers should not mutate."""
    return list(_RECORDS)
