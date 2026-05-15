"""
src/craidd/schema/validation.py — the Craidd validation contract.

The pure-function validation layer (architecture.md §6.2). Every write
path runs through these functions; they take plain data in and return
lists of human-readable error strings — an empty list means valid. They
never touch a database, a file, or the network: callers (the Write API,
craidd-init) supply everything needed, including the subject entity's
type and any existing-claim context for cardinality checks.

These functions validate CLAIM-TABLE-shaped data (design/v0.1-schema.md
§3.2) — subject_id, predicate, the typed value_* columns, qualifiers,
source_id, recorded_by, confidence, status. The looser v0 proposal
format (client/craidd_client.py) is mapped onto this shape by the write
path before validation.

Source of truth for the rules: design/v0.1-schema.md.
"""
from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import Any

from .entity_types import VALID_ENTITY_TYPES
from .predicates import (
    PredicateDef,
    PREDICATE_REGISTRY,
    SEED_PREDICATES,
    VALUE_TYPES,
    CARDINALITIES,
)
from .qualifiers import QUALIFIER_KEYS, CLOSED_QUALIFIER_DOMAINS


# Confidence levels permitted on a claim (design/v0.1-schema.md §3.2 DDL).
VALID_CONFIDENCES: frozenset[str] = frozenset({"high", "medium", "low"})

# Claim lifecycle statuses (design/v0.1-schema.md §3.2 DDL).
VALID_CLAIM_STATUSES: frozenset[str] = frozenset(
    {"active", "superseded", "disputed", "withdrawn"}
)

# Entity visibility values (design/v0.1-schema.md §3.1).
VALID_VISIBILITIES: frozenset[str] = frozenset(
    {"public", "restricted", "private"}
)

# value_type -> the claim column(s) that must carry the value. For
# 'bilingual', at least one of the pair must be populated; for 'date',
# value_date is required and value_date_text is an optional companion.
_VALUE_COLUMNS: dict[str, tuple[str, ...]] = {
    "text": ("value_text",),
    "int": ("value_int",),
    "real": ("value_real",),
    "date": ("value_date",),
    "geom": ("value_geom",),
    "bilingual": ("value_cy", "value_en"),
    "entity_ref": ("value_entity_ref",),
}


def _is_empty(value: Any) -> bool:
    """True if a value is absent — None, or an empty/whitespace string."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def validate_predicate_def(pred: PredicateDef) -> list[str]:
    """Validate that a predicate definition is itself well-formed. Used
    by craidd-init to check the seed set before writing it to the
    registry."""
    errors: list[str] = []
    if _is_empty(pred.name):
        errors.append("predicate name is empty")
    if pred.value_type not in VALUE_TYPES:
        errors.append(
            f"predicate '{pred.name}': value_type '{pred.value_type}' is not "
            f"one of {sorted(VALUE_TYPES)}"
        )
    if pred.cardinality not in CARDINALITIES:
        errors.append(
            f"predicate '{pred.name}': cardinality '{pred.cardinality}' is "
            f"not one of {sorted(CARDINALITIES)}"
        )
    if not pred.applies_to_types:
        errors.append(f"predicate '{pred.name}': applies_to_types is empty")
    for t in pred.applies_to_types:
        if t not in VALID_ENTITY_TYPES:
            errors.append(
                f"predicate '{pred.name}': applies_to type '{t}' is not a "
                f"valid entity type"
            )
    for q in pred.required_qualifiers:
        if q not in QUALIFIER_KEYS:
            errors.append(
                f"predicate '{pred.name}': required qualifier '{q}' is not a "
                f"known qualifier key"
            )
    if _is_empty(pred.description_en):
        errors.append(f"predicate '{pred.name}': description_en is empty")
    if _is_empty(pred.description_cy):
        errors.append(f"predicate '{pred.name}': description_cy is empty")
    if pred.constraint_json is not None:
        try:
            json.loads(pred.constraint_json)
        except (ValueError, TypeError) as exc:
            errors.append(
                f"predicate '{pred.name}': constraint_json is not valid JSON "
                f"({exc})"
            )
    return errors


def validate_seed_predicates() -> list[str]:
    """Validate every predicate in SEED_PREDICATES. craidd-init calls this
    before bootstrapping the registry — a non-empty result means the seed
    set itself is malformed and bootstrap must not proceed."""
    errors: list[str] = []
    for pred in SEED_PREDICATES:
        errors.extend(validate_predicate_def(pred))
    return errors


def validate_entity(
    entity_id: str,
    entity_type: str,
    visibility: str | None = None,
) -> list[str]:
    """Validate an entity's core fields (design/v0.1-schema.md §3.1, §3.4)."""
    errors: list[str] = []
    if _is_empty(entity_id):
        errors.append("entity_id is empty")
    if entity_type not in VALID_ENTITY_TYPES:
        errors.append(
            f"entity '{entity_id}': entity_type '{entity_type}' is not one "
            f"of {sorted(VALID_ENTITY_TYPES)}"
        )
    if visibility is not None:
        if visibility not in VALID_VISIBILITIES:
            errors.append(
                f"entity '{entity_id}': visibility '{visibility}' is not one "
                f"of {sorted(VALID_VISIBILITIES)}"
            )
        if entity_type != "source":
            errors.append(
                f"entity '{entity_id}': visibility is only meaningful for "
                f"source entities (this is a '{entity_type}')"
            )
    return errors


def validate_qualifiers(
    qualifiers: Mapping[str, Any],
    pred: PredicateDef,
) -> list[str]:
    """Validate a claim's qualifiers against a predicate's requirements
    and the §3.2 qualifier vocabulary. `qualifiers` is the parsed mapping
    (the write path parses claim.qualifiers_json before calling)."""
    errors: list[str] = []
    # required qualifiers must all be present and non-empty
    for required in pred.required_qualifiers:
        if required not in qualifiers or _is_empty(qualifiers.get(required)):
            errors.append(
                f"predicate '{pred.name}' requires the '{required}' qualifier"
            )
    # every supplied qualifier key must be known; closed-domain values
    # must be in their domain (open-domain values are not rejected)
    for key, value in qualifiers.items():
        if key not in QUALIFIER_KEYS:
            errors.append(f"unknown qualifier key '{key}'")
            continue
        domain = CLOSED_QUALIFIER_DOMAINS.get(key)
        if domain is not None and value not in domain:
            errors.append(
                f"qualifier '{key}' value '{value}' is not one of "
                f"{sorted(domain)}"
            )
    return errors


def validate_claim(
    claim: Mapping[str, Any],
    *,
    subject_entity_type: str,
    predicate_registry: Mapping[str, PredicateDef] = PREDICATE_REGISTRY,
    deprecated_predicates: Collection[str] = (),
    existing_active_predicates: Collection[str] = (),
) -> list[str]:
    """Validate a single claim against the schema. Returns a list of
    error strings — an empty list means the claim is valid.

    Pure function. The caller (the Write API) supplies everything needed:

      subject_entity_type         entity_type of the claim's subject, so
                                  the predicate's applies_to can be checked
      predicate_registry          name -> PredicateDef. Defaults to the
                                  seed registry; the live Write API passes
                                  the registry loaded from the DB
      deprecated_predicates       predicate names currently deprecated —
                                  new claims using one are rejected
      existing_active_predicates  predicate names that already have an
                                  active, conflicting claim on this
                                  subject, for single-cardinality checks

    `claim` is a mapping keyed by the claim-table column names
    (design/v0.1-schema.md §3.2). `claim['qualifiers']` is the parsed
    qualifiers mapping (not the raw qualifiers_json string).
    """
    errors: list[str] = []

    # --- required structural fields -------------------------------------
    if _is_empty(claim.get("subject_id")):
        errors.append("claim has no subject_id")
    if _is_empty(claim.get("source_id")):
        errors.append("claim has no source_id")
    if _is_empty(claim.get("recorded_by")):
        errors.append("claim has no recorded_by")

    confidence = claim.get("confidence")
    if confidence not in VALID_CONFIDENCES:
        errors.append(
            f"confidence '{confidence}' is not one of "
            f"{sorted(VALID_CONFIDENCES)}"
        )

    status = claim.get("status")
    if status is not None and status not in VALID_CLAIM_STATUSES:
        errors.append(
            f"status '{status}' is not one of {sorted(VALID_CLAIM_STATUSES)}"
        )

    # --- predicate resolution -------------------------------------------
    predicate_name = claim.get("predicate")
    if _is_empty(predicate_name):
        errors.append("claim has no predicate")
        return errors  # nothing further is checkable without a predicate
    pred = predicate_registry.get(predicate_name)
    if pred is None:
        errors.append(f"unknown predicate '{predicate_name}'")
        return errors  # nothing further is checkable without the definition

    if predicate_name in deprecated_predicates:
        errors.append(
            f"predicate '{predicate_name}' is deprecated; new claims using "
            f"it are rejected"
        )

    # --- applies_to ------------------------------------------------------
    if subject_entity_type not in pred.applies_to_types:
        errors.append(
            f"predicate '{predicate_name}' does not apply to entity type "
            f"'{subject_entity_type}' (applies to: "
            f"{', '.join(pred.applies_to_types)})"
        )

    # --- value placement -------------------------------------------------
    columns = _VALUE_COLUMNS.get(pred.value_type, ())
    has_value = any(not _is_empty(claim.get(col)) for col in columns)
    if not has_value:
        if pred.value_type == "bilingual":
            errors.append(
                f"predicate '{predicate_name}' is bilingual: at least one of "
                f"value_cy / value_en must be set"
            )
        else:
            errors.append(
                f"predicate '{predicate_name}' expects a {pred.value_type} "
                f"value in {columns[0] if columns else '(unknown column)'}, "
                f"but it is empty"
            )

    # --- qualifiers ------------------------------------------------------
    qualifiers = claim.get("qualifiers") or {}
    if not isinstance(qualifiers, Mapping):
        errors.append("claim 'qualifiers' must be a mapping")
    else:
        errors.extend(validate_qualifiers(qualifiers, pred))

    # --- cardinality -----------------------------------------------------
    if (
        pred.cardinality == "single"
        and predicate_name in existing_active_predicates
    ):
        errors.append(
            f"predicate '{predicate_name}' is single-cardinality and the "
            f"subject already has an active claim on it — supersede the "
            f"existing claim rather than adding a second"
        )

    return errors


# --- proposal validation -----------------------------------------------------
# A proposal (client/craidd_client.py format) is the looser pre-claim
# shape: it carries a single untyped `value` and may identify its subject
# by `subject_hint` rather than a resolved entity_id. validate_proposal
# checks the subset of the claim contract decidable WITHOUT the database —
# predicate registry membership and deprecation, value typing, qualifiers,
# confidence, source shape, subject identification. The checks that need
# the live store — resolving subject_hint to an entity, the predicate's
# applies_to against that entity's type, and single-cardinality conflicts
# — are deliberately deferred to craidd-review. A clean validate_proposal
# result means a proposal is well formed enough to enter the queue; it is
# never a guarantee of acceptance.

def _proposal_value_errors(value: Any, pred: PredicateDef) -> list[str]:
    """Check a proposal's untyped `value` against its predicate's
    value_type. Partial by design: it confirms the Python type is
    consistent, but does not deeply parse dates or geometry — that
    resolves when craidd-review maps the value into the typed claim
    columns."""
    vt = pred.value_type
    name = pred.name

    if vt == "bilingual":
        if not isinstance(value, Mapping):
            return [
                f"predicate '{name}' is bilingual: value must be a mapping "
                f"with 'cy' and/or 'en' keys"
            ]
        if _is_empty(value.get("cy")) and _is_empty(value.get("en")):
            return [
                f"predicate '{name}' is bilingual: at least one of 'cy' / "
                f"'en' must be set"
            ]
        return []

    if _is_empty(value):
        return [f"predicate '{name}' expects a {vt} value, but it is empty"]

    if vt == "text":
        ok = isinstance(value, str)
    elif vt == "int":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif vt == "real":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif vt in ("date", "geom", "entity_ref"):
        # date precision (precise vs value_date_text) and geometry parsing
        # resolve at review; here we only require a non-empty string.
        ok = isinstance(value, str)
    else:
        ok = False

    if not ok:
        return [
            f"predicate '{name}' expects a {vt} value, got "
            f"{type(value).__name__}"
        ]
    return []


def validate_proposal(
    proposal: Mapping[str, Any],
    *,
    predicate_registry: Mapping[str, PredicateDef] = PREDICATE_REGISTRY,
    deprecated_predicates: Collection[str] = (),
) -> list[str]:
    """Validate a proposal (the looser pre-claim format) against the
    subset of the schema contract decidable without the database. Returns
    a list of error strings — an empty list means the proposal is well
    formed enough to enter the queue.

    Pure function. `proposal` is a mapping in the client/craidd_client.py
    proposal format: submitter, subject / subject_hint, predicate, value,
    source, confidence, and an optional qualifiers mapping.

    What this does NOT check (deferred to craidd-review against the live
    store): resolution of subject_hint to a real entity, the predicate's
    applies_to against that entity's type, and single-cardinality
    conflicts with existing active claims.
    """
    errors: list[str] = []

    # --- submitter -------------------------------------------------------
    if _is_empty(proposal.get("submitter")):
        errors.append("proposal has no submitter")

    # --- subject identification -----------------------------------------
    subject = proposal.get("subject")
    subject_hint = proposal.get("subject_hint")
    has_subject = not _is_empty(subject)
    has_hint = isinstance(subject_hint, Mapping) and len(subject_hint) > 0
    if subject_hint is not None and not isinstance(subject_hint, Mapping):
        errors.append("proposal 'subject_hint' must be a mapping")
    if not has_subject and not has_hint:
        errors.append(
            "proposal must identify its subject — either 'subject' (an "
            "entity_id) or a non-empty 'subject_hint' mapping"
        )

    # --- confidence ------------------------------------------------------
    confidence = proposal.get("confidence")
    if confidence not in VALID_CONFIDENCES:
        errors.append(
            f"confidence '{confidence}' is not one of "
            f"{sorted(VALID_CONFIDENCES)}"
        )

    # --- source ----------------------------------------------------------
    source = proposal.get("source")
    if not isinstance(source, Mapping) or _is_empty(source.get("id")):
        errors.append(
            "proposal 'source' must be a mapping including a non-empty 'id'"
        )

    # --- predicate resolution -------------------------------------------
    predicate_name = proposal.get("predicate")
    if _is_empty(predicate_name):
        errors.append("proposal has no predicate")
        return errors  # nothing further is checkable without a predicate
    pred = predicate_registry.get(predicate_name)
    if pred is None:
        errors.append(f"unknown predicate '{predicate_name}'")
        return errors  # nothing further is checkable without the definition

    if predicate_name in deprecated_predicates:
        errors.append(
            f"predicate '{predicate_name}' is deprecated; new proposals "
            f"using it are rejected"
        )

    # --- value -----------------------------------------------------------
    errors.extend(_proposal_value_errors(proposal.get("value"), pred))

    # --- qualifiers ------------------------------------------------------
    qualifiers = proposal.get("qualifiers") or {}
    if not isinstance(qualifiers, Mapping):
        errors.append("proposal 'qualifiers' must be a mapping")
    else:
        errors.extend(validate_qualifiers(qualifiers, pred))

    return errors
