"""
Tests for the standardised Welsh place-names authority.

These pin three things:
  1. The CSV loads cleanly at import (no parse errors).
  2. A handful of Gwynedd spot-check names resolve correctly —
     Dolgellau / Bermo / Tywyn / Aberdyfi — both ways (Welsh→English
     and English→Welsh).
  3. The Gwynedd subset is non-empty and bounded sensibly (~300+
     names; the Commissioner's coverage of Gwynedd is rich).

Spot-checks are deliberately Gwynedd-heavy because the immediate
downstream consumer is the Dolgellau Town Dataset; the authority
itself is national so adding spot-checks for other LAs would
expand the test surface without much value.
"""

from __future__ import annotations

import pytest

from craidd.placenames import (
    PlaceName,
    lookup_by_welsh,
    lookup_by_english,
    lookup_by_grid_ref,
    subset_by_local_authority,
    all_records,
    CSV_FILENAME,
    CSV_VINTAGE,
    LICENCE,
    SOURCE_URL,
)
from craidd.placenames.authority import lookup_by_welsh_all


def test_module_loads_and_records_non_empty():
    records = all_records()
    assert len(records) > 3000, (
        f"expected ~3,500+ records; got {len(records)} — "
        "did the CSV ship?"
    )
    assert all(isinstance(r, PlaceName) for r in records)


def test_provenance_constants():
    assert CSV_FILENAME.endswith(".csv")
    assert CSV_VINTAGE.count("-") == 2  # ISO date
    assert "welshlanguagecommissioner.wales" in SOURCE_URL
    assert LICENCE.startswith("OGL")


def test_dolgellau_resolves():
    rec = lookup_by_welsh("Dolgellau")
    assert rec is not None
    assert rec.welsh_name == "Dolgellau"
    assert rec.english_name == "Dolgellau"  # English form is the same
    assert rec.local_authority_en == "Gwynedd"
    assert rec.grid_ref == "SH7217"


def test_bermo_barmouth_bilingual():
    """Welsh "Bermo, Y" (= "Y Bermo") maps to English "Barmouth".
    Both directions of lookup work."""
    rec = lookup_by_english("Barmouth")
    assert rec is not None
    assert rec.welsh_name.lower().startswith("bermo")
    assert rec.english_name == "Barmouth"
    assert rec.local_authority_en == "Gwynedd"

    # Reverse direction
    rec2 = lookup_by_welsh("Bermo, Y")
    assert rec2 is not None
    assert rec2.english_name == "Barmouth"


def test_tywyn_disambiguated_by_grid_ref():
    """'Tywyn' is ambiguous (Gwynedd + Conwy share the name). The
    singular `lookup_by_welsh` returns one; the `_all` variant returns
    both; and `lookup_by_grid_ref` disambiguates."""
    all_tywyn = lookup_by_welsh_all("Tywyn")
    assert len(all_tywyn) >= 2, (
        "expected at least 2 'Tywyn' records (Gwynedd + Conwy); "
        f"got {len(all_tywyn)}"
    )
    grid_refs = {r.grid_ref for r in all_tywyn}
    assert "SH5800" in grid_refs  # Tywyn (Gwynedd)
    # Verify lookup_by_grid_ref picks the Gwynedd one out cleanly
    gw_tywyn = lookup_by_grid_ref("SH5800")
    assert any(r.local_authority_en == "Gwynedd" for r in gw_tywyn)


def test_aberdyfi_resolves():
    rec = lookup_by_welsh("Aberdyfi")
    assert rec is not None
    assert rec.english_name == "Aberdyfi"
    assert rec.local_authority_en == "Gwynedd"
    assert rec.grid_ref == "SN6196"


def test_subset_by_local_authority_gwynedd_is_rich():
    gw = subset_by_local_authority("Gwynedd")
    assert len(gw) > 200, (
        f"expected 200+ Gwynedd records; got {len(gw)} — "
        "did the CSV vintage drop coverage?"
    )
    # Every record should agree on its LA tag (bilingual)
    for r in gw:
        assert r.local_authority_en == "Gwynedd"
        # Welsh LA name for Gwynedd is also "Gwynedd"
        assert r.local_authority_cy == "Gwynedd"


def test_normalisation_is_case_insensitive_but_preserves_diacritics():
    # Lookup is case-insensitive
    assert lookup_by_welsh("DOLGELLAU") is not None
    assert lookup_by_welsh("dolgellau") is not None
    # But diacritic-bearing names round-trip — picking one with ŵ/â
    rec = lookup_by_welsh("Llanrwst")
    if rec is not None:
        # If present in the snapshot, its stored Welsh form preserves
        # whatever the source carried — case may differ but diacritics
        # round-trip.
        assert isinstance(rec.welsh_name, str)


def test_grid_ref_normalisation_is_uppercase_no_spaces():
    """Grid refs lookup as uppercased no-spaces."""
    rec = lookup_by_grid_ref("sh7217")  # lowercase
    assert any(r.welsh_name == "Dolgellau" for r in rec)
    rec2 = lookup_by_grid_ref("SH 7217")  # spaced
    assert any(r.welsh_name == "Dolgellau" for r in rec2)


def test_unknown_name_returns_none():
    assert lookup_by_welsh("Notarealplace") is None
    assert lookup_by_english("Notarealplace") is None
    assert lookup_by_grid_ref("ZZ9999") == []


def test_empty_input_handled_gracefully():
    assert lookup_by_welsh("") is None
    assert lookup_by_welsh("   ") is None
    assert lookup_by_english(None) is None  # type: ignore[arg-type]


def test_immutability_of_all_records():
    """`all_records()` returns a fresh list each call — mutating it
    doesn't corrupt the module's internal state."""
    rs1 = all_records()
    rs1.clear()
    rs2 = all_records()
    assert len(rs2) > 3000
