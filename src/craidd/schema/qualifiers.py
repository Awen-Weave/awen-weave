"""
Qualifier vocabulary — claim-level metadata. Source: design/v0.1-schema.md §3.2
plus the Lleolydd-driven additions in §10 item 7 (landed 2026-05-16).

Qualifiers describe a claim (its dialect, its applicable floor, its date
precision, its name type, its verification provenance, its temporal status)
without warranting separate provenance. They travel with the claim in the
claim.qualifiers_json column.

Two existing domains are CLOSED — a value outside the set is a validation
error (name_type, date_precision). Two existing domains are OPEN with known
values — the listed values are recognised but a value outside is permitted
(dialect accepts any ISO language code; floor_scope accepts free text).

§10 item 7 additions (2026-05-16):
- `verification_method`, `temporal_status`, `geometry_basis` — three new
  CLOSED domains supporting Lleolydd's UPRN-verification flow.
- `verified_at`, `cache_snapshot_id`, `field_session_id`, `co_signed_by` —
  four new OPEN-form keys recognised as valid qualifier names; their
  values get type/format checks in validation.py rather than enum checks.
- Cross-qualifier rule (enforced in validation.py): `co_signed_by` must
  be accompanied by `field_session_id`. Co-sign requires a named session.

Phase 2.1 additions (2026-07-03) — the `federated` binding:
- `binding` — a new CLOSED domain (BINDINGS) recording *how* a claim's
  value was derived: asserted / measured / curated / derived / federated.
  Follows the §10 item 7 precedent exactly (closed-domain qualifier +
  validation + a cross-qualifier rule). No default — binding is explicit.
- `federated_from`, `source_ran_at` — two new OPEN-form keys carrying the
  minimal source-of-record for a federated read (the source instance id
  and the source's OWN run-UTC). Structured, not free text: `source_ran_at`
  parses as ISO-8601 in validation.py; `federated_from` is a non-empty
  string. The FULL federation stamp (repo, paths, counts, licence, …)
  lives in craidd/federation.py and is what Prawf logs — these two keys
  are only the fail-loud gate on the claim itself.
- Cross-qualifier rule (enforced in validation.py): a claim with
  `binding == "federated"` MUST carry both `federated_from` and
  `source_ran_at` (mirrors `co_signed_by` ⇒ `field_session_id`).
  See design/v0.1-schema.md §10 item 8 and craidd/federation.py.
"""
from __future__ import annotations

# The qualifier keys that exist at all in v0.1.
# 4 original + 7 added by §10 item 7 + 3 added by Phase 2.1 = 14 total.
QUALIFIER_KEYS: frozenset[str] = frozenset(
    {
        # Original v0.1 vocabulary.
        "dialect",
        "name_type",
        "floor_scope",
        "date_precision",
        # §10 item 7 — closed-domain additions.
        "verification_method",
        "temporal_status",
        "geometry_basis",
        # §10 item 7 — open-form additions (string-shaped, no closed enum).
        "verified_at",
        "cache_snapshot_id",
        "field_session_id",
        "co_signed_by",
        # Phase 2.1 — the federated binding.
        "binding",              # CLOSED domain (BINDINGS).
        "federated_from",       # open-form: source instance id.
        "source_ran_at",        # open-form: source's OWN run-UTC (ISO-8601).
    }
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

# --- verification_method: CLOSED domain. v0.1-schema.md §10 item 7.3. -------
# Records *how* the curator reached a verification decision, on geometry,
# verified_building_toid, and location_verification_status claims.
VERIFICATION_METHODS: frozenset[str] = frozenset(
    {"on-site", "aerial", "local-knowledge", "documentary", "desk-derived"}
)

# --- temporal_status: CLOSED domain. v0.1-schema.md §10 item 7.4. -----------
# Lets one drag-to-place primitive serve both curator-correcting-existing-UPRN
# (existing) and energy-modeller-placing-future-PV (proposed) without changing
# the underlying claim shape.
TEMPORAL_STATUSES: frozenset[str] = frozenset(
    {"existing", "proposed", "historic", "removed"}
)
DEFAULT_TEMPORAL_STATUS = "existing"

# --- geometry_basis: CLOSED domain. v0.1-schema.md §10 item 7.2. ------------
# v0.1 item 7 introduces this enum (no pre-existing values in the code as of
# 2026-05-16 — zero usage in src/, tests/, seed/). Existing geometry claims
# with no geometry_basis qualifier remain valid; the qualifier is optional.
GEOMETRY_BASES: frozenset[str] = frozenset(
    {
        "os-open-uprn-original",        # original OS Open UPRN coordinate
        "auto-snapped-to-toid",         # snapped to unique TOID centroid
        "curator-placed",               # drag-to-place from scratch
        "curator-confirmed-original",   # original confirmed, no change
    }
)

# --- binding: CLOSED domain. Phase 2.1 (2026-07-03), v0.1-schema.md §10 item 8.
# Records HOW a claim's value was derived. The provenance-derivation axis,
# distinct from confidence (how sure) and verification_method (how a curator
# decided). No DEFAULT_BINDING — a binding, when carried, is always explicit;
# claims may omit `binding` entirely (it is not a required qualifier), but a
# stated binding must be in this set.
#   asserted  — stated by a source (a source entity says so).
#   measured  — an instrument / open-data reading.
#   curated   — a human decided it.
#   derived   — computed from other claims on this instance.
#   federated — referenced read-only from ANOTHER Awen instance (never copied).
#               Requires source-of-record provenance — see the cross-rule in
#               validation.py and the stamp in craidd/federation.py.
BINDINGS: frozenset[str] = frozenset(
    {"asserted", "measured", "curated", "derived", "federated"}
)

# Closed domains: a qualifier value here MUST be in the set.
# Order: original v0.1 entries first, then §10 item 7 additions, then Phase 2.1.
CLOSED_QUALIFIER_DOMAINS: dict[str, frozenset[str]] = {
    "name_type": NAME_TYPES,
    "date_precision": DATE_PRECISIONS,
    "verification_method": VERIFICATION_METHODS,
    "temporal_status": TEMPORAL_STATUSES,
    "geometry_basis": GEOMETRY_BASES,
    "binding": BINDINGS,
}

# Open domains: the listed values are recognised, but a value outside the
# set is permitted (validation may warn, but does not reject).
OPEN_QUALIFIER_DOMAINS: dict[str, frozenset[str]] = {
    "dialect": KNOWN_DIALECTS,
    "floor_scope": KNOWN_FLOOR_SCOPES,
}
