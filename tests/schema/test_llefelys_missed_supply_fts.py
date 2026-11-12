"""The two Llefelys missed-supply predicates widened to Find a Tender: descriptions only (card c2410).

Huw ruled on 12/11/2026 to build a Find a Tender layer for Llefelys (AWE-011): a complement to Sell2Wales, not a
replacement, with one awen-weave release to widen these two predicates' descriptions. Row
REQ-arloesidolgellau-4c289e is countersigned [sig:4bf0aa58] for Procurement Act 2023 awards only (from 24/02/2025),
via the OCP Data Registry. Nothing else changes: same names, types, cardinality, subject kind and grain; still 297.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from craidd.schema.predicates import PREDICATE_REGISTRY, Grain

NAMES = ("public_contract_supplier_awards_count", "public_contract_award_value_gbp")
S2W = "April 2022 to March 2026, Sell2Wales via the OCP Data Registry"
FTS = "Procurement Act 2023 awards, Find a Tender via the OCP Data Registry"


@pytest.mark.parametrize("name", NAMES)
def test_each_names_both_sources_and_their_labels(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "Sell2Wales" in d and "Find a Tender" in d
    assert S2W in d and FTS in d
    assert "from 24/02/2025" in d and "Procurement Act 2023" in d


@pytest.mark.parametrize("name", NAMES)
def test_each_says_the_two_are_never_added_or_set_side_by_side(name):
    d = PREDICATE_REGISTRY[name].description_en
    assert "value_en names which source and range" in d
    assert "never added together or read as comparable" in d


def test_the_count_is_no_longer_sell2wales_only():
    d = PREDICATE_REGISTRY["public_contract_supplier_awards_count"].description_en
    assert not d.startswith("The number of Sell2Wales contract awards")
    assert d.startswith("The number of public contract awards to suppliers")


@pytest.mark.parametrize("name", NAMES)
def test_shape_and_rules_unchanged(name):
    p = PREDICATE_REGISTRY[name]
    assert (p.value_type, p.cardinality, p.applies_to_types, p.finest_grain) == ("int", "multi", ("area",), Grain.AREA)
    d = p.description_en
    assert "fewer than 5" in d and "no supplier is ever named" in d and "CPV" in d


def test_still_297_and_released_as_0_2_57():
    assert len(PREDICATE_REGISTRY) == 297
    meta = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text())
    assert meta["project"]["version"] == "0.2.57"
