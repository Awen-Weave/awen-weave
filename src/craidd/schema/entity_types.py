"""
Controlled vocabulary for entity.entity_type — the twelve v0.1 entity types.

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
    # 0.1.4 (Llys ratified 25/07/2026): a bounded parcel or development site as a subject in
    # its own right — what a planning application, allocation or opportunity assessment is
    # ABOUT. Distinct from `area` (a designated/administrative boundary, which exists
    # independently of any proposal) and from `building` (a site may hold none, or several).
    "site": "A bounded parcel or development site considered as a subject in its own right.",
    # 0.1.5 (Llys ratified 06/08/2026, sig:c659a12f): an environmental monitoring facility
    # (gauge/sensor/station) — the fixed point observations are taken AT and attach to;
    # anchored to INSPIRE EnvironmentalMonitoringFacility. Distinct from `site` (a parcel/
    # development subject) and `building` (a structure): a station is the measurement facility
    # itself, the subject a hydrology or air-quality observation is about. Anchors the 4 EA
    # Hydrology predicates ratified alongside.
    "station": "An environmental monitoring facility — a fixed point (gauge/sensor/station) that observations attach to.",
    # 0.1.6 (Llys ratified 07/08/2026, sig:7508450d): a coastal/marine management unit — a Defra
    # SMP sediment cell or policy unit — as a subject in its own right; the stretch of coast a
    # shoreline policy, coastal-erosion projection or sea-level figure is ABOUT. The marine/coastal
    # join spine (SPINES.md), alongside the UPRN and gazetteer-GSS spines. Distinct from `area` (a
    # land boundary) and `station` (a fixed monitoring point). Anchors coastal indicators.
    "coastal_cell": "A coastal/marine management unit (Defra SMP sediment cell) — the stretch of coast a shoreline policy, erosion projection or sea-level figure is about.",
}

# The set used for fast membership checks and by the validation contract.
VALID_ENTITY_TYPES: frozenset[str] = frozenset(ENTITY_TYPES)


def is_valid_entity_type(entity_type: str) -> bool:
    """True if entity_type is one of the twelve v0.1 controlled types (`site` 0.1.4, `station` 0.1.5, `coastal_cell` 0.1.6)."""
    return entity_type in VALID_ENTITY_TYPES
