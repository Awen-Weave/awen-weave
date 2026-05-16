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
import re
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

# Known schemes for entity_proposal.entity.external_refs[].scheme. Per
# design/entity-proposal-shape.md §12.c (resolved 2026-05-16). Lives here
# alongside the other validation-layer constants — it's an entity-reference
# scheme registry, not a qualifier domain. Extensible for v0.3.
KNOWN_EXTERNAL_REF_SCHEMES: frozenset[str] = frozenset(
    {"uprn", "toid", "cadw", "blb", "nhle", "osm-id"}
)

# Proposal ID regexes for the entity-proposal-shape.md formats:
#   EP-<YYYYMMDD>-<HHMM>-<8 hex chars>  for entity proposals
#   B-<YYYYMMDD>-<HHMM>-<8 hex chars>   for bundles
# Both shared by validate_proposal (for bundle_id checks on claim proposals)
# and validate_entity_proposal. The corresponding claim-proposal id format
# (P-<YYYYMMDD-HHMMSS>-<8 hex>, deliberately a different shape because claim
# proposals can be created at sub-minute cadence) lives in
# client/craidd_client.py::_new_proposal_id.
_EP_ID_RE = re.compile(r"^EP-\d{8}-\d{4}-[0-9a-fA-F]{8}$")
_BUNDLE_ID_RE = re.compile(r"^B-\d{8}-\d{4}-[0-9a-fA-F]{8}$")

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


def _validate_iso_date(value: Any) -> str | None:
    """Return an error message if `value` is not a parseable ISO date /
    datetime string, otherwise None. Accepts both date (`YYYY-MM-DD`) and
    datetime (`YYYY-MM-DDTHH:MM:SS[+TZ]`) forms — Python's fromisoformat
    handles both on 3.11+, and on earlier versions we strip a trailing 'Z'
    for compatibility with curator-supplied timestamps."""
    if not isinstance(value, str) or not value:
        return "must be a non-empty ISO-8601 date or datetime string"
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        # date.fromisoformat would reject a datetime; try datetime first,
        # fall back to date.
        from datetime import datetime, date  # noqa: PLC0415 — lazy import
        try:
            datetime.fromisoformat(candidate)
        except ValueError:
            date.fromisoformat(candidate)
    except ValueError as exc:
        return f"is not a valid ISO-8601 date/datetime ({exc})"
    return None


def validate_qualifiers(
    qualifiers: Mapping[str, Any],
    pred: PredicateDef | None = None,
) -> list[str]:
    """Validate a claim's qualifiers against the §3.2 vocabulary plus the
    §10 item 7 additions, optionally checking predicate-required keys.

    `qualifiers` is the parsed mapping (the write path parses
    claim.qualifiers_json before calling). `pred` is optional — entity
    proposals carry qualifiers without a single owning predicate, and pass
    `pred=None` so the required-qualifier check is skipped.

    Checks applied:
      - required qualifiers from `pred.required_qualifiers` are present
        (only when `pred` is supplied);
      - every supplied qualifier key is in QUALIFIER_KEYS;
      - closed-domain values are in their domain (open-domain values are
        not rejected);
      - open-form item-7 keys with type/format expectations are checked:
        `verified_at` parses as ISO-8601; `cache_snapshot_id`,
        `field_session_id`, `co_signed_by` are non-empty strings;
      - cross-qualifier rule (design/lleolydd.md §12.A): `co_signed_by`
        requires `field_session_id` in the same qualifier set — co-sign
        is a synchronous acceptance path that needs a named session.
    """
    errors: list[str] = []
    # required qualifiers must all be present and non-empty
    if pred is not None:
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
            continue
        # Open-form item-7 keys with type/format expectations.
        if key == "verified_at":
            err = _validate_iso_date(value)
            if err is not None:
                errors.append(f"qualifier 'verified_at' {err}")
        elif key in ("cache_snapshot_id", "field_session_id", "co_signed_by"):
            if not isinstance(value, str) or _is_empty(value):
                errors.append(
                    f"qualifier '{key}' must be a non-empty string"
                )

    # Cross-qualifier rule: co_signed_by requires field_session_id.
    # Applies to claims AND to proposals (validate_entity_proposal and
    # validate_proposal both delegate here). Fires once per qualifier set
    # regardless of the iteration above.
    if "co_signed_by" in qualifiers and "field_session_id" not in qualifiers:
        errors.append(
            "qualifier 'co_signed_by' requires 'field_session_id' in the "
            "same qualifier set — co-sign requires a named session "
            "(design/lleolydd.md §12.A)"
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

    # --- bundle membership (optional) -----------------------------------
    # When a claim proposal is part of a bundle (entity-proposal-shape.md
    # §4), it carries bundle_id and may use subject_hint == "<bundle>"
    # as a deferred-subject sentinel — the bundled entity proposal hasn't
    # been accepted yet, so its entity_id doesn't exist. craidd-review
    # resolves the sentinel to the just-created entity_id at accept-time.
    bundle_id = proposal.get("bundle_id")
    if bundle_id is not None:
        if not isinstance(bundle_id, str) or not _BUNDLE_ID_RE.match(bundle_id):
            errors.append(
                f"proposal bundle_id {bundle_id!r} must match B-<YYYYMMDD>-"
                f"<HHMM>-<8-hex>"
            )

    # --- subject identification -----------------------------------------
    subject = proposal.get("subject")
    subject_hint = proposal.get("subject_hint")
    has_subject = not _is_empty(subject)
    # Bundle-member sentinel: subject_hint == "<bundle>" is valid iff
    # bundle_id is also present and validates above.
    is_bundle_sentinel = (
        isinstance(subject_hint, str) and subject_hint == "<bundle>"
        and bundle_id is not None
    )
    has_hint = (
        is_bundle_sentinel
        or (isinstance(subject_hint, Mapping) and len(subject_hint) > 0)
    )
    if (
        subject_hint is not None
        and not isinstance(subject_hint, Mapping)
        and not is_bundle_sentinel
    ):
        errors.append(
            "proposal 'subject_hint' must be a mapping (or the bundle "
            "sentinel '<bundle>' when bundle_id is present)"
        )
    if not has_subject and not has_hint:
        errors.append(
            "proposal must identify its subject — either 'subject' (an "
            "entity_id), a non-empty 'subject_hint' mapping, or "
            "subject_hint='<bundle>' alongside a valid bundle_id"
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


# --- claim-columns -> proposal value -----------------------------------------
# A claim (design/v0.1-schema.md §3.2) carries its value spread across
# type-tagged columns (value_text, value_int, value_real, value_date,
# value_date_text, value_geom, value_cy, value_en, value_entity_ref). A
# proposal carries a single untyped `value`. value_from_claim_columns
# collapses the former into the latter — the inverse of how the Write API
# will later spread a proposal's value back across the columns. It is the
# core of the BRA -> proposal-queue adapter (design/bra-proposal-handoff.md).

_ALL_VALUE_COLUMNS: tuple[str, ...] = (
    "value_text", "value_int", "value_real", "value_date",
    "value_date_text", "value_geom", "value_cy", "value_en",
    "value_entity_ref",
)


def value_from_claim_columns(
    claim: Mapping[str, Any], pred: PredicateDef
) -> tuple[Any, list[str]]:
    """Collapse a claim's type-tagged value_* columns into the single
    `value` the proposal format carries.

    Returns (value, errors). A non-empty errors list means the columns
    were inconsistent with the predicate's value_type — nothing populated
    where a value is required, or a column for a different type populated.
    When errors is non-empty the returned value is best-effort and should
    not be trusted.

    Pure function. The caller supplies the predicate so the value_type is
    known; `claim` is a mapping keyed by claim-table column names.
    """
    errors: list[str] = []
    vt = pred.value_type

    # which columns this value_type legitimately uses
    if vt == "date":
        expected = {"value_date", "value_date_text"}
    else:
        expected = set(_VALUE_COLUMNS.get(vt, ()))

    # any value column populated outside the expected set is a mismatch
    populated = {
        col for col in _ALL_VALUE_COLUMNS if not _is_empty(claim.get(col))
    }
    stray = populated - expected
    if stray:
        errors.append(
            f"predicate '{pred.name}' is {vt}, but value column(s) "
            f"{', '.join(sorted(stray))} are populated"
        )

    # extract the value in the shape the proposal format expects
    if vt == "bilingual":
        value: dict[str, Any] = {}
        if not _is_empty(claim.get("value_cy")):
            value["cy"] = claim["value_cy"]
        if not _is_empty(claim.get("value_en")):
            value["en"] = claim["value_en"]
        if not value:
            errors.append(
                f"predicate '{pred.name}' is bilingual, but neither "
                f"value_cy nor value_en is set"
            )
        return value, errors

    if vt == "date":
        # v0.1's hybrid date: prefer the precise value_date, fall back to
        # the free-text value_date_text (date_precision lives on a qualifier).
        v = claim.get("value_date")
        if _is_empty(v):
            v = claim.get("value_date_text")
        if _is_empty(v):
            errors.append(
                f"predicate '{pred.name}' is date, but neither value_date "
                f"nor value_date_text is set"
            )
            return None, errors
        return v, errors

    columns = _VALUE_COLUMNS.get(vt, ())
    column = columns[0] if columns else None
    v = claim.get(column) if column else None
    if _is_empty(v):
        errors.append(
            f"predicate '{pred.name}' expects a {vt} value in "
            f"{column or '(unknown column)'}, but it is empty"
        )
        return None, errors
    return v, errors


# --- entity_proposal validation ------------------------------------------------
# The entity_proposal shape (design/entity-proposal-shape.md) is a second
# proposal type alongside claim proposals. It carries an entity-creation
# request rather than a single new claim; craidd-review composes it with
# bundled claim proposals (same bundle_id) on acceptance.
#
# validate_entity_proposal is the schema-layer pure-function counterpart
# of validate_proposal — it checks everything decidable without the live
# store. Collision detection (external_refs against existing entities),
# bundle-member consistency, and curator-identity checks are deferred to
# craidd-review.
#
# _EP_ID_RE and _BUNDLE_ID_RE are defined at module scope above (next to
# the other validation-layer constants) so validate_proposal can also use
# _BUNDLE_ID_RE for bundle-member claim proposals.

# Per-scheme value-shape sanity checks for external_refs. Strictly cheap
# pattern matches — not real-world validity. UPRN is 12 digits per OS;
# TOID is 'osgb' + digits; Cadw / BLB / NHLE / osm-id are numeric strings.
_EXTERNAL_REF_PATTERNS: dict[str, "re.Pattern[str]"] = {
    "uprn": re.compile(r"^\d{12}$"),
    "toid": re.compile(r"^osgb\d+$"),
    "cadw": re.compile(r"^\d+$"),
    "blb": re.compile(r"^\d+$"),
    "nhle": re.compile(r"^\d+$"),
    "osm-id": re.compile(r"^\d+$"),
}


def _check_name_entry(idx: int, entry: Any) -> list[str]:
    """Validate one entry in entity.names. Returns a list of error strings
    prefixed with the entry's index."""
    errors: list[str] = []
    prefix = f"entity.names[{idx}]"
    if not isinstance(entry, Mapping):
        return [f"{prefix} must be a mapping"]
    language = entry.get("language")
    if language not in ("cy", "en"):
        errors.append(
            f"{prefix}: language must be 'cy' or 'en', got {language!r}"
        )
    from .qualifiers import NAME_TYPES  # local import to avoid cycle hazard
    name_type = entry.get("name_type")
    if name_type not in NAME_TYPES:
        errors.append(
            f"{prefix}: name_type {name_type!r} is not one of "
            f"{sorted(NAME_TYPES)}"
        )
    value = entry.get("value")
    if not isinstance(value, str) or _is_empty(value):
        errors.append(f"{prefix}: value must be a non-empty string")
    return errors


def _check_external_ref(
    idx: int,
    ref: Any,
    schemes: Collection[str],
) -> list[str]:
    """Validate one entry in entity.external_refs."""
    errors: list[str] = []
    prefix = f"entity.external_refs[{idx}]"
    if not isinstance(ref, Mapping):
        return [f"{prefix} must be a mapping"]
    scheme = ref.get("scheme")
    value = ref.get("value")
    if scheme not in schemes:
        errors.append(
            f"{prefix}: scheme {scheme!r} is not one of {sorted(schemes)}"
        )
        return errors
    if not isinstance(value, str) or _is_empty(value):
        errors.append(f"{prefix}: value must be a non-empty string")
        return errors
    pattern = _EXTERNAL_REF_PATTERNS.get(scheme)
    if pattern is not None and not pattern.match(value):
        errors.append(
            f"{prefix}: value {value!r} is not well-formed for scheme "
            f"{scheme!r}"
        )
    return errors


def validate_entity_proposal(
    proposal: Mapping[str, Any],
    *,
    entity_types: Collection[str] = VALID_ENTITY_TYPES,
    known_external_ref_schemes: Collection[str] = KNOWN_EXTERNAL_REF_SCHEMES,
) -> list[str]:
    """Validate an entity_proposal (the new proposal shape introduced by
    design/entity-proposal-shape.md). Returns a list of error strings —
    an empty list means the proposal is well formed enough to enter the
    queue.

    Pure function. The caller (the Write API, or
    client.craidd_client.propose_entity) supplies everything decidable
    without the DB:

      entity_types                permitted entity_type values. Defaults
                                  to the v0.1 nine.
      known_external_ref_schemes  the allow-list of identifier schemes
                                  for entity.external_refs (uprn, toid,
                                  cadw, blb, nhle, osm-id at v0.1).

    `proposal` is a mapping matching the file shape in
    entity-proposal-shape.md §3 — proposal_type, proposal_id,
    submitted_at, submitter, optional bundle_id / field_session_id,
    entity{entity_type, names[], optional address_text / external_refs[]},
    source, confidence, optional qualifiers, optional bilingual note.

    What this does NOT check (deferred to craidd-review):
      - whether the entity already exists (external_ref collision);
      - whether bundled claim proposals are consistent with the EP;
      - whether the submitter is a known curator;
      - whether `field_session_id` references a real open session.

    The cross-qualifier rule (co_signed_by ⇒ field_session_id) is
    delegated to validate_qualifiers and so applies here too.
    """
    errors: list[str] = []

    # --- proposal_type literal ------------------------------------------
    proposal_type = proposal.get("proposal_type")
    if proposal_type != "entity":
        errors.append(
            f"proposal_type must be 'entity', got {proposal_type!r}"
        )

    # --- proposal_id -----------------------------------------------------
    proposal_id = proposal.get("proposal_id")
    if not isinstance(proposal_id, str) or not _EP_ID_RE.match(proposal_id):
        errors.append(
            f"proposal_id {proposal_id!r} must match EP-<YYYYMMDD>-<HHMM>-"
            f"<8-hex>"
        )

    # --- submitted_at ----------------------------------------------------
    err = _validate_iso_date(proposal.get("submitted_at"))
    if err is not None:
        errors.append(f"submitted_at {err}")

    # --- submitter -------------------------------------------------------
    if _is_empty(proposal.get("submitter")):
        errors.append("submitter must be a non-empty string")

    # --- bundle_id / field_session_id (both optional) -------------------
    bundle_id = proposal.get("bundle_id")
    if bundle_id is not None:
        if not isinstance(bundle_id, str) or not _BUNDLE_ID_RE.match(bundle_id):
            errors.append(
                f"bundle_id {bundle_id!r} must match B-<YYYYMMDD>-<HHMM>-"
                f"<8-hex>"
            )
    field_session_id = proposal.get("field_session_id")
    if field_session_id is not None:
        if not isinstance(field_session_id, str) or _is_empty(field_session_id):
            errors.append("field_session_id must be a non-empty string")

    # --- entity block ----------------------------------------------------
    entity = proposal.get("entity")
    if not isinstance(entity, Mapping):
        errors.append("entity must be a mapping")
        # Without an entity block there's nothing more to check.
        return _finalise_entity_proposal_errors(errors, proposal)

    entity_type = entity.get("entity_type")
    if entity_type not in entity_types:
        errors.append(
            f"entity.entity_type {entity_type!r} is not one of "
            f"{sorted(entity_types)}"
        )

    # names: non-empty list, each entry well formed.
    names = entity.get("names")
    if not isinstance(names, list) or len(names) == 0:
        errors.append("entity.names must be a non-empty list")
    else:
        for i, entry in enumerate(names):
            errors.extend(_check_name_entry(i, entry))

    # address_text optional, must be a string if present.
    address_text = entity.get("address_text")
    if address_text is not None and not isinstance(address_text, str):
        errors.append("entity.address_text must be a string when present")

    # external_refs optional; if present, must be a list with valid entries.
    external_refs = entity.get("external_refs")
    if external_refs is not None:
        if not isinstance(external_refs, list):
            errors.append("entity.external_refs must be a list when present")
        else:
            for i, ref in enumerate(external_refs):
                errors.extend(
                    _check_external_ref(i, ref, known_external_ref_schemes)
                )

    # --- source: same minimal shape as claim proposals ------------------
    source = proposal.get("source")
    if not isinstance(source, Mapping) or _is_empty(source.get("source_id")):
        # Accept both 'source_id' (entity-proposal-shape.md §3 example) and
        # 'id' (claim proposals' convention) for forward-compatibility.
        if not isinstance(source, Mapping) or _is_empty(source.get("id")):
            errors.append(
                "source must be a mapping with a non-empty 'source_id' "
                "(or 'id')"
            )

    # --- confidence ------------------------------------------------------
    confidence = proposal.get("confidence")
    if confidence not in VALID_CONFIDENCES:
        errors.append(
            f"confidence {confidence!r} is not one of "
            f"{sorted(VALID_CONFIDENCES)}"
        )

    # --- note (optional, bilingual mapping) ------------------------------
    note = proposal.get("note")
    if note is not None:
        if not isinstance(note, Mapping):
            errors.append("note must be a mapping with cy and/or en keys")
        else:
            for lang in ("cy", "en"):
                if lang in note and not isinstance(note[lang], str):
                    errors.append(f"note.{lang} must be a string")

    # --- qualifiers (optional) ------------------------------------------
    qualifiers = proposal.get("qualifiers")
    if qualifiers is not None:
        if not isinstance(qualifiers, Mapping):
            errors.append("qualifiers must be a mapping when present")
        else:
            errors.extend(validate_qualifiers(qualifiers, pred=None))

    return errors


def _finalise_entity_proposal_errors(
    errors: list[str], proposal: Mapping[str, Any]
) -> list[str]:
    """Helper for the early-return path when entity block is missing.
    Still applies the qualifier and confidence checks that don't depend
    on the entity block."""
    confidence = proposal.get("confidence")
    if confidence not in VALID_CONFIDENCES:
        errors.append(
            f"confidence {confidence!r} is not one of "
            f"{sorted(VALID_CONFIDENCES)}"
        )
    qualifiers = proposal.get("qualifiers")
    if isinstance(qualifiers, Mapping):
        errors.extend(validate_qualifiers(qualifiers, pred=None))
    return errors
