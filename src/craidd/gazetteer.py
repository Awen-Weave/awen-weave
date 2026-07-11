"""
src/craidd/gazetteer.py — Deliverable B: the federation stamp emitter, plus the
record builders a gazetteer read needs.

Wraps the core `provenance_stamp` (craidd/federation.py) to emit ONE
SCH-FEDERATION-001 stamp per federated source read — it does not hand-roll a
stamp (brief §2). Alongside it, two builders shape the other two record kinds a
gazetteer snapshot carries:

  - `place_anchor(...)`   -> a SCH-PLACEANCHOR-001 record (labels + GSS codes +
                             lat/lng, keyed on uprn where resolved, null-tolerated).
  - `federated_name_claim(...)` -> a SCH-CLAIM-001 record for a federated name_*,
                             carrying the claim-level fail-loud gate:
                             binding="federated" + federated_from + source_ran_at
                             (brief §4). The qualifiers are derived from the SAME
                             SourceOfRecord as the stamp, via the core
                             `federation_qualifiers`, so the two layers can never
                             drift.

Engine-agnostic: an instance's reader (Dolgellau's, Y Bala's, a maes reader)
calls these to turn its own rows into governed records; the SCH-* shape lives
here once. `federated_utc` (the read time) is deliberately distinct from the
source's `ran_at_utc` (its run time) — verify-not-recall.
"""
from __future__ import annotations

from typing import Optional

from .federation import (
    FederatedResult,
    SourceOfRecord,
    federation_qualifiers,
    now_utc,
    provenance_stamp,
)

# Place-anchor keys the SCH-PLACEANCHOR-001 schema permits (additionalProperties
# is false), minus `labels` which is assembled separately. Keeping this explicit
# means a stray key never silently rides into a snapshot.
_ANCHOR_SCALAR_KEYS = (
    "uprn", "postcode", "lsoa", "ward_gss", "community_council_gss",
    "county_gss", "lat", "lng",
)


def place_anchor(
    *,
    uprn: Optional[str] = None,
    postcode: Optional[str] = None,
    lsoa: Optional[str] = None,
    ward_gss: Optional[str] = None,
    community_council_gss: Optional[str] = None,
    county_gss: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    label_cy: Optional[str] = None,
    label_en: Optional[str] = None,
) -> dict:
    """Build one SCH-PLACEANCHOR-001 record. All fields optional/null-tolerated
    (most UPRNs are null until coverage resolves them). `uprn` is coerced to a
    string (the schema types it string|null; the source store carries it as an
    integer). Only the `labels` present are emitted."""
    values = {
        "uprn": str(uprn) if uprn is not None else None,
        "postcode": postcode,
        "lsoa": lsoa,
        "ward_gss": ward_gss,
        "community_council_gss": community_council_gss,
        "county_gss": county_gss,
        "lat": lat,
        "lng": lng,
    }
    anchor = {k: values[k] for k in _ANCHOR_SCALAR_KEYS}
    labels = {}
    if label_cy is not None:
        labels["cy"] = label_cy
    if label_en is not None:
        labels["en"] = label_en
    if labels:
        anchor["labels"] = labels
    return anchor


def federated_name_claim(
    *,
    subject_id: str,
    predicate: str,           # "name_cy" | "name_en"
    value: str,
    source_id: str,
    recorded_by: str,
    source: SourceOfRecord,
    name_type: str,           # current_local | listed_register | historic | vernacular
    confidence: str = "high",
    dialect: Optional[str] = None,
) -> dict:
    """Build one federated SCH-CLAIM-001 name claim.

    Carries the claim-level federation gate (binding=federated + federated_from
    + source_ran_at), derived from `source` via the core `federation_qualifiers`
    so it matches the stamp exactly. Fail-loud through that call if the source
    lacks identity or run-UTC (invariants 2 & 3)."""
    if predicate not in ("name_cy", "name_en"):
        raise ValueError(f"federated_name_claim expects name_cy/name_en, got {predicate!r}")
    result = FederatedResult(source=source)
    qualifiers = federation_qualifiers(result)  # {binding, federated_from, source_ran_at}
    qualifiers["name_type"] = name_type
    if dialect is not None:
        qualifiers["dialect"] = dialect
    return {
        "subject_id": subject_id,
        "predicate": predicate,
        "value_text": value,
        "source_id": source_id,
        "recorded_by": recorded_by,
        "confidence": confidence,
        "qualifiers": qualifiers,
    }


def gazetteer_stamp(
    *,
    source: SourceOfRecord,
    consumer_instance: str,
    craidd_node: Optional[str] = None,
    craidd_source: Optional[str] = None,
    grade: Optional[str] = None,
    counts: Optional[dict] = None,
    federated_utc: Optional[str] = None,
    licence: str = "OGL",
    crs: str = "n/a",
    aoi: str = "n/a",
    clipped: bool = False,
    notes: str = "",
) -> dict:
    """Emit ONE SCH-FEDERATION-001 stamp for a gazetteer read.

    A thin wrapper over the core `provenance_stamp` (never a hand-rolled stamp).
    `federated_utc` (the consumer's read time) defaults to now and is distinct
    from `source.ran_at_utc` (the source's run time) — do not conflate them."""
    result = FederatedResult(
        source=source,
        consumer_instance=consumer_instance,
        craidd_node=craidd_node,
        craidd_source=craidd_source,
        grade=grade,
        federated_utc=federated_utc or now_utc(),
        licence=licence,
        crs=crs,
        aoi=aoi,
        clipped=clipped,
        counts=counts or {},
        notes=notes,
    )
    return provenance_stamp(result)
