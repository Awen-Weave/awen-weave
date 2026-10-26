"""CQC's own label for a hospice in the closed type domain: Huw's decision <SIG> (card c1910), separate from [sig:092052fa].

Scrutiny c1905, P1: adding a value to the closed care_establishment_type domain is a C9 ruling of its own. "Hospice" is
CQC's "Service types" value for the same service type HIW calls "Hospices"; nothing else is admitted.
"""
from __future__ import annotations

from craidd.schema.predicates import CARE_ESTABLISHMENT_TYPES
from craidd.schema.validation import validate_claim


def _ok(value):
    c = {"source_id": "src:cqc-test", "recorded_by": "lludd", "confidence": "high", "qualifiers": {},
         "subject_id": "care_establishment:cqc-1-129536667", "predicate": "care_establishment_type", "value_text": value}
    return validate_claim(c, subject_entity_type="care_establishment")


def test_the_domain_is_each_registers_own_label_for_a_hospice_and_nothing_else():
    assert CARE_ESTABLISHMENT_TYPES == ("Hospices", "Hospice")
    assert _ok("Hospice") == [] and _ok("Hospices") == []
    for other in ("Home hospice care", "Hospice services", "Homecare agencies"):
        assert _ok(other) != [], other
