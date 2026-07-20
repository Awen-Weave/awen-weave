"""
The v0.1 seed predicate set — predicates spanning building, tenancy,
event, research_question, source, and town entities.

Source of truth: design/v0.1-schema.md §3.5. craidd-init writes these
rows into the predicate table at bootstrap; adding more after bootstrap
is a deliberate, Prawf-logged act.

NOTE — count: design/v0.1-schema.md §3.5 closes with the prose summary
"52 predicates", but the §3.5 tables themselves enumerate 58. The tables
are the authoritative spec; SEED_PREDICATES below transcribes all 58
plus the two §10 item 7 additions (verified_building_toid,
location_verification_status), bringing the total to 60. The "52" figure
should be corrected in the doc.

NOTE — post-bootstrap additions: the four Egni demand predicates
(_ENERGY_DEMAND, 2026-07-20) take the total to 64. Registering them is a
deliberate, Prawf-logged post-bootstrap act, per the ratified Egni
decision note (egni/design/entity-kind-and-predicates-decision-note.md
§2a). They apply only to the existing `area`/`building` kinds — the
demand baseline (Egni M2) needs no new entity kind. The `site` kind the
same note proposes is an M3 concern AND a constitution machine-layer
change (SCH-ENTITY-001 enumerates a closed nine at the pinned v0.1.3), so
it is deliberately NOT added here — see the hand-off report.

NOTE — Welsh descriptions: the predicate table requires description_cy
NOT NULL, but §3.5 supplies English meanings only. Every description_cy
below is the tutor-attested form from the 2026-05-19 Catrin Stephens
session via the magic-link cards app — see
Awen-Weave/awen-cards/welsh-tutor-cards.yaml (each card's `chosen` block
carries the verified attestor + capture timestamp) and the session
export at Awen-Weave/awen-cards/sessions/2026-05-19-catrin-stephens.json.
CY_PENDING remains in this module as a placeholder for any future
predicate added before its Welsh form is attested.
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
                 "Postal address.", description_cy="cyfeiriad post"),
    PredicateDef("geometry", "geom", "single", ("building",),
                 "Building footprint or point.", description_cy="geometreg yr adeilad - ôl troed yr adeilad"),
    PredicateDef("uprn", "int", "single", ("building",),
                 "OS Unique Property Reference Number.", description_cy="Rhif Cyfeirnod Unigryw Eiddo (UPRN) yr OS"),
    PredicateDef("building_type", "text", "single", ("building",),
                 "Building type. v0.1-schema.md §3.5 marks this a controlled "
                 "enum but does not yet define the enum values.", description_cy="math o adeilad"),
    PredicateDef("floor_area_m2", "real", "single", ("building",),
                 "Total internal floor area in square metres.", description_cy="cyfanswm arwynebedd llawr mewnol mewn metrau sgwâr"),
    PredicateDef("build_year", "int", "single", ("building",),
                 "Year built — use only when the date is exact.", description_cy="blwyddyn adeiladu — defnyddiwch dim ond pan fo'r dyddiad yn fanwl gywir"),
    PredicateDef("build_period", "text", "single", ("building",),
                 "Imprecise build period, e.g. 'c.1885', 'late C18'.",
                 required_qualifiers=("date_precision",), description_cy="Cyfnod adeiladu yn fras"),
    PredicateDef("original_use", "bilingual", "multi", ("building",),
                 "Historic primary use(s).", description_cy="defnydd(iau) gwreiddiol"),
    PredicateDef("current_use", "bilingual", "single", ("building",),
                 "Today's primary use.", description_cy="defnydd presennol"),
    PredicateDef("listed_grade", "text", "single", ("building",),
                 "Statutory listing grade.",
                 constraint_json='{"enum": ["I", "II*", "II"]}', description_cy="gradd restredig statudol"),
    PredicateDef("listed_id", "text", "multi", ("building",),
                 "Cadw or British Listed Buildings register reference. "
                 "Multi-cardinality: a building may carry several.", description_cy="cyfeirnod cofrestr Cadw neu adeiladau rhestredig Prydain"),
    PredicateDef("conservation_area", "text", "multi", ("building",),
                 "Conservation area(s) the building sits within.", description_cy="ardal gadwraeth"),
    PredicateDef("name_cy", "text", "multi", ("building",),
                 "Welsh name. Multi-cardinality; every claim must carry a "
                 "name_type qualifier.",
                 required_qualifiers=("name_type",), description_cy="enw Cymraeg"),
    PredicateDef("name_en", "text", "multi", ("building",),
                 "English name. Multi-cardinality; every claim must carry a "
                 "name_type qualifier.",
                 required_qualifiers=("name_type",), description_cy="enw Saesneg"),
    PredicateDef("historical_note", "bilingual", "multi", ("building",),
                 "Free-text historical claim.", description_cy="nodyn hanesyddol — testun rhydd"),
    PredicateDef("architectural_description", "bilingual", "multi", ("building",),
                 "Structured architectural detail.", description_cy="disgrifiad pensaernïol strwythuredig"),
    PredicateDef("material_primary", "text", "single", ("building",),
                 "Primary external wall material, e.g. 'snecked rubble "
                 "dolerite'.", description_cy="prif ddeunydd wal allanol"),
    PredicateDef("roof_type", "text", "single", ("building",),
                 "Roof form and material, e.g. 'hipped slate'.", description_cy="math o do — ffurf a deunydd"),
    PredicateDef("storeys", "int", "single", ("building",),
                 "Number of full storeys.", description_cy="nifer y lloriau llawn"),
    PredicateDef("adjacent_to", "entity_ref", "multi", ("building",),
                 "Another building physically adjacent to this one.", description_cy="adeilad arall sy'n gyfagos yn gorfforol i hwn"),
    PredicateDef("contemporary_with", "entity_ref", "multi", ("building",),
                 "A building of the same construction period.", description_cy="adeilad o'r un cyfnod adeiladu"),
    PredicateDef("group_value_with", "entity_ref", "multi", ("building",),
                 "A building whose listing reason is shared or related "
                 "(listed 'group value').", description_cy="adeilad sy'n rhannu rheswm rhestru (gwerth grŵp)"),
    # --- §10 item 7 — Lleolydd UPRN-verification predicates (2026-05-16) ---
    PredicateDef(
        name="verified_building_toid",
        value_type="text",  # OS MasterMap TopographicArea string, e.g. "osgb1000005195614324"
        cardinality="single",  # latest wins; superseded entries retained in history
        applies_to_types=("building",),
        description_en=(
            "The OS MasterMap TopographicArea TOID a curator has explicitly "
            "confirmed represents this building's footprint. Distinct from "
            "any auto-snapped TOID, which lives only as a derivation."
        ),
        description_cy="TOID OS MasterMap Topographic Area wedi cadarnhau yn benodol gan guradur fel amlinelliad yr adeilad",
        required_qualifiers=(
            "verification_method", "verified_at", "cache_snapshot_id",
        ),
        constraint_json=None,
    ),
    PredicateDef(
        name="location_verification_status",
        value_type="text",  # enum-as-text; constraint_json carries the closed set
        cardinality="single",  # derived; materialised
        # v0.1 scope: building only. The schema doc's "Subject: building, UPRN"
        # was loose — UPRN isn't a v0.1 entity_type. UPRN-as-subject deferred to
        # v0.3 (Huw decision 2026-05-16). Status indirectly covers the
        # building's primary UPRN.
        applies_to_types=("building",),
        description_en=(
            "The verification status band for this building's primary UPRN. "
            "Derived from the live claims plus Lleolydd's broadcast layer's "
            "pending placements; refreshed on proposal acceptance, cache "
            "rebuild, and broadcast tick. One of: verified, auto-snapped, "
            "unsnapped, contested, non-postal."
        ),
        description_cy="statws gwirio lleoliad — band sy'n deillio o honiadau byw a haen ddarlledu Lleolydd",
        required_qualifiers=("cache_snapshot_id",),
        constraint_json=(
            '{"enum": ["verified", "auto-snapped", "unsnapped", '
            '"contested", "non-postal"]}'
        ),
    ),
)

# ---------------------------------------------------------------------------
# Tenancy predicates — applies to entity_type 'tenancy'
# ---------------------------------------------------------------------------
_TENANCY: tuple[PredicateDef, ...] = (
    PredicateDef("tenancy_of", "entity_ref", "single", ("tenancy",),
                 "The building (or area) this tenancy occupies.", description_cy="yr adeilad (neu'r ardal) y mae'r denantiaeth hon yn ei feddiannu"),
    PredicateDef("tenant_name", "text", "single", ("tenancy",),
                 "Common name of the tenant.", description_cy="enw cyffredin y tenant"),
    PredicateDef("tenant_organisation", "text", "single", ("tenancy",),
                 "Formal organisation name, where applicable.", description_cy="enw'r sefydliad yn ffurfiol, lle bo'n berthnasol"),
    PredicateDef("tenancy_type", "text", "single", ("tenancy",),
                 "Tenancy type.",
                 constraint_json='{"enum": ["commercial_retail", '
                 '"commercial_wholesale", "residential", "office", '
                 '"hospitality", "community", "mixed", "vacant", "other"]}', description_cy="math o denantiaeth"),
    PredicateDef("tenant_business_type", "bilingual", "single", ("tenancy",),
                 "Nature of the tenant's business, e.g. 'newsagents and "
                 "bookshop'.", description_cy="natur busnes y tenant, e.e. 'siop bapurau newydd a llyfrau'"),
    PredicateDef("period_start", "date", "single", ("tenancy",),
                 "Earliest plausible start of the tenancy.",
                 required_qualifiers=("date_precision",), description_cy="dechrau cynharaf credadwy y denantiaeth"),
    PredicateDef("period_end", "date", "single", ("tenancy",),
                 "Earliest plausible end of the tenancy; null means current.",
                 required_qualifiers=("date_precision",), description_cy="diwedd cynharaf credadwy y denantiaeth; gadael yn wag ar gyfer tenantiaeth cyfredol"),
)

# ---------------------------------------------------------------------------
# Event predicates — applies to entity_type 'event'
# ---------------------------------------------------------------------------
_EVENT: tuple[PredicateDef, ...] = (
    PredicateDef("event_type", "text", "single", ("event",),
                 "Event type.",
                 constraint_json='{"enum": ["refurbishment", "designation", '
                 '"change_of_use", "sale", "construction", "demolition", '
                 '"fire", "flood", "other"]}', description_cy="math o ddigwyddiad"),
    PredicateDef("event_start", "date", "single", ("event",),
                 "Event start date.",
                 required_qualifiers=("date_precision",), description_cy="dyddiad dechrau'r digwyddiad"),
    PredicateDef("event_end", "date", "single", ("event",),
                 "Event end date; null means ongoing.",
                 required_qualifiers=("date_precision",), description_cy="dyddiad diwedd y digwyddiad; gadael yn wag ar gyfer digwyddiad cyfredol"),
    PredicateDef("affects_entity", "entity_ref", "multi", ("event",),
                 "An entity this event acts upon.", description_cy="endid y mae'r digwyddiad hwn yn ei effeithio"),
    PredicateDef("funder", "entity_ref", "multi", ("event",),
                 "A funder, where the funder is itself a recorded entity.", description_cy="arianwr, lle bo'r arianwr ei hun yn endid sydd wedi'i gofnodi"),
    PredicateDef("funder_text", "text", "multi", ("event",),
                 "A funder, where recorded as a string only.", description_cy="arianwr, lle'i nodir fel llinyn yn unig"),
    PredicateDef("scope_description", "bilingual", "single", ("event",),
                 "What the event did.", description_cy="disgrifiad y digwyddiad - beth wnaeth y digwyddiad"),
    PredicateDef("consent_reference", "text", "multi", ("event",),
                 "Listed-building-consent, planning, or designation reference.", description_cy="cyfeirnod cydsynio adeilad rhestredig, cynllunio, neu ddynodi"),
)

# ---------------------------------------------------------------------------
# Research-question predicates — applies to entity_type 'research_question'
# ---------------------------------------------------------------------------
_RESEARCH_QUESTION: tuple[PredicateDef, ...] = (
    PredicateDef("question_text", "bilingual", "single", ("research_question",),
                 "The research question itself.", description_cy="y cwestiwn ymchwil ei hun"),
    PredicateDef("relates_to_entity", "entity_ref", "multi",
                 ("research_question",),
                 "An entity the question is about.", description_cy="pwnc y mae'r cwestiwn yn ei gylch"),
    PredicateDef("suggested_sources", "text", "multi", ("research_question",),
                 "Where to look — free text.", description_cy="ble i edrych — testun rhydd"),
    PredicateDef("priority", "text", "single", ("research_question",),
                 "Question priority.",
                 constraint_json='{"enum": ["low", "medium", "high"]}', description_cy="blaenoriaeth cwestiwn"),
    PredicateDef("status", "text", "single", ("research_question",),
                 "Question status.",
                 constraint_json='{"enum": ["open", "in_progress", '
                 '"answered", "abandoned"]}', description_cy="statws cwestiwn"),
    PredicateDef("answered_by_claim", "text", "single", ("research_question",),
                 "claim_id of the claim that resolved the question.", description_cy="claim_id yr honiad a ddatrysodd y cwestiwn"),
)

# ---------------------------------------------------------------------------
# Source predicates — applies to entity_type 'source'
# ---------------------------------------------------------------------------
_SOURCE: tuple[PredicateDef, ...] = (
    PredicateDef("title_cy", "text", "single", ("source",),
                 "Welsh title, where applicable.", description_cy="teitl Cymraeg, lle bo'n berthnasol"),
    PredicateDef("title_en", "text", "single", ("source",),
                 "English title.", description_cy="teitl Saesneg"),
    PredicateDef("citation", "text", "single", ("source",),
                 "Full citation string.", description_cy="mynegai cyfeirio"),
    PredicateDef("url", "text", "single", ("source",),
                 "Canonical URL.", description_cy="URL canhwynol"),
    PredicateDef("organisation", "text", "single", ("source",),
                 "Authoring or holding organisation.", description_cy="sefydliad awduriaethol neu storfa"),
    PredicateDef("licence", "text", "single", ("source",),
                 "Licence — OGL, CC-BY-SA, internal, etc.", description_cy="trwydded — OGL, CC-BY-SA, mewnol, ac yn y blaen"),
    PredicateDef("accessed_at", "date", "single", ("source",),
                 "Most recent retrieval date.", description_cy="dyddiad agor mwyaf diweddar"),
    PredicateDef("file_hash", "text", "single", ("source",),
                 "SHA-256 of the evidence file, where applicable.", description_cy="SHA-256 y ffeil dystiolaeth, lle bo'n berthnasol"),
)

# ---------------------------------------------------------------------------
# Town predicates — applies to entity_type 'town'
# ---------------------------------------------------------------------------
_TOWN: tuple[PredicateDef, ...] = (
    PredicateDef("material_tradition", "bilingual", "multi", ("town",),
                 "The town's building-material tradition.", description_cy="traddodiad deunyddiau adeiladu'r dref"),
    PredicateDef("street_pattern", "bilingual", "single", ("town",),
                 "Narrative description of the town's street pattern.", description_cy="disgrifiad naratif o batrwm strydoedd y dref"),
    PredicateDef("notable_event", "bilingual", "multi", ("town",),
                 "A notable event in the town's history.", description_cy="digwyddiad nodedig yn hanes y dref"),
    PredicateDef("conservation_authority", "text", "single", ("town",),
                 "Local planning authority for conservation consent.", description_cy="awdurdod cynllunio lleol ar gyfer cydsynio cadwraeth"),
    PredicateDef("unitary_authority", "text", "single", ("town",),
                 "Council responsible for non-planning matters.", description_cy="cyngor unedol"),
    PredicateDef("listed_building_count", "int", "single", ("town",),
                 "Count of listed buildings in the town. v0.1-schema.md §3.5 "
                 "notes the count should record the date it was made; "
                 "'accessed_at' is not a §3.2 qualifier, so record that date "
                 "in the claim note or via the source until v0.2 resolves it.", description_cy="nifer yr adeiladau rhestredig yn y dref"),
    PredicateDef("parish", "text", "single", ("town",),
                 "Ecclesiastical parish, where relevant.", description_cy="plwyf eglwysig, lle bo'n berthnasol"),
)


# ---------------------------------------------------------------------------
# Energy-demand predicates (Egni M2) — applies to the existing 'area' and
# 'building' kinds. Registered per the ratified Egni decision note §2a as a
# deliberate, Prawf-logged post-bootstrap addition. description_cy=CY_PENDING
# until the Welsh forms are attested via the vocabulary harvest (identifiers
# stay English, descriptions are Welsh — never fabricated here).
# ---------------------------------------------------------------------------
_ENERGY_DEMAND: tuple[PredicateDef, ...] = (
    PredicateDef("electricity_consumption_kwh", "real", "single", ("area",),
                 "Annual electricity consumption for the small area, kWh "
                 "(DESNZ sub-national).", description_cy=CY_PENDING),
    PredicateDef("gas_consumption_kwh", "real", "single", ("area",),
                 "Annual gas consumption for the small area, kWh (DESNZ "
                 "sub-national) — settles where the gas grid actually reaches.",
                 description_cy=CY_PENDING),
    # multi: one claim per main-fuel class in the small area (Census TS046) —
    # the fuel label rides in value_en/value_cy, the percentage in value_real.
    # A single-cardinality predicate could hold only one fuel's share per area.
    PredicateDef("heating_fuel_share", "real", "multi", ("area",),
                 "Share of households by main heating fuel, per cent "
                 "(Census 2021 TS046); fuel carried in value_en/cy.",
                 description_cy=CY_PENDING),
    PredicateDef("main_fuel", "text", "single", ("building",),
                 "Main heating fuel of the dwelling, verbatim from EPC.",
                 description_cy=CY_PENDING),
)


# The complete seed set, in schema-document order; the Egni demand predicates
# (post-bootstrap, 2026-07-20) follow the v0.1 seed groups.
SEED_PREDICATES: tuple[PredicateDef, ...] = (
    _BUILDING + _TENANCY + _EVENT + _RESEARCH_QUESTION + _SOURCE + _TOWN
    + _ENERGY_DEMAND
)

# Name -> PredicateDef, for fast lookup by the validation contract.
PREDICATE_REGISTRY: dict[str, PredicateDef] = {
    p.name: p for p in SEED_PREDICATES
}

# Import-time invariant: a duplicate predicate name would silently shadow
# in PREDICATE_REGISTRY. 64 distinct names expected: 60 v0.1 seed (58 +
# §10 item 7's verified_building_toid + location_verification_status) plus
# the 4 Egni demand predicates (_ENERGY_DEMAND, 2026-07-20).
if len(PREDICATE_REGISTRY) != len(SEED_PREDICATES):
    raise RuntimeError("duplicate predicate name in SEED_PREDICATES")
