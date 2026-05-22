"""
src/craidd/placenames — authoritative bilingual Welsh place-names.

Reference module sourced from the Welsh Language Commissioner's
**List of Standardised Welsh Place-names** (OGL v3). The list is
maintained by the Place-names Standardisation Panel and is the
national authority for correct Welsh forms of UK place-names in
Wales.

This module is a *naming authority*, NOT a spatial place-pack layer.
Instances of Awen Weave (e.g. the Dolgellau Town Dataset) READ from
it — they do not ingest a copy of it. Rationale: a national
standardised-naming authority is domain-agnostic reference data,
exactly like the predicate vocabulary that already lives in the
framework. Build it once in `awen-weave`; every instance reads from
it. Parallels the [framework-holds-method, instance-holds-content]
rule.

Provenance
----------
Source     Welsh Language Commissioner / Comisiynydd y Gymraeg
           "List of Standardised Welsh Place-names"
           https://www.welshlanguagecommissioner.wales/standard-welsh-place-names
Vintage    2026-05-22 (download date; the panel maintains rolling
           updates — see `data/README.md` for the captured snapshot)
Licence    Open Government Licence v3.0 (page asserts OGL 3.0
           except where otherwise stated)
Format     CSV (3,616 rows incl. header; Welsh-first column order)
Fields     - Ffurf safonol (welsh_name)
           - Ffurf safonol arall (welsh_name_alt)
           - Ffurf Saesneg (english_name)
           - Cyfeirnod grid (grid_ref, e.g. SH7217)
           - Math (Cymraeg) (place_type_cy)
           - Math (Saesneg) (place_type_en)
           - Awdurdod lleol (Cymraeg) (local_authority_cy)
           - Awdurdod lleol (Saesneg) (local_authority_en)

Attribution required in any pack content quoting these names:
  "Source: Welsh Language Commissioner / Comisiynydd y Gymraeg —
   List of Standardised Welsh Place-names (Open Government Licence v3)."

Refresh policy
--------------
The Place-names Standardisation Panel publishes rolling updates, not
fixed-cadence. A future PR should refresh `data/standardised-welsh-
place-names-<DATE>.csv` and rename `_CSV_FILENAME` below. The
authority's external contract is the lookup API on this module; the
CSV path is an internal implementation detail.

Public API
----------
The exported names below are the stable surface; the CSV layout is
not. See `authority.py` for the lookup functions:

  - lookup_by_welsh(name) -> PlaceName | None
  - lookup_by_english(name) -> PlaceName | None
  - lookup_by_grid_ref(grid_ref) -> list[PlaceName]
  - subset_by_local_authority(la_en) -> list[PlaceName]
  - all_records() -> list[PlaceName]

Design discipline (Huw 2026-05-22)
----------------------------------
- This is a *suggest/validate* authority, NOT an auto-rewriter. An
  instance's `name_cy` schema field may *consult* this module to
  suggest a standardised Welsh form; the curator / tutor retains
  authority over what's claimed. Don't push automatic overwrites
  into Craidd from this module.
"""

from .authority import (
    PlaceName,
    lookup_by_welsh,
    lookup_by_english,
    lookup_by_grid_ref,
    subset_by_local_authority,
    all_records,
    CSV_FILENAME,
    CSV_VINTAGE,
    SOURCE_URL,
    LICENCE,
    ATTRIBUTION,
)

__all__ = [
    "PlaceName",
    "lookup_by_welsh",
    "lookup_by_english",
    "lookup_by_grid_ref",
    "subset_by_local_authority",
    "all_records",
    "CSV_FILENAME",
    "CSV_VINTAGE",
    "SOURCE_URL",
    "LICENCE",
    "ATTRIBUTION",
]
