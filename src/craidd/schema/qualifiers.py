"""
Qualifier vocabulary — claim-level metadata. Source: design/v0.1-schema.md §3.2.

Qualifiers describe a claim (its dialect, its applicable floor, its date
precision, its name type) without warranting separate provenance. They
travel with the claim in the claim.qualifiers_json column.

Two of the four domains are CLOSED — a value outside the set is a
validation error (name_type, date_precision). Two are OPEN with known
values — the listed values are recognised, but the domain is not closed
(dialect accepts any ISO language code; floor_scope accepts free text
where a building's occupancy needs it, per §3.2).
"""
from __future__ import annotations

# The qualifier keys that exist at all in v0.1.
QUALIFIER_KEYS: frozenset[str] = frozenset(
    {"dialect", "name_type", "floor_scope", "date_precision"}
)

# --- dialect: OPEN domain. Default for Dolgellau is north-Wales register. ---
DEFAULT_DIALECT = "cy-GB-north"
KNOWN_DIALECTS: frozenset[str] = frozenset(
    {"cy-GB-north", "cy-GB-south", "cy-GB-mid", "cy-GB"}
)

# --- name_type: CLOSED domain. Required on every name_cy / name_en claim. ---
NAME_TYPES: frozenset[str] = frozenset(
    {"current_local", "listed_register", "historic", "vernacular"}
)

# --- floor_scope: OPEN domain. Used on tenancy and event claims. ---
KNOWN_FLOOR_SCOPES: frozenset[str] = frozenset(
    {"whole", "ground", "first", "upper", "attic", "basement"}
)

# --- date_precision: CLOSED domain. Used on claims carrying a value_date. ---
DATE_PRECISIONS: frozenset[str] = frozenset(
    {"exact", "year", "decade", "century", "range"}
)

# Closed domains: a qualifier value here MUST be in the set.
CLOSED_QUALIFIER_DOMAINS: dict[str, frozenset[str]] = {
    "name_type": NAME_TYPES,
    "date_precision": DATE_PRECISIONS,
}

# Open domains: the listed values are recognised, but a value outside the
# set is permitted (validation may warn, but does not reject).
OPEN_QUALIFIER_DOMAINS: dict[str, frozenset[str]] = {
    "dialect": KNOWN_DIALECTS,
    "floor_scope": KNOWN_FLOOR_SCOPES,
}
