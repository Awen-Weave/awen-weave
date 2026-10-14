"""nhs_org_role gains 'service' (awen-weave 0.2.40, PROPOSED).

Ruled by Huw as Llys 14/10/2026 [sig:81e81fa4], option B of PROPOSAL-nhs-org-service-role-2026-10-14.md
(awen-shared#820, card c1029). Huw's reading: SCH-ENTITY-001's nhs_org means an NHS organisation
identified by its ODS code; GP practice, site and health board are examples, not an exhaustive list. So
the closed role list widens in awen-weave alone, through the one gate, with no constitution change.

A service is an NHS body with its own ODS code that delivers care but holds no registered patient list.
It is never a GP practice and is never counted as one.

WHERE PRACTICES ARE COUNTED. Nothing in awen-weave counts practices: the grammar only states what a
role may be. Counts are made by the producers and consumers (Lludd's builders, the catalogue module that
will emit services, a consumer's read-back), and each must filter on nhs_org_role = gp-practice. This file
holds the grammar's half: 'service' is its own value, distinct from 'gp-practice', so a filter on the
practice role can never take a service in.
"""
from __future__ import annotations

import json

import pytest

from craidd.schema.predicates import NHS_ORG_ROLES, PREDICATE_REGISTRY
from craidd.schema.validation import VALUE_CHECKED_PREDICATES, validate_claim


def _errors(value: str) -> list:
    claim = {"subject_id": "nhs_org:W00190", "predicate": "nhs_org_role", "value_text": value,
             "source_id": "ods-epraccur", "recorded_by": "test@example.org", "confidence": "high",
             "qualifiers": {"binding": "asserted"}}
    return validate_claim(claim, subject_entity_type="nhs_org")


def test_service_is_a_role():
    assert "service" in NHS_ORG_ROLES
    assert json.loads(PREDICATE_REGISTRY["nhs_org_role"].constraint_json) == {"enum": list(NHS_ORG_ROLES)}


def test_a_service_role_is_accepted():
    assert _errors("service") == []


@pytest.mark.parametrize("bad", ["services", "Service", "urgent-care", "practice", ""])
def test_an_unknown_role_is_still_refused(bad):
    assert _errors(bad), bad


def test_the_list_is_the_three_ruled_13_10_plus_service_and_nothing_else():
    assert NHS_ORG_ROLES == ("gp-practice", "site", "health-board", "service")
    assert "nhs_org_role" in VALUE_CHECKED_PREDICATES


def test_a_service_is_never_a_practice():
    """The grammar's half of 'never counted as practices': service and gp-practice are distinct values,
    so a count filtered on gp-practice cannot include a service."""
    roles = set(NHS_ORG_ROLES)
    assert "service" in roles and "gp-practice" in roles and "service" != "gp-practice"
    d = PREDICATE_REGISTRY["nhs_org_role"].description_en
    assert "service (an NHS body with its own ODS code that delivers care but holds no registered " \
           "patient list" in d
    assert "never counted as a GP practice" in d


def test_the_rest_of_the_predicate_is_unchanged():
    p = PREDICATE_REGISTRY["nhs_org_role"]
    assert (p.value_type, p.cardinality, p.applies_to_types) == ("text", "single", ("nhs_org",))
    assert p.required_qualifiers == ()
