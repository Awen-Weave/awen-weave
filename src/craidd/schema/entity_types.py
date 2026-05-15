"""
Controlled vocabulary for entity.entity_type — the nine v0.1 entity types.

Source of truth: design/v0.1-schema.md §3.4. The DDL CHECK constraint in
src/craidd/storage/ mirrors VALID_ENTITY_TYPES exactly — keep the two in
sync, per architecture.md §4 boundary 4.

Note (from v0.1-schema.md §3.4): `street` and `area` are valid entity
types but have no dedicated predicates in the §3.5 seed set yet, and
`person` is declared but deliberately not pre-populated — people enter
the Craidd only as the answers to specific research questions.
"""
from __future__ import annotations

# entity_type -> one-line purpose (from design/v0.1-schema.md §3.4).
ENTITY_TYPES: dict[str, str] = {
    "building": "A physical building or substantial structure.",
    "street": "A named street or street segment.",
    "area": "A bounded area — conservation area, ward, parish.",
    "town": "The town as a whole subject (a single instance in v1).",
    "tenancy": "An occupancy of a building (or floor) by a tenant over a period.",
    "event": "A dated thing that happened — designation, refurbishment, sale, fire.",
    "research_question": "A known-unknown the dataset is actively tracking.",
    "source": "A citation. Carries a visibility setting.",
    "person": "A named individual relevant to a building's history.",
}

# The set used for fast membership checks and by the validation contract.
VALID_ENTITY_TYPES: frozenset[str] = frozenset(ENTITY_TYPES)


def is_valid_entity_type(entity_type: str) -> bool:
    """True if entity_type is one of the nine v0.1 controlled types."""
    return entity_type in VALID_ENTITY_TYPES
