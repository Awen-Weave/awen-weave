"""
The v0.1 seed predicate set — predicates spanning building, tenancy,
event, research_question, source, and town entities.

Source of truth: design/v0.1-schema.md §3.5. craidd-init writes these
rows into the predicate table at bootstrap; adding more after bootstrap
is a deliberate, Prawf-logged act.

NOTE — count: design/v0.1-schema.md §3.5 closes with the prose summary
"52 predicates", but the §3.5 tables themselves enumerate 58. The tables
are the authoritative spec; SEED_PREDICATES below transcribes all 58.
The "52" figure should be corrected in the doc.

NOTE — Welsh descriptions: the predicate table requires description_cy
NOT NULL, but §3.5 supplies English meanings only. Rather than machine-
translate (which would breach the project's Welsh-honesty discipline),
every description_cy here is the placeholder CY_PENDING. Filling these
properly is a deliberate Welsh-pass task — see the foundation handover.
"""
from __future__ import annotations

from dataclasses import dataclass


# Placeholder for description_cy until a proper Welsh pass is done. It
# satisfies the NOT NULL constraint without pretending to be Welsh, and
# is conspicuous in GET /predicates output.
CY_PENDING = "(Welsh description pending)"

# Value types and cardinalities permitted by the schema — mirrors the
# CHECK constraints in the predicate DDL (design/v0.1-schema.md §11).
VALUE_TYPES: frozenset[str] = frozenset(
    {"text", "int", "real", "date", "geom", "bilingual", "entity_ref"}
)
CARDINALITIES: frozenset[str] = frozenset({"single", "multi"})


@dataclass(frozen=True)
class PredicateDef:
    """One predicate's definition — the shape of a row in the predicate
    table (design/v0.1-schema.md §3.3).

    name                 the predicate name (primary key)
    value_type           text | int | real | date | geom | bilingual | entity_ref
    cardinality          single | multi
    applies_to_types     entity types this predicate may be claimed on
    description_en       English description (from §3.5 "meaning" column)
    description_cy       Welsh description (CY_PENDING until a Welsh pass)
    required_qualifiers  qualifier keys every claim on this predicate must carry
    constraint_json      optional JSON constraint string (e.g. an enum), or None
    """

    name: str
    value_type: str
    cardinality: str
    applies_to_types: tuple[str, ...]
    description_en: str
    description_cy: str = CY_PENDING
    required_qualifiers: tuple[str, ...] = ()
    constraint_json: str | None = None


# ---------------------------------------------------------------------------
# Building predicates — applies to entity_type 'building'
# ---------------------------------------------------------------------------
_BUILDING: tuple[PredicateDef, ...] = (
    PredicateDef("address", "bilingual", "single", ("building",),
                 "Postal address."),
    PredicateDef("geometry", "geom", "single", ("building",),
                 "Building footprint or point."),
    PredicateDef("uprn", "int", "single", ("building",),
                 "OS Unique Property Reference Number."),
    PredicateDef("building_type", "text", "single", ("building",),
                 "Building type. v0.1-schema.md §3.5 marks this a controlled "
                 "enum but does not yet define the enum values."),
    PredicateDef("floor_area_m2", "real", "single", ("building",),
                 "Total internal floor area in square metres."),
    PredicateDef("build_year", "int", "single", ("building",),
                 "Year built — use only when the date is exact."),
    PredicateDef("build_period", "text", "single", ("building",),
                 "Imprecise build period, e.g. 'c.1885', 'late C18'.",
                 required_qualifiers=("date_precision",)),
    PredicateDef("original_use", "bilingual", "multi", ("building",),
                 "Historic primary use(s)."),
    PredicateDef("current_use", "bilingual", "single", ("building",),
                 "Today's primary use."),
    PredicateDef("listed_grade", "text", "single", ("building",),
                 "Statutory listing grade.",
                 constraint_json='{"enum": ["I", "II*", "II"]}'),
    PredicateDef("listed_id", "text", "multi", ("building",),
                 "Cadw or British Listed Buildings register reference. "
                 "Multi-cardinality: a building may carry several."),
    PredicateDef("conservation_area", "text", "multi", ("building",),
                 "Conservation area(s) the building sits within."),
    PredicateDef("name_cy", "text", "multi", ("building",),
                 "Welsh name. Multi-cardinality; every claim must carry a "
                 "name_type qualifier.",
                 required_qualifiers=("name_type",)),
    PredicateDef("name_en", "text", "multi", ("building",),
                 "English name. Multi-cardinality; every claim must carry a "
                 "name_type qualifier.",
                 required_qualifiers=("name_type",)),
    PredicateDef("historical_note", "bilingual", "multi", ("building",),
                 "Free-text historical claim."),
    PredicateDef("architectural_description", "bilingual", "multi", ("building",),
                 "Structured architectural detail."),
    PredicateDef("material_primary", "text", "single", ("building",),
                 "Primary external wall material, e.g. 'snecked rubble "
                 "dolerite'."),
    PredicateDef("roof_type", "text", "single", ("building",),
                 "Roof form and material, e.g. 'hipped slate'."),
    PredicateDef("storeys", "int", "single", ("building",),
                 "Number of full storeys."),
    PredicateDef("adjacent_to", "entity_ref", "multi", ("building",),
                 "Another building physically adjacent to this one."),
    PredicateDef("contemporary_with", "entity_ref", "multi", ("building",),
                 "A building of the same construction period."),
    PredicateDef("group_value_with", "entity_ref", "multi", ("building",),
                 "A building whose listing reason is shared or related "
                 "(listed 'group value')."),
)

# ---------------------------------------------------------------------------
# Tenancy predicates — applies to entity_type 'tenancy'
# ---------------------------------------------------------------------------
_TENANCY: tuple[PredicateDef, ...] = (
    PredicateDef("tenancy_of", "entity_ref", "single", ("tenancy",),
                 "The building (or area) this tenancy occupies."),
    PredicateDef("tenant_name", "text", "single", ("tenancy",),
                 "Common name of the tenant."),
    PredicateDef("tenant_organisation", "text", "single", ("tenancy",),
                 "Formal organisation name, where applicable."),
    PredicateDef("tenancy_type", "text", "single", ("tenancy",),
                 "Tenancy type.",
                 constraint_json='{"enum": ["commercial_retail", '
                 '"commercial_wholesale", "residential", "office", '
                 '"hospitality", "community", "mixed", "vacant", "other"]}'),
    PredicateDef("tenant_business_type", "bilingual", "single", ("tenancy",),
                 "Nature of the tenant's business, e.g. 'newsagents and "
                 "bookshop'."),
    PredicateDef("period_start", "date", "single", ("tenancy",),
                 "Earliest plausible start of the tenancy.",
                 required_qualifiers=("date_precision",)),
    PredicateDef("period_end", "date", "single", ("tenancy",),
                 "Earliest plausible end of the tenancy; null means current.",
                 required_qualifiers=("date_precision",)),
)

# ---------------------------------------------------------------------------
# Event predicates — applies to entity_type 'event'
# ---------------------------------------------------------------------------
_EVENT: tuple[PredicateDef, ...] = (
    PredicateDef("event_type", "text", "single", ("event",),
                 "Event type.",
                 constraint_json='{"enum": ["refurbishment", "designation", '
                 '"change_of_use", "sale", "construction", "demolition", '
                 '"fire", "flood", "other"]}'),
    PredicateDef("event_start", "date", "single", ("event",),
                 "Event start date.",
                 required_qualifiers=("date_precision",)),
    PredicateDef("event_end", "date", "single", ("event",),
                 "Event end date; null means ongoing.",
                 required_qualifiers=("date_precision",)),
    PredicateDef("affects_entity", "entity_ref", "multi", ("event",),
                 "An entity this event acts upon."),
    PredicateDef("funder", "entity_ref", "multi", ("event",),
                 "A funder, where the funder is itself a recorded entity."),
    PredicateDef("funder_text", "text", "multi", ("event",),
                 "A funder, where recorded as a string only."),
    PredicateDef("scope_description", "bilingual", "single", ("event",),
                 "What the event did."),
    PredicateDef("consent_reference", "text", "multi", ("event",),
                 "Listed-building-consent, planning, or designation reference."),
)

# ---------------------------------------------------------------------------
# Research-question predicates — applies to entity_type 'research_question'
# ---------------------------------------------------------------------------
_RESEARCH_QUESTION: tuple[PredicateDef, ...] = (
    PredicateDef("question_text", "bilingual", "single", ("research_question",),
                 "The research question itself."),
    PredicateDef("relates_to_entity", "entity_ref", "multi",
                 ("research_question",),
                 "An entity the question is about."),
    PredicateDef("suggested_sources", "text", "multi", ("research_question",),
                 "Where to look — free text."),
    PredicateDef("priority", "text", "single", ("research_question",),
                 "Question priority.",
                 constraint_json='{"enum": ["low", "medium", "high"]}'),
    PredicateDef("status", "text", "single", ("research_question",),
                 "Question status.",
                 constraint_json='{"enum": ["open", "in_progress", '
                 '"answered", "abandoned"]}'),
    PredicateDef("answered_by_claim", "text", "single", ("research_question",),
                 "claim_id of the claim that resolved the question."),
)

# ---------------------------------------------------------------------------
# Source predicates — applies to entity_type 'source'
# ---------------------------------------------------------------------------
_SOURCE: tuple[PredicateDef, ...] = (
    PredicateDef("title_cy", "text", "single", ("source",),
                 "Welsh title, where applicable."),
    PredicateDef("title_en", "text", "single", ("source",),
                 "English title."),
    PredicateDef("citation", "text", "single", ("source",),
                 "Full citation string."),
    PredicateDef("url", "text", "single", ("source",),
                 "Canonical URL."),
    PredicateDef("organisation", "text", "single", ("source",),
                 "Authoring or holding organisation."),
    PredicateDef("licence", "text", "single", ("source",),
                 "Licence — OGL, CC-BY-SA, internal, etc."),
    PredicateDef("accessed_at", "date", "single", ("source",),
                 "Most recent retrieval date."),
    PredicateDef("file_hash", "text", "single", ("source",),
                 "SHA-256 of the evidence file, where applicable."),
)

# ---------------------------------------------------------------------------
# Town predicates — applies to entity_type 'town'
# ---------------------------------------------------------------------------
_TOWN: tuple[PredicateDef, ...] = (
    PredicateDef("material_tradition", "bilingual", "multi", ("town",),
                 "The town's building-material tradition."),
    PredicateDef("street_pattern", "bilingual", "single", ("town",),
                 "Narrative description of the town's street pattern."),
    PredicateDef("notable_event", "bilingual", "multi", ("town",),
                 "A notable event in the town's history."),
    PredicateDef("conservation_authority", "text", "single", ("town",),
                 "Local planning authority for conservation consent."),
    PredicateDef("unitary_authority", "text", "single", ("town",),
                 "Council responsible for non-planning matters."),
    PredicateDef("listed_building_count", "int", "single", ("town",),
                 "Count of listed buildings in the town. v0.1-schema.md §3.5 "
                 "notes the count should record the date it was made; "
                 "'accessed_at' is not a §3.2 qualifier, so record that date "
                 "in the claim note or via the source until v0.2 resolves it."),
    PredicateDef("parish", "text", "single", ("town",),
                 "Ecclesiastical parish, where relevant."),
)


# The complete v0.1 seed set, in schema-document order.
SEED_PREDICATES: tuple[PredicateDef, ...] = (
    _BUILDING + _TENANCY + _EVENT + _RESEARCH_QUESTION + _SOURCE + _TOWN
)

# Name -> PredicateDef, for fast lookup by the validation contract.
PREDICATE_REGISTRY: dict[str, PredicateDef] = {
    p.name: p for p in SEED_PREDICATES
}

# Import-time invariant: a duplicate predicate name would silently shadow
# in PREDICATE_REGISTRY. 58 distinct names expected (see the count note
# in this module's docstring).
if len(PREDICATE_REGISTRY) != len(SEED_PREDICATES):
    raise RuntimeError("duplicate predicate name in SEED_PREDICATES")
