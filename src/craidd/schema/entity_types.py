"""
Controlled vocabulary for entity.entity_type — the fifteen v0.1 entity types.

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
    # 0.1.10 (PROPOSED, card c0944; rulings Llys 10/10/2026 Q1 [sig:8f0740b4], Q2 [sig:3cc4cb54],
    # Q4 [sig:02dd6f4c]): an ODS-coded NHS organisation (practice, site or board; the role is a
    # claim) and a GP cluster (by its publisher's code). NEITHER IS A PLACE: both are grain
    # `not_spatial` (grain.py), and where an organisation's premises are is carried as stated
    # claims about it (_NHS_ORG in predicates.py). Written `nhs_org:<ODS code>` and
    # `cluster:<publisher code>`; a bare code is refused (validation.org_subject_errors).
    "nhs_org": "An NHS organisation identified by its ODS code — a GP practice, a site, or a health board. Not a place.",
    "cluster": "A GP cluster — a publisher-defined group of practices, keyed by the publisher's code. Not a place.",
    # 0.1.11 (card c1878; signed by Huw as Llys 26/10/2026 [sig:0ad68cf6], ruled [sig:d458cafe], Class A scrutiny c1852):
    # a registered care establishment that is not an NHS body. NOT A PLACE (grain.py), as nhs_org. Written
    # `care_establishment:<register>-<id>` in lower case: hiw-m and four digits (minted, from the catalogue's ledger) or a
    # CIW URN lower-cased; a bare id is refused (validation.ORG_SUBJECT_SHAPES).
    "care_establishment": ("A health or social care establishment with premises the public attends, as a Welsh regulator "
                           "registers it (HIW or CIW). Not an NHS body or unit (that is nhs_org); not a service at a "
                           "private dwelling (domiciliary support, childminding). Not a place."),
}

# The set used for fast membership checks and by the validation contract.
VALID_ENTITY_TYPES: frozenset[str] = frozenset(ENTITY_TYPES)


def is_valid_entity_type(entity_type: str) -> bool:
    """True if entity_type is one of the fourteen v0.1 controlled types (`site` 0.1.4, `station` 0.1.5, `coastal_cell` 0.1.6, `nhs_org` and `cluster` 0.1.10, `care_establishment` 0.1.11)."""
    return entity_type in VALID_ENTITY_TYPES
