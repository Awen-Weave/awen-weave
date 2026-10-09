"""Constitution 0.1.9 in the grammar: the `source_kind` predicate and its value check (awen-weave 0.2.26).

Ruled by Huw as Llys 02/10/2026 [sig:ca783ae5] on phase 4 task 4.1 (placement A, Llys 01/10/2026):

* `source_kind` is the ninth predicate on `source`. Its closed domain is NOT typed here: it is read
  from the vendored `SCH-ENTITY-001 $defs.source_kind` (constitution 0.1.9), so the grammar cannot
  drift from the constitution (proposal section 2.3).
* `validate_claim` refuses an off-domain `source_kind` value, for `source_kind` ONLY (decision 7):
  every other `constraint_json` (e.g. `listed_grade`) stays exactly as unenforced as before, and
  that general gap is measured separately. The refusal is awen-weave's, not the constitution's:
  Porth's `constitution_validate` accepts any value (Class A pass, N1).
* `description_cy` is CY_PENDING, never self-attested. Under the Llys ruling of 31/08/2026 that makes
  `source_kind` unemittable by a bilingual-parity instance (NWC-WLM-001) until attested (pass N3).

Seen to fail first: on 0.2.25 every test here fails at the first assertion (no `source_kind`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from craidd import CONSTITUTION_TAG, CONSTITUTION_VERSION
from craidd.schema.grain import Grain
from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, PredicateDef
from craidd.schema.validation import validate_claim

SIX = ["observation", "open-dataset", "cross-reference", "learning", "commercial", "proprietary"]
VENDORED_ENTITY = (Path(__file__).resolve().parents[2] / "src" / "craidd" / "constitution_vendor"
                   / "schema" / "entity.schema.json")


def _claim(value: str, predicate: str = "source_kind") -> dict:
    return {"subject_id": "source:x", "source_id": "source:x", "recorded_by": "t", "confidence": "high",
            "predicate": predicate, "value_text": value, "qualifiers": {}}


def test_the_package_pins_constitution_0_1_9():          # version-bound: retires at the next release
    assert CONSTITUTION_VERSION == "0.1.9"
    assert CONSTITUTION_TAG == "v0.1.9"


def test_the_vendored_entity_schema_carries_the_six():
    d = json.loads(VENDORED_ENTITY.read_text(encoding="utf-8"))["$defs"]["source_kind"]
    assert d["enum"] == SIX


def test_source_kind_is_a_single_text_predicate_on_source_only():
    p = PREDICATE_REGISTRY["source_kind"]
    assert (p.value_type, p.cardinality, p.applies_to_types) == ("text", "single", ("source",))
    assert p.finest_grain is Grain.NOT_SPATIAL
    assert p.description_cy == CY_PENDING          # never self-attested (N3)


def test_its_constraint_is_built_from_the_vendored_defs_not_typed():
    p = PREDICATE_REGISTRY["source_kind"]
    vendored = json.loads(VENDORED_ENTITY.read_text(encoding="utf-8"))["$defs"]["source_kind"]["enum"]
    assert json.loads(p.constraint_json) == {"enum": vendored}


@pytest.mark.parametrize("value", SIX)
def test_each_ruled_value_is_accepted(value):
    assert validate_claim(_claim(value), subject_entity_type="source") == []


@pytest.mark.parametrize("value", ["unknown", "Open-Dataset", "open dataset", "commons", ""])
def test_an_off_domain_value_is_refused(value):
    errors = validate_claim(_claim(value), subject_entity_type="source")
    assert errors, value
    if value:
        assert any("source_kind" in e and "not one of" in e for e in errors), errors


def test_the_check_reaches_source_kind_only_listed_grade_stays_as_it_was():
    """Decision 7. listed_grade declares {"enum": ["I","II*","II"]} and is still not enforced."""
    p = PREDICATE_REGISTRY["listed_grade"]
    assert json.loads(p.constraint_json)["enum"] == ["I", "II*", "II"]
    errors = validate_claim(_claim("III", "listed_grade"), subject_entity_type=p.applies_to_types[0])
    assert not any("not one of" in e for e in errors), errors


def test_the_check_reads_the_predicates_own_constraint_so_a_registry_override_is_honoured():
    """The value check uses the PredicateDef's constraint_json, not a second hard-coded list."""
    base = PREDICATE_REGISTRY["source_kind"]
    narrowed = PredicateDef(base.name, base.value_type, base.cardinality, base.applies_to_types,
                            base.description_en, base.description_cy, base.required_qualifiers,
                            json.dumps({"enum": ["observation"]}), base.finest_grain)
    reg = {**PREDICATE_REGISTRY, "source_kind": narrowed}
    assert validate_claim(_claim("observation"), subject_entity_type="source", predicate_registry=reg) == []
    assert validate_claim(_claim("learning"), subject_entity_type="source", predicate_registry=reg)


def test_the_registry_count_moves_by_exactly_one():
    # 144 at 0.2.24/0.2.25, + source_kind (0.1.9) = 145; + the 3 Welsh Government allowance predicates
    # (0.2.27, [sig:dc82671f], none of them on `source`) = 148. The `source` list below is what pins
    # that source_kind moved the `source` set by exactly one.
    # + the 8 Open Evidence predicates (0.2.28, [sig:a40a1dcd], none on `source`) = 156.
    # + the 3 Lludd dialysis predicates (0.2.29, [sig:75935d1b], none on `source`) = 159.
    assert len(PREDICATE_REGISTRY) == 161
    assert sorted(n for n, p in PREDICATE_REGISTRY.items() if p.applies_to_types == ("source",)) == sorted(
        ["title_cy", "title_en", "citation", "url", "organisation", "licence", "accessed_at", "file_hash",
         "source_kind"])
