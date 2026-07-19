"""craidd.returns — the RETURNS CHANNEL slice (up-flow federation).

Federation Doctrine v0.2 (RATIFIED 2026-07-18) §8: a public's commons-returnable
claims flow *up* from the instance (the Pi) to the commons centre — stamped,
reference-don't-copy. The dataset never moves; the Pi stays sole author/custodian.
This module builds the governed slice; `cli/craidd_return.py` is the thin CLI.

REALITY-CONFIRM CORRECTION (2026-07-18, Code):
    The brief's slice rule — "claims already stamped `returnable: commons`" — does
    NOT map to the data. There is no `returnable`/`tier`/commons stamp anywhere:
    the claim qualifier set is CLOSED (`additionalProperties:false`, 15 keys), so
    returnability is a CONSTITUTIONAL CATEGORY (ADJ-RETURN-001), not a stored field.
    So the slice is defined by CLAIM CATEGORY (predicate) per ADJ-RETURN-001, not by
    a filter on a non-existent flag. The predicate allowlist below is the concrete,
    coordinator-adjustable mapping of ADJ-RETURN-001's returnable categories onto
    the Town Dataset's real predicates — flagged for confirmation, not invented
    adjudication (it implements an existing rule).

ADJ-RETURN-001 returnable categories → Town Dataset predicates:
    1. identity of an open-world object (UPRN, TOID, title/INSPIRE ref) → uprn, toid
    2. linkage between two open identifiers (Cadw↔building, UPRN↔building)  → listed_id
    3. geometry (footprint / boundary)                                     → geometry*
    4. provenance/attestation metadata for the above                       → (carried as source_id/qualifiers)

  * `geometry` is DEFERRED from the v1 slice: it needs WKT/CRS serialisation
    (value_geom → value_text with an explicit CRS) which is a separate, careful
    step. v1 carries the open-identifier IDENTITY + LINKAGE claims only. Add
    'geometry' here once the geometry serialisation + CRS stamp are agreed.

Everything else is OUT by construction: names, addresses, descriptions, survey
content, anything personal/tenancy/event — none are in the allowlist, so the
"if it isn't an open-identifier identity/linkage claim, it doesn't travel" slice
discipline is enforced positively, not by a denylist.
"""
from __future__ import annotations

from typing import Optional

from craidd.federation import FederatedResult, SourceOfRecord, federation_qualifiers
from craidd.snapshot import SnapshotRecords

# --- the returnable slice: ADJ-RETURN-001 open-identifier identity + linkage ---
# Coordinator-adjustable. Grounded in ADJ-RETURN-001 categories 1 & 2. `geometry`
# (category 3) is intentionally absent from v1 — see module docstring.
RETURNABLE_PREDICATES: tuple[str, ...] = ("uprn", "toid", "listed_id")


def _value_of(row: dict) -> Optional[str]:
    """The claim's value as text, from whichever value_* column is populated.

    Open-identifier claims carry text/int values (e.g. listed_id='Cadw 4938',
    uprn=100100..). We never fabricate a value; a claim with no usable value is
    skipped by the caller.
    """
    if row.get("value_text") not in (None, ""):
        return str(row["value_text"])
    if row.get("value_int") is not None:
        return str(row["value_int"])
    if row.get("value_en") not in (None, ""):
        return str(row["value_en"])
    if row.get("value_cy") not in (None, ""):
        return str(row["value_cy"])
    return None


def federated_return_claim(
    *,
    subject_id: str,
    predicate: str,
    value: str,
    source_id: str,
    recorded_by: str,
    source: SourceOfRecord,
    confidence: str = "high",
) -> dict:
    """One federated SCH-CLAIM-001 claim for the returns slice (any returnable
    predicate — NOT restricted to names like `gazetteer.federated_name_claim`).

    Routes the claim-level gate through the same `federation_qualifiers(source)`
    as the stamp, so the claim's `binding=federated`/`federated_from`/
    `source_ran_at` and the Prawf-logged stamp can never drift. Fail-loud (via
    that call) if the source lacks identity or run-UTC.
    """
    qualifiers = federation_qualifiers(FederatedResult(source=source))
    return {
        "subject_id": subject_id,
        "predicate": predicate,
        "value_text": value,
        "source_id": source_id,
        "recorded_by": recorded_by,
        "confidence": confidence,
        "qualifiers": qualifiers,
    }


# Columns the selection reads from the Craidd `current_claim` view (the deduped
# active claim surface the gazetteer reader also uses).
_SELECT_COLS = (
    "subject_id",
    "predicate",
    "value_text",
    "value_int",
    "value_cy",
    "value_en",
    "source_id",
    "confidence",
)


def read_returnable_claims(con, *, predicates: tuple[str, ...] = RETURNABLE_PREDICATES) -> list[dict]:
    """Read the returnable-category claims from a Craidd DuckDB connection.

    Pure read (the caller opens the connection read_only). Selects from the
    `current_claim` view (active, superseded rows excluded) restricted to the
    ADJ-RETURN-001 predicate allowlist. Skips rows with no usable value.
    """
    placeholders = ",".join("?" for _ in predicates)
    rows = con.execute(
        f"SELECT {', '.join(_SELECT_COLS)} FROM current_claim "
        f"WHERE predicate IN ({placeholders}) "
        f"ORDER BY subject_id, predicate",
        list(predicates),
    ).fetchall()
    out = []
    for r in rows:
        row = dict(zip(_SELECT_COLS, r))
        if _value_of(row) is None:
            continue
        out.append(row)
    return out


def build_returns(
    claim_rows: list[dict],
    *,
    source: SourceOfRecord,
    consumer_instance: str,
    recorded_by: str,
    stamp,
) -> SnapshotRecords:
    """Assemble a SnapshotRecords for the returns slice.

    `stamp` is a pre-built SCH-FEDERATION-001 stamp (via craidd.federation /
    gazetteer.gazetteer_stamp) carrying source_of_record = the Town Dataset
    instance. Place-anchors are empty in v1 — the slice is identity/linkage
    claims that resolve to their subject via subject_id + source_of_record; richer
    anchors follow when geometry is added.
    """
    claims = [
        federated_return_claim(
            subject_id=row["subject_id"],
            predicate=row["predicate"],
            value=_value_of(row),
            source_id=row["source_id"] or source.instance,
            recorded_by=recorded_by,
            source=source,
            confidence=row.get("confidence") or "high",
        )
        for row in claim_rows
    ]
    return SnapshotRecords(
        place_anchors=[],
        claims=claims,
        stamps=[stamp],
        source_ran_at={source.instance: source.ran_at_utc},
    )
