"""
src/craidd/schema — the Craidd schema layer (architecture.md §6.2).

Pure logic: the controlled vocabularies (entity types, predicates,
qualifiers) and the validation contract that every write path runs
against. No I/O, no DB access, no auth — pure functions over plain data.

The storage layer's DDL (src/craidd/storage/) mirrors these vocabularies;
when one changes the other must change in the same commit, per
architecture.md §4 boundary 4.

Source of truth: design/v0.1-schema.md.
"""
from __future__ import annotations

from .entity_types import ENTITY_TYPES, VALID_ENTITY_TYPES, is_valid_entity_type
from .qualifiers import (
    DEFAULT_DIALECT,
    QUALIFIER_KEYS,
    NAME_TYPES,
    DATE_PRECISIONS,
    KNOWN_DIALECTS,
    KNOWN_FLOOR_SCOPES,
    CLOSED_QUALIFIER_DOMAINS,
    OPEN_QUALIFIER_DOMAINS,
)
from .predicates import (
    PredicateDef,
    SEED_PREDICATES,
    PREDICATE_REGISTRY,
    VALUE_TYPES,
    CARDINALITIES,
    CY_PENDING,
)
from .validation import (
    validate_predicate_def,
    validate_seed_predicates,
    validate_entity,
    validate_qualifiers,
    validate_claim,
    VALID_CONFIDENCES,
    VALID_CLAIM_STATUSES,
    VALID_VISIBILITIES,
)

__all__ = [
    # entity types
    "ENTITY_TYPES",
    "VALID_ENTITY_TYPES",
    "is_valid_entity_type",
    # qualifiers
    "DEFAULT_DIALECT",
    "QUALIFIER_KEYS",
    "NAME_TYPES",
    "DATE_PRECISIONS",
    "KNOWN_DIALECTS",
    "KNOWN_FLOOR_SCOPES",
    "CLOSED_QUALIFIER_DOMAINS",
    "OPEN_QUALIFIER_DOMAINS",
    # predicates
    "PredicateDef",
    "SEED_PREDICATES",
    "PREDICATE_REGISTRY",
    "VALUE_TYPES",
    "CARDINALITIES",
    "CY_PENDING",
    # validation contract
    "validate_predicate_def",
    "validate_seed_predicates",
    "validate_entity",
    "validate_qualifiers",
    "validate_claim",
    "VALID_CONFIDENCES",
    "VALID_CLAIM_STATUSES",
    "VALID_VISIBILITIES",
]
