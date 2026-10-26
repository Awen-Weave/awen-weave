"""Registered care establishments in England: constitution 0.1.12 in the grammar (card c1902).

Huw ruled 26/10/2026 [sig:092052fa]: the care_establishment definition names the Care Quality Commission beside HIW and
CIW (still not NHS bodies, still premises the public attends), and the key form gains `cqc-<location id>`, with the
paired awen-weave and registry key shapes. These tests hold the grammar's half:

  * a CQC key is `care_establishment:cqc-1-`, a digit 1-9, then eight to ten more digits: the location id as CQC
    publishes it, as every one of the 55,334 CQC-form location ids on the 22/10/2026 active directory is (observed on
    that one snapshot, not promised); nothing is minted for CQC;
  * every 0.1.11 key is still valid, and the reserved minted form cannot be written under cqc-.

Whether care_establishment_type admits CQC's own label "Hospice" is Huw's separate decision (scrutiny c1905, P1), and
its test lands only with that decision: tests/schema/test_care_establishment_cqc_type.py.
"""
from __future__ import annotations

import pytest

from craidd.schema.entity_types import ENTITY_TYPES
from craidd.schema.validation import ORG_SUBJECT_SHAPES, validate_claim, validate_entity

BASE = dict(source_id="src:cqc-test", recorded_by="lludd", confidence="high")
HOPE_HOUSE = "care_establishment:cqc-1-129536667"


def _ok(pred, subject=HOPE_HOUSE, **value):
    c = {**BASE, "subject_id": subject, "predicate": pred, "qualifiers": {}, **value}
    return validate_claim(c, subject_entity_type="care_establishment")


@pytest.mark.parametrize("subject,ok", [
    (HOPE_HOUSE, True), ("care_establishment:cqc-1-1000000000", True), ("care_establishment:cqc-1-10000000000", True),
    ("care_establishment:cqc-1-12345678", False), ("care_establishment:cqc-1-123456789012", False),
    ("care_establishment:cqc-1-0123456789", False), ("care_establishment:cqc-1-012345678", False),
    ("care_establishment:cqc-2-129536667", False), ("care_establishment:cqc-129536667", False),
    ("care_establishment:cqc-1129536667", False), ("care_establishment:CQC-1-129536667", False),
    ("care_establishment:cqc- 1-129536667", False), ("care_establishment:cqc-m0001", False),
    ("care_establishment:cqc-rx1", False), ("care_establishment:cqc-1-123", False),
    ("cqc-1-129536667", False), ("1-129536667", False),
])
def test_the_cqc_key_shape(subject, ok):
    assert bool(ORG_SUBJECT_SHAPES["care_establishment"].fullmatch(subject)) is ok
    assert (_ok("registered_name", subject, value_text="x") == []) is ok
    assert (validate_entity(subject, "care_establishment") == []) is ok


@pytest.mark.parametrize("subject", ["care_establishment:hiw-m0001", "care_establishment:hiw-m0011",
                                     "care_establishment:ciw-sin-00012345-abcd", "care_establishment:ciw-abc-00000001"])
def test_every_0_1_11_key_is_still_valid(subject):
    assert ORG_SUBJECT_SHAPES["care_establishment"].fullmatch(subject)


def test_a_bare_cqc_id_is_refused_with_its_reason():
    errs = _ok("registered_name", "1-129536667", value_text="x")
    assert errs and any("care_establishment:<register>-<id>" in e for e in errs), errs


def test_the_type_description_names_cqc():
    d = ENTITY_TYPES["care_establishment"]
    assert "CQC in England" in d and "HIW or CIW in Wales" in d
    for words in ("premises the public attends", "Not an NHS body", "Not a place", "private dwelling"):
        assert words in d, words
