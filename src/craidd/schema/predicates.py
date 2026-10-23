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
(_ENERGY_DEMAND, 2026-07-20) take the total to 64, then the 34 ratified
2026-07-22 additions — 17 EPC (_EPC), 15 planning-lifecycle (_PLANNING),
2 BGS searches (_BGS_SEARCHES) — take it to 98. Registering them is a
deliberate, Prawf-logged post-bootstrap act, per the ratified Egni
decision note (egni/design/entity-kind-and-predicates-decision-note.md
§2a) and the three catalogue predicate-registration decision notes
(awen-source-catalogue/design/*-predicate-registration-decision-note.md,
ratified 2026-07-22). They all apply only to the existing
`area`/`building`/`event` kinds — no new entity kind, no constitution
change. The `site` kind the Egni note proposes is an M3 concern AND a
constitution machine-layer change (SCH-ENTITY-001 enumerates a closed
nine at the pinned v0.1.3), so it is deliberately NOT added here — see
the hand-off report.

NOTE — Welsh descriptions: the predicate table requires description_cy
NOT NULL, but §3.5 supplies English meanings only. Every description_cy
below is the tutor-attested form from the 2026-05-19 Catrin Stephens
session via the magic-link cards app — see
Awen-Weave/awen-cards/welsh-tutor-cards.yaml (each card's `chosen` block
carries the verified attestor + capture timestamp) and the session
export at Awen-Weave/awen-cards/sessions/2026-05-19-catrin-stephens.json.
CY_PENDING remains in this module as a placeholder for any future
predicate added before its Welsh form is attested.

NOTE — THE WELSH GAP IS A CONSTRAINT ON WHAT CAN BE EMITTED, NOT A
BACKLOG. Ruled by Huw as Llys 2026-08-31. Recorded here rather than only
in the build ledger, because this module is where a reader of the
registry meets the predicates themselves.

MEASURED at 0.2.20: **71 of 143 predicates carry no attested Welsh** —
every one of them the explicit CY_PENDING sentinel, and description_cy
is empty on NONE. At 0.2.15 it was 69 of 141. **Plus two predicates,
plus two pending: the gap grows with every addition rather than
closing**, and that delta is exactly the two predicates added since.

SO, PLAINLY: for an instance gated on bilingual parity — NWC-WLM-001 is
the live example — **a predicate whose description_cy is the pending
sentinel is UNEMITTABLE.** Not degraded, not emittable-with-a-caveat:
unemittable. **That currently applies to half this registry**, and to
every predicate the v0.1.6 climate increment delivered.

The sentence above the count is the one that misleads if read alone:
CY_PENDING is described as a placeholder for "any future predicate",
which reads as an edge case. It is the majority case.

HOW IT CLOSES IS DELIBERATELY NOT RECORDED HERE. Huw has deferred that
decision; attested Welsh comes from a tutor session, not from this
module, and nothing here proposes a plan or supplies a translation.

AND THIS NOTE HAS NO GUARD. A test asserting the count was explicitly
forbidden with the rest of the 2026-09-06 pause, so the number above
will drift as predicates are added and nothing will go red when it
does. Re-derive it from description_cy rather than trusting this line.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .grain import DECLARED_GRAINS, Grain

# decision_outcome's closed domain (P-2, Llys 04/10/2026 [sig:a40a1dcd]) and its export mapping onto
# MHCLG's binary decision codelist. split and withdrawn have no binary value, so they map to None:
# an exporter states them in its own words rather than forcing them into grant or refuse.
DECISION_OUTCOMES: tuple[str, ...] = ("granted", "refused", "split", "withdrawn")
_DECISION_OUTCOME_TO_MHCLG: dict[str, str | None] = {
    "granted": "grant", "refused": "refuse", "split": None, "withdrawn": None,
}


def decision_outcome_to_mhclg(value: str) -> str | None:
    """Map a decision_outcome value to MHCLG's binary `decision` codelist (grant | refuse) at export.

    Returns None for split and withdrawn, which the binary list cannot express. Raises ValueError
    for anything outside DECISION_OUTCOMES, so an off-domain value cannot leak out as a guess.
    """
    if value not in _DECISION_OUTCOME_TO_MHCLG:
        raise ValueError(f"decision_outcome value {value!r} is not one of {list(DECISION_OUTCOMES)}")
    return _DECISION_OUTCOME_TO_MHCLG[value]


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
    finest_grain         the FINEST grain this predicate's SOURCE supports
                         (phase 8, accepted by Huw as Llys 25/08/2026). A claim
                         may be at that grain or coarser, never finer. ABSENT
                         IS REFUSED FOR EVERY PREDICATE, with no exception:
                         `validate_predicate_def` refuses `Grain.UNDECLARED`
                         and `_assert_grain_declarations` refuses it again at
                         IMPORT. The default stays `Grain.UNDECLARED` so that
                         "absent" is a typed, refusable state rather than a
                         crash — it is not a wildcard and nothing forgives it.
    """

    name: str
    value_type: str
    cardinality: str
    applies_to_types: tuple[str, ...]
    description_en: str
    description_cy: str = CY_PENDING
    required_qualifiers: tuple[str, ...] = ()
    constraint_json: str | None = None
    finest_grain: Grain = Grain.UNDECLARED


# ---------------------------------------------------------------------------
# Building predicates — applies to entity_type 'building'
# ---------------------------------------------------------------------------
# PROPOSED, HOLD (cards c1272/c1281; Llefelys AWE-011 build item 2, Census profiles): the grain Huw
# countersigned on REQ-arloesidolgellau-7d070c [sig:607e58a8], said once and used by TS066 and TS067.
_LLEFELYS_GRAIN = (
    " Also SERVED at Welsh community (W04) grain for Llefelys (AWE-011) under the grain rule Huw "
    "countersigned on REQ-arloesidolgellau-7d070c [sig:607e58a8]: a community's figure is published only "
    "where it has at least 1,000 residents and 400 households, and smaller communities are shown merged "
    "with a neighbour or the wider area and labelled. A community figure is approximate: a best-fit sum "
    "of whole output areas (area_in_community). The output area values behind it are never served.")
# RATIFIED [sig:8e70be16] (card c1487; Llefelys AWE-011 phase 13 exit L1): the Welsh language tables reach the
# community grain only through the Llefelys transition naming them, DRAFT on awen-shared#998.
_LLEFELYS_WELSH_WAIT = (
    " For TS032 and TS033 that rule is extended by the Llefelys transition on REQ-arloesidolgellau-7d070c "
    "(awen-shared#998); until Huw countersigns it, no community figure from either table is served.")

_BUILDING: tuple[PredicateDef, ...] = (
    PredicateDef("address", "bilingual", "single", ("building",),
                 "Postal address.", description_cy="Cyfeiriad post",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("geometry", "geom", "single", ("building",),
                 "Building footprint or point.", description_cy="Geometreg yr adeilad - ôl troed yr adeilad",
        finest_grain=Grain.PROPERTY,
    ),
    # `text`, not `int`: a UPRN is an IDENTIFIER, never a quantity. Nothing adds
    # or averages one, its 12-digit width is significant, and every other part
    # of the estate already treats it as a string — place-anchor.schema.json
    # types it ["string","null"], the external-ref pattern is ^\d{12}$,
    # gazetteer.py str()s it, and returns.py emits it in value_text. It was
    # declared `int` here alone, which made every returnable UPRN claim
    # grammar-invalid the moment the build gate started checking the grammar
    # (27/07). Sibling identifier `listed_id` was already `text`.
    PredicateDef("uprn", "text", "single", ("building",),
                 "OS Unique Property Reference Number.", description_cy="Rhif Cyfeirnod Unigryw Eiddo (UPRN) yr OS",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("building_type", "text", "single", ("building",),
                 "Building type. v0.1-schema.md §3.5 marks this a controlled "
                 "enum but does not yet define the enum values.", description_cy="Math o adeilad",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("floor_area_m2", "real", "single", ("building",),
                 "Total internal floor area in square metres.", description_cy="Cyfanswm arwynebedd llawr mewnol mewn metrau sgwâr",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("build_year", "int", "single", ("building",),
                 "Year built — use only when the date is exact.", description_cy="Blwyddyn adeiladu — defnyddiwch dim ond pan fo'r dyddiad yn fanwl gywir",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("build_period", "text", "single", ("building",),
                 "Imprecise build period, e.g. 'c.1885', 'late C18'.",
                 required_qualifiers=("date_precision",), description_cy="Cyfnod adeiladu yn fras",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("original_use", "bilingual", "multi", ("building",),
                 "Historic primary use(s).", description_cy="Defnydd(iau) gwreiddiol",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("current_use", "bilingual", "single", ("building",),
                 "Today's primary use.", description_cy="Defnydd presennol",
        finest_grain=Grain.PROPERTY,
    ),
    # P-1 (Llys 04/10/2026 [sig:a40a1dcd], decision 8a): also binds to `site`. listed_id does NOT
    # (decision 8b): it is returnable, so widening it is a returns ruling first.
    PredicateDef("listed_grade", "text", "single", ("building", "site"),
                 "Statutory listing grade.",
                 constraint_json='{"enum": ["I", "II*", "II"]}', description_cy="Gradd restredig statudol",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("listed_id", "text", "multi", ("building",),
                 "Cadw or British Listed Buildings register reference. "
                 "Multi-cardinality: a building may carry several.", description_cy="Cyfeirnod cofrestr Cadw neu adeiladau rhestredig Prydain",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("conservation_area", "text", "multi", ("building", "site"),   # P-1, decision 8a
                 "Conservation area(s) the building or development site sits within.",
                 description_cy="Ardal gadwraeth",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("name_cy", "text", "multi", ("building",),
                 "Welsh name. Multi-cardinality; every claim must carry a "
                 "name_type qualifier.",
                 required_qualifiers=("name_type",), description_cy="Enw Cymraeg",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("name_en", "text", "multi", ("building",),
                 "English name. Multi-cardinality; every claim must carry a "
                 "name_type qualifier.",
                 required_qualifiers=("name_type",), description_cy="Enw Saesneg",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("historical_note", "bilingual", "multi", ("building",),
                 "Free-text historical claim.", description_cy="Nodyn hanesyddol — testun rhydd",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("architectural_description", "bilingual", "multi", ("building",),
                 "Structured architectural detail.", description_cy="Disgrifiad pensaernïol strwythuredig",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("material_primary", "text", "single", ("building",),
                 "Primary external wall material, e.g. 'snecked rubble "
                 "dolerite'.", description_cy="Prif ddeunydd wal allanol",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("roof_type", "text", "single", ("building",),
                 "Roof form and material, e.g. 'hipped slate'.", description_cy="Math o do — ffurf a deunydd",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("storeys", "int", "single", ("building",),
                 "Number of full storeys.", description_cy="Nifer y lloriau llawn",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("adjacent_to", "entity_ref", "multi", ("building",),
                 "Another building physically adjacent to this one.", description_cy="Adeilad arall sy'n gyfagos yn gorfforol i hwn",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("contemporary_with", "entity_ref", "multi", ("building",),
                 "A building of the same construction period.", description_cy="Adeilad o'r un cyfnod adeiladu",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("group_value_with", "entity_ref", "multi", ("building",),
                 "A building whose listing reason is shared or related "
                 "(listed 'group value').", description_cy="Adeilad sy'n rhannu rheswm rhestru (gwerth grŵp)",
        finest_grain=Grain.PROPERTY,
    ),
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
    
        finest_grain=Grain.PROPERTY,
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
        description_cy="Statws gwirio lleoliad — band sy'n deillio o honiadau byw a haen ddarlledu Lleolydd",
        required_qualifiers=("cache_snapshot_id",),
        constraint_json=(
            '{"enum": ["verified", "auto-snapped", "unsnapped", '
            '"contested", "non-postal"]}'
        ),
    
        finest_grain=Grain.PROPERTY,
    ),
)

# ---------------------------------------------------------------------------
# Tenancy predicates — applies to entity_type 'tenancy'
# ---------------------------------------------------------------------------
_TENANCY: tuple[PredicateDef, ...] = (
    PredicateDef("tenancy_of", "entity_ref", "single", ("tenancy",),
                 "The building (or area) this tenancy occupies.", description_cy="Yr adeilad (neu'r ardal) y mae'r denantiaeth hon yn ei feddiannu",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("tenant_name", "text", "single", ("tenancy",),
                 "Common name of the tenant.", description_cy="Enw cyffredin y tenant",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("tenant_organisation", "text", "single", ("tenancy",),
                 "Formal organisation name, where applicable.", description_cy="Enw'r sefydliad yn ffurfiol, lle bo'n berthnasol",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("tenancy_type", "text", "single", ("tenancy",),
                 "Tenancy type.",
                 constraint_json='{"enum": ["commercial_retail", '
                 '"commercial_wholesale", "residential", "office", '
                 '"hospitality", "community", "mixed", "vacant", "other"]}', description_cy="Math o denantiaeth",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("tenant_business_type", "bilingual", "single", ("tenancy",),
                 "Nature of the tenant's business, e.g. 'newsagents and "
                 "bookshop'.", description_cy="Natur busnes y tenant, e.e. 'siop bapurau newydd a llyfrau'",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("period_start", "date", "single", ("tenancy",),
                 "Earliest plausible start of the tenancy.",
                 required_qualifiers=("date_precision",), description_cy="Dechrau cynharaf credadwy y denantiaeth",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("period_end", "date", "single", ("tenancy",),
                 "Earliest plausible end of the tenancy; null means current.",
                 required_qualifiers=("date_precision",), description_cy="Diwedd cynharaf credadwy y denantiaeth; gadael yn wag ar gyfer tenantiaeth cyfredol",
        finest_grain=Grain.NOT_SPATIAL,
    ),
)

# ---------------------------------------------------------------------------
# Event predicates — applies to entity_type 'event'
# ---------------------------------------------------------------------------
_EVENT: tuple[PredicateDef, ...] = (
    PredicateDef("event_type", "text", "single", ("event",),
                 "Event type.",
                 constraint_json='{"enum": ["refurbishment", "designation", '
                 '"change_of_use", "sale", "construction", "demolition", '
                 '"fire", "flood", "other"]}', description_cy="Math o ddigwyddiad",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("event_start", "date", "single", ("event",),
                 "Event start date.",
                 required_qualifiers=("date_precision",), description_cy="Dyddiad dechrau'r digwyddiad",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("event_end", "date", "single", ("event",),
                 "Event end date; null means ongoing.",
                 required_qualifiers=("date_precision",), description_cy="Dyddiad diwedd y digwyddiad; gadael yn wag ar gyfer digwyddiad cyfredol",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("affects_entity", "entity_ref", "multi", ("event",),
                 "An entity this event acts upon.", description_cy="Endid y mae'r digwyddiad hwn yn ei effeithio",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("funder", "entity_ref", "multi", ("event",),
                 "A funder, where the funder is itself a recorded entity.", description_cy="Arianwr, lle bo'r arianwr ei hun yn endid sydd wedi'i gofnodi",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("funder_text", "text", "multi", ("event",),
                 "A funder, where recorded as a string only.", description_cy="Arianwr, lle'i nodir fel llinyn yn unig",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("scope_description", "bilingual", "single", ("event",),
                 "What the event did.", description_cy="Disgrifiad y digwyddiad - beth wnaeth y digwyddiad",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("consent_reference", "text", "multi", ("event",),
                 "Listed-building-consent, planning, or designation reference.", description_cy="Cyfeirnod cydsynio adeilad rhestredig, cynllunio, neu ddynodi",
        finest_grain=Grain.NOT_SPATIAL,
    ),
)

# ---------------------------------------------------------------------------
# Research-question predicates — applies to entity_type 'research_question'
# ---------------------------------------------------------------------------
_RESEARCH_QUESTION: tuple[PredicateDef, ...] = (
    PredicateDef("question_text", "bilingual", "single", ("research_question",),
                 "The research question itself.", description_cy="Y cwestiwn ymchwil ei hun",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("relates_to_entity", "entity_ref", "multi",
                 ("research_question",),
                 "An entity the question is about.", description_cy="Pwnc y mae'r cwestiwn yn ei gylch",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("suggested_sources", "text", "multi", ("research_question",),
                 "Where to look — free text.", description_cy="Ble i edrych — testun rhydd",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("priority", "text", "single", ("research_question",),
                 "Question priority.",
                 constraint_json='{"enum": ["low", "medium", "high"]}', description_cy="Blaenoriaeth cwestiwn",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("status", "text", "single", ("research_question",),
                 "Question status.",
                 constraint_json='{"enum": ["open", "in_progress", '
                 '"answered", "abandoned"]}', description_cy="Statws cwestiwn",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("answered_by_claim", "text", "single", ("research_question",),
                 "claim_id of the claim that resolved the question.", description_cy="claim_id yr honiad a ddatrysodd y cwestiwn",
        finest_grain=Grain.NOT_SPATIAL,
    ),
)

# ---------------------------------------------------------------------------
# Source predicates — applies to entity_type 'source'
# ---------------------------------------------------------------------------
# The closed domain of `source_kind` (constitution 0.1.9, Llys 01/10/2026, placement A). READ from the
# vendored SCH-ENTITY-001 $defs.source_kind, never typed here, so the grammar cannot drift from the
# constitution (task 4.1 proposal section 2.3). A missing or malformed vendor copy fails at import.
_VENDORED_ENTITY_SCHEMA = (Path(__file__).resolve().parent.parent / "constitution_vendor" / "schema"
                           / "entity.schema.json")


def _vendored_source_kinds() -> tuple[str, ...]:
    enum = json.loads(_VENDORED_ENTITY_SCHEMA.read_text(encoding="utf-8"))["$defs"]["source_kind"]["enum"]
    if not enum or len(set(enum)) != len(enum) or not all(isinstance(v, str) and v for v in enum):
        raise RuntimeError(f"vendored $defs.source_kind is malformed: {enum!r}")
    return tuple(enum)


SOURCE_KINDS: tuple[str, ...] = _vendored_source_kinds()

_SOURCE: tuple[PredicateDef, ...] = (
    PredicateDef("title_cy", "text", "single", ("source",),
                 "Welsh title, where applicable.", description_cy="Teitl Cymraeg, lle bo'n berthnasol",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("title_en", "text", "single", ("source",),
                 "English title.", description_cy="Teitl Saesneg",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("citation", "text", "single", ("source",),
                 "Full citation string.", description_cy="Mynegai cyfeirio",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("url", "text", "single", ("source",),
                 "Canonical URL.", description_cy="URL canhwynol",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("organisation", "text", "single", ("source",),
                 "Authoring or holding organisation.", description_cy="Sefydliad awduriaethol neu storfa",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("licence", "text", "single", ("source",),
                 "Licence — OGL, CC-BY-SA, internal, etc.", description_cy="Trwydded — OGL, CC-BY-SA, mewnol, ac yn y blaen",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("accessed_at", "date", "single", ("source",),
                 "Most recent retrieval date.", description_cy="Dyddiad agor mwyaf diweddar",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("file_hash", "text", "single", ("source",),
                 "SHA-256 of the evidence file, where applicable.", description_cy="SHA-256 y ffeil dystiolaeth, lle bo'n berthnasol",
        finest_grain=Grain.NOT_SPATIAL,
    ),
    # Constitution 0.1.9 (Llys 02/10/2026 [sig:ca783ae5]). POL-TIERAB-001's `source.kind`, resolved
    # through a claim's source_id to this predicate. Closed domain read from the vendored $defs.
    # validate_claim refuses an off-domain value (for this predicate only; decision 7). Welsh is
    # PENDING, never self-attested, so it is unemittable by a bilingual-parity instance until a tutor
    # attests it (Llys 31/08/2026; task 4.1 Class A pass N3).
    PredicateDef("source_kind", "text", "single", ("source",),
                 "The kind of source, one of the six in SCH-ENTITY-001 $defs.source_kind: observation, "
                 "open-dataset, cross-reference, learning, commercial, proprietary. Drives POL-TIERAB-001's "
                 "Tier A eligibility; an absent kind is not eligible.",
                 constraint_json=json.dumps({"enum": list(SOURCE_KINDS)}),
        finest_grain=Grain.NOT_SPATIAL,
    ),
)

# ---------------------------------------------------------------------------
# Town predicates — applies to entity_type 'town'
# ---------------------------------------------------------------------------
_TOWN: tuple[PredicateDef, ...] = (
    PredicateDef("material_tradition", "bilingual", "multi", ("town",),
                 "The town's building-material tradition.", description_cy="Traddodiad deunyddiau adeiladu'r dref",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("street_pattern", "bilingual", "single", ("town",),
                 "Narrative description of the town's street pattern.", description_cy="Disgrifiad naratif o batrwm strydoedd y dref",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("notable_event", "bilingual", "multi", ("town",),
                 "A notable event in the town's history.", description_cy="Digwyddiad nodedig yn hanes y dref",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("conservation_authority", "text", "single", ("town",),
                 "Local planning authority for conservation consent.", description_cy="Awdurdod cynllunio lleol ar gyfer cydsynio cadwraeth",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("unitary_authority", "text", "single", ("town",),
                 "Council responsible for non-planning matters.", description_cy="Cyngor unedol",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("listed_building_count", "int", "single", ("town",),
                 "Count of listed buildings in the town. v0.1-schema.md §3.5 "
                 "notes the count should record the date it was made; "
                 "'accessed_at' is not a §3.2 qualifier, so record that date "
                 "in the claim note or via the source until v0.2 resolves it.", description_cy="Nifer yr adeiladau rhestredig yn y dref",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("parish", "text", "single", ("town",),
                 "Ecclesiastical parish, where relevant.", description_cy="Plwyf eglwysig, lle bo'n berthnasol",
        finest_grain=Grain.AREA,
    ),
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
                 "(DESNZ sub-national).", description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("gas_consumption_kwh", "real", "single", ("area",),
                 "Annual gas consumption for the small area, kWh (DESNZ "
                 "sub-national) — settles where the gas grid actually reaches.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    # Ratified Llys 09/08/2026 [sig:7577b7d1 clearance / energy-grammar-rulings]. Adopt-and-cite
    # DESNZ's own official statistics; statistical-indicator shape (RDF Data Cube / SDMX). Both
    # are counts on the place grain (area→gazetteer GSS); awen-weave-minor, no Tier-1 change.
    PredicateDef("off_gas_grid_properties", "int", "single", ("area",),
                 "Count of domestic properties NOT connected to the mains gas network in the "
                 "area (DESNZ estimates). The mains-gas-footprint complement to "
                 "gas_consumption_kwh — the off-gas-grid / heat-transition case. Vintage in the "
                 "citation; VERIFY-AT-REGISTRATION the LSOA vintage (LSOA21 spine vs source).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("energy_efficiency_measures_installed", "int", "single", ("area",),
                 "Count of home energy-efficiency measures installed under ECO / Green Deal in "
                 "the area (DESNZ Household Energy Efficiency). An absolute count; vintage in "
                 "the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    # multi: one claim per main-fuel class in the small area (Census TS046) —
    # the fuel label rides in value_en/value_cy, the percentage in value_real.
    # A single-cardinality predicate could hold only one fuel's share per area.
    PredicateDef("heating_fuel_share", "real", "multi", ("area",),
                 "Share of households by main heating fuel, per cent "
                 "(Census 2021 TS046); fuel carried in value_en/cy.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    # Census 2021 OA tables (phase 9, card c0628; Llys 09/10/2026 15:23:55Z [sig:8ea7c020] keeps them
    # in phase 9; register REQ-arloesidolgellau-7d070c). PROPOSED in awen-weave 0.2.31 through the one
    # gate. The category rides value_en/value_cy, as heating_fuel_share's fuel does; no qualifier.
    PredicateDef("usual_residents_count", "int", "multi", ("area",),
                 "Census 2021 count of usual residents in an area, for the category or five-year "
                 "age band named in value_en / value_cy (TS001: all usual residents, in households, "
                 "in communal establishments; TS007A: age bands). A census-day COUNT, not the ONS "
                 "mid-year estimate: that is population_estimate, and the two are never mixed in one "
                 "series. An absolute count; vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("households_car_van_availability_count", "int", "multi", ("area",),
                 "Census 2021 count of households in an area by car or van availability, for the "
                 "category named in value_en / value_cy (TS045: no cars or vans, one, two, three or "
                 "more). Counts households, not vehicles or people. An absolute count; vintage in "
                 "the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    # Census 2021 wave 2 OA tables (card c0840; awen-shared PROPOSAL-census-wave-2-2026-10-11.md, card
    # c0826). Huw's 10/10/2026 rulings: Q1, one predicate per further table, named after its subject;
    # Q2, one generated batch after the measured table list. PROPOSED in awen-weave 0.2.32 through the
    # one gate. Wave 1's form: the category rides value_en/value_cy; no qualifier.
    PredicateDef("households_central_heating_count", "int", "multi", ("area",),
                 "Census 2021 count of households in an area by type of central heating, for the "
                 "category named in value_en / value_cy (TS046: no central heating, mains gas only, "
                 "electric only, oil only, renewable energy only, two or more types, and the rest, "
                 "VERBATIM from ONS). An absolute count of households; not heating_fuel_share, the "
                 "per-cent share of the same table at LSOA. Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("households_tenure_count", "int", "multi", ("area",),
                 "Census 2021 count of households in an area by tenure, for the leaf category named "
                 "in value_en / value_cy (TS054: owns outright, owns with a mortgage or loan, shared "
                 "ownership, social rented from the council or other, private rented, lives rent "
                 "free; VERBATIM from ONS, subtotals not carried). An area count, not the EPC "
                 "building-level tenure predicate. Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("households_accommodation_type_count", "int", "multi", ("area",),
                 "Census 2021 count of households in an area by accommodation type, for the category "
                 "named in value_en / value_cy (TS044: detached, semi-detached, terraced, flats, "
                 "converted or shared houses, commercial buildings, caravans; VERBATIM from ONS). "
                 "Counts households, not dwellings. Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("household_spaces_by_size_count", "int", "multi", ("area",),
                 "Census 2021 count of household spaces in an area by the number of people in the "
                 "household, for the category named in value_en / value_cy (TS017: 0 people to 8 or "
                 "more). Its universe is household spaces, so '0 people in household' counts empty "
                 "spaces: it is not a count of households. Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("usual_residents_economic_activity_count", "int", "multi", ("area",),
                 "Census 2021 count of usual residents aged 16 years and over in an area by economic "
                 "activity status, for the leaf category named in value_en / value_cy (TS066: in "
                 "employment, unemployed, full-time students, retired, looking after home or family, "
                 "long-term sick or disabled, other; VERBATIM from ONS, subtotals not carried). "
                 "SERVED for general use at LSOA only (Huw 12/10/2026 [sig:691127c0]); the output "
                 "area grain is built for Lludd (AWE-009) alone and is not served openly." + _LLEFELYS_GRAIN
                 + " Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("households_count", "int", "single", ("area",),
                 "Census 2021 number of households in an area (TS041), one figure per area: the base "
                 "the Census 2021 household tables are checked against. Each table is perturbed "
                 "separately by ONS, so another table's total may differ by a few. Vintage in the "
                 "citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("main_fuel", "text", "single", ("building",),
                 "Main heating fuel of the dwelling, verbatim from EPC.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Hydrology predicates (Axis A, constitution 0.1.5) — observations on the new
# `station` entity kind (SCH-ENTITY-001, INSPIRE EnvironmentalMonitoringFacility).
# Ratified Llys 06/08/2026 [sig:c659a12f]. ADOPT-AND-CITE the recognised standards
# rather than invent: value carries a SOSA/O&M observation result; each predicate maps
# to an EA `op:` observed-property (namespace http://environment.data.gov.uk/reference/def/op/),
# a GCOS Essential Climate Variable, and a QUDT unit; the wire form is WaterML 2.0. Claims
# are `binding=measured` (set at registration in the catalogue module, not here); the spine
# is the gazetteer GSS via the station's containing authority (gp-locations precedent).
# description_cy=CY_PENDING — not yet Catrin-attested (identifiers stay English regardless).
# Until 26/09/2026 this comment said the Welsh forms were on the vocabulary-harvest worklist;
# they were not (424 pass, N5). The five are added to the worklist with constitution 0.1.8.
#
# CONSTITUTION 0.1.8 (Llys 26/09/2026 [sig:c8426dc4], dispatch 428):
#   - `tide_level` joins the block (Climate's 19/09 ask, Option C);
#   - `vertical_datum` (CLOSED, qualifiers.py) is REQUIRED on `tide_level` and `water_level`,
#     enforced here via required_qualifiers — not by the constitution schema (424 pass, N1). A
#     producer derives it from the publisher's unit through schema/vertical_datum.py, never types it;
#   - ALL FIVE are cardinality `multi` (B4): the 06/08 ratified text said "a site carries a time
#     series, distinguished by observation time"; the registry had drifted to `single`. Re-checked
#     26/09 before switching: no claim on any of the five exists in any repo or local store.
# ---------------------------------------------------------------------------
_HYDROLOGY: tuple[PredicateDef, ...] = (
    PredicateDef("water_flow", "real", "multi", ("station",),
                 "River discharge (volumetric flow) at a monitoring station. EA op: waterFlow; "
                 "GCOS ECV River Discharge; QUDT unit CubicMeterPerSecond (m3/s); SOSA/O&M "
                 "observation result; WaterML 2.0. Adopt-and-cite EA Hydrology, licence OGL v3.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("water_level", "real", "multi", ("station",),
                 "Water / river stage (level) at a monitoring station. EA op: waterLevel; "
                 "QUDT unit Meter (m), relative to the claim's `vertical_datum`; SOSA/O&M "
                 "observation result; WaterML 2.0. Adopt-and-cite EA Hydrology, licence OGL v3.",
                 required_qualifiers=("vertical_datum",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("rainfall", "real", "multi", ("station",),
                 "Precipitation depth at a monitoring station. EA op: rainfall; GCOS ECV "
                 "Precipitation; QUDT unit Millimetre (mm); SOSA/O&M observation result; "
                 "WaterML 2.0. Adopt-and-cite EA Hydrology, licence OGL v3.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("groundwater_level", "real", "multi", ("station",),
                 "Groundwater level at a monitoring station. EA op: groundwaterLevel; GCOS ECV "
                 "Groundwater; QUDT unit Meter (mAOD); SOSA/O&M observation result; WaterML 2.0. "
                 "Adopt-and-cite EA Hydrology, licence OGL v3.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("tide_level", "real", "multi", ("station",),
                 "Sea surface height at a tide gauge, relative to the datum named by the claim's "
                 "`vertical_datum` qualifier. Adopt-and-cite: EA flood-monitoring measure "
                 "parameter `level`, qualifier `Tidal Level`; GCOS ECV Sea Level; QUDT unit Meter "
                 "(m); SOSA/O&M observation result. A separate predicate from water_level so a "
                 "tide series and a river series at one station are never summed as one. NRW "
                 "tide gauges as served (mAOD). Constitution 0.1.8, Llys 26/09/2026.",
                 required_qualifiers=("vertical_datum",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# EPC domestic predicates (IDR-006 EPC national layer) — per-certificate on the
# existing 'building' kind + one per-authority 'area' aggregate. Additive, no
# constitution change (EPC predicate-registration decision note, ratified
# 2026-07-22). Verbatim EPC classes, never re-bucketed; 'uprn'/'main_fuel'
# already registered (not re-added). description_cy=CY_PENDING (harvest).
# ---------------------------------------------------------------------------
_EPC: tuple[PredicateDef, ...] = (
    PredicateDef("epc_location", "geom", "single", ("building",),
                 "Point location of the assessed dwelling — the UPRN spine's "
                 "coordinate (EPSG:4326), never a Royal Mail address.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("current_energy_rating", "text", "single", ("building",),
                 "Current energy-efficiency band (A–G), verbatim from the EPC.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("potential_energy_rating", "text", "single", ("building",),
                 "Potential energy-efficiency band after recommended "
                 "improvements, verbatim.", description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("current_energy_efficiency", "int", "single", ("building",),
                 "Current energy-efficiency score (SAP points, 1–100).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("potential_energy_efficiency", "int", "single", ("building",),
                 "Potential energy-efficiency score after improvements.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("environment_impact_current", "int", "single", ("building",),
                 "Current environmental-impact (CO₂) score.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("environment_impact_potential", "int", "single", ("building",),
                 "Potential environmental-impact score after improvements.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("co2_emissions_current", "real", "single", ("building",),
                 "Current CO₂ emissions, per the EPC (tonnes/yr or "
                 "per-floor-area as sourced).", description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("total_floor_area", "real", "single", ("building",),
                 "Total floor area (m²), verbatim from the EPC (distinct from "
                 "the survey 'floor_area_m2').", description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("property_type", "text", "single", ("building",),
                 "Dwelling type (House/Flat/Bungalow/Maisonette), verbatim.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("built_form", "text", "single", ("building",),
                 "Built form (Detached/Semi/Terrace/…), verbatim.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("tenure", "text", "single", ("building",),
                 "Tenure at assessment (owner-occupied / rented …), verbatim.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("mainheat_description", "text", "single", ("building",),
                 "Main heating system descriptor, verbatim.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("inspection_date", "date", "single", ("building",),
                 "Date the assessment was carried out.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("lodgement_date", "date", "single", ("building",),
                 "Date the certificate was lodged on the register.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("epc_recommendation", "text", "multi", ("building",),
                 "An improvement measure recommended on the certificate (one "
                 "claim per measure).", description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("epc_certificate_count", "int", "single", ("area",),
                 "Count of addressless domestic EPC certificates joined to the "
                 "UPRN spine in the authority (derived aggregate; the full "
                 "per-certificate set is the box full-store).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Planning-lifecycle predicates (AWE-006 Tref) — on the existing 'event' kind,
# bound to a 'building' via the already-registered 'affects_entity'. Names/enums
# mirror the MHCLG national planning-decision spec (adopt, don't invent).
# Additive, no constitution change (planning predicate-registration decision
# note, ratified 2026-07-22). description_cy=CY_PENDING (harvest).
# ---------------------------------------------------------------------------
_PLANNING: tuple[PredicateDef, ...] = (
    PredicateDef("application_reference", "text", "single", ("event",),
                 "The planning application reference, verbatim from the "
                 "authority (the PK; authority is the record of truth).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("lpa", "text", "single", ("event",),
                 "Local planning authority name (GSS where an LA; NPAs resolve "
                 "via boundary).", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("application_type", "text", "single", ("event",),
                 "Application type, verbatim (Full / Outline / Tree works / …).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("application_status", "text", "single", ("event",),
                 "Application status, verbatim from the authority portal.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("received_date", "date", "single", ("event",),
                 "Date the LPA first received the application (the "
                 "timeliness/deadline basis).", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("valid_date", "date", "single", ("event",),
                 "Date the application was made valid.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    # P-2 (Llys 04/10/2026 [sig:a40a1dcd], decision 9): the enum the description always stated is now
    # the predicate's closed domain, and validate_claim refuses a value outside it (an appeal outcome
    # such as 'dismissed' belongs in appeal_outcome). Taken only after Mac 6's estate search (04/10)
    # found every held value inside it. Kept at four values because MHCLG's binary decision codelist
    # (grant | refuse) cannot say split or withdrawn; decision_outcome_to_mhclg() maps at export.
    PredicateDef("decision_outcome", "text", "single", ("event",),
                 "Decision outcome mapped to the MHCLG enum "
                 "(granted/refused/split/withdrawn); raw text kept, never "
                 "re-bucketed away: the authority's own wording travels in "
                 "semantics_caveat.", description_cy=CY_PENDING,
                 constraint_json=json.dumps({"enum": list(DECISION_OUTCOMES)}),
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("decided_by", "text", "single", ("event",),
                 "WHO decided — officer / committee / inspectorate (the MHCLG "
                 "first-class provenance field; None when the source doesn't "
                 "state it — recorded honestly, never guessed).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("decision_date", "date", "single", ("event",),
                 "Date of the decision notice.", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("condition_discharge_status", "text", "single", ("event",),
                 "A condition's discharge status "
                 "(imposed/discharged/not_discharged/unknown) — the line of "
                 "sight from imposition → discharge → works.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("appeal_outcome", "text", "single", ("event",),
                 "PINS appeal outcome (allowed/dismissed/split) — from Open "
                 "Evidence appeals_corpus (v0.2).", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("works_evidence", "text", "single", ("event",),
                 "Did-it-happen confidence (confirmed/likely/unknown) — "
                 "permission granted is NOT evidence of works; the kind + basis "
                 "ride in the semantics_caveat.", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("site_toid", "text", "single", ("event",),
                 "The bound building's OS TOID — from OS Open Linked "
                 "Identifiers (OGL) via the UPRN spine, NOT MasterMap; part of "
                 "the returnable UPRN/TOID bind.", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("source_url", "text", "single", ("event",),
                 "The authoritative authority record URL (per-application "
                 "provenance; the record of truth).", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("fetch_hash", "text", "single", ("event",),
                 "Content hash of the fetched source record (verify-not-recall "
                 "audit).", description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
)


# ---------------------------------------------------------------------------
# BGS searches predicates (Sail-Sale, for Evan) — per-UPRN indicative class on
# the existing 'building' kind, binding: asserted. Verbatim BGS class; the
# meaning-limit rides in semantics_caveat. Additive, no constitution change
# (BGS-searches predicate-registration decision note, ratified 2026-07-22).
# ---------------------------------------------------------------------------
_BGS_SEARCHES: tuple[PredicateDef, ...] = (
    PredicateDef("mining_hazard", "text", "single", ("building",),
                 "BGS non-coal mining-hazard indicative class covering the "
                 "property (NA / Low / Moderate / Significant), verbatim from "
                 "the BGS 1 km hex. Indicative likelihood, not a site "
                 "investigation; coal is a separate regime (Mining Remediation "
                 "Authority).", description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("radon_potential", "int", "single", ("building",),
                 "UKHSA/BGS radon potential class 1–6 for the property's "
                 "location (estimated % of homes above the radon action level; "
                 "1 = lowest <1%, 6 = highest ≥30%). An area indication, not a "
                 "measured dwelling radon level.", description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Heritage-designation search predicates (Sail-Sale Tier-A A1, LLC1) — per-UPRN
# on the existing 'building' kind, binding: asserted. OGL (Historic England NHLE
# + Cadw). Value = the designation's verbatim list-entry reference (factual core;
# rich descriptive text stays VERIFY). LISTED BUILDINGS reuse the existing
# `listed_grade` + `listed_id`; CONSERVATION AREAS reuse `conservation_area` — so
# only scheduled monuments, registered parks/gardens and battlefields are new here.
# Additive, no constitution change (mirrors the ratified BGS-searches pattern).
# Welsh: CY_PENDING — the four description_cy forms are on Catrin's harvest worklist
# (VH-FUT-060..063); Cadw publishes official Welsh designation terms (select-and-attest).
# ---------------------------------------------------------------------------
_HERITAGE_SEARCHES: tuple[PredicateDef, ...] = (
    PredicateDef("within_scheduled_monument", "text", "multi", ("building",),
                 "Scheduled monument whose designated area contains the property "
                 "— verbatim list-entry reference (Historic England NHLE / Cadw). "
                 "The OGL designation fact; descriptive text held VERIFY.",
                 description_cy="O fewn heneb gofrestredig",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("near_scheduled_monument_250m", "text", "multi", ("building",),
                 "DEPRECATED (2026-07-24, superseded by `near_scheduled_monument` "
                 "with a setting-scale-derived radius; not emitted). Kept for additive "
                 "discipline — a fixed 250 m is a poor proxy for a monument's setting. "
                 "Scheduled monument(s) within 250 m of the property.",
                 description_cy="O fewn 250 m i heneb gofrestredig",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("near_scheduled_monument", "text", "multi", ("building",),
                 "Scheduled monument(s) near the property (within the monument's "
                 "setting-scale-derived radius) — verbatim list-entry reference. A "
                 "proximity indication for a search, NOT a statement the property is "
                 "designated. The applied radius scales with the monument's designated "
                 "area (see `setting_scale` / `designated_area_ha`).",
                 description_cy="Yn agos at heneb gofrestredig (o fewn dalgylch ei gosodiad)",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("in_registered_park_garden", "text", "multi", ("building",),
                 "Registered park or garden of special historic interest "
                 "containing the property — verbatim list-entry reference "
                 "(NHLE / Cadw).", description_cy="O fewn parc a gardd hanesyddol gofrestredig",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("in_registered_battlefield", "text", "single", ("building",),
                 "Registered battlefield containing the property — verbatim "
                 "list-entry reference (NHLE; England only).",
                 description_cy="O fewn maes brwydr cofrestredig",
        finest_grain=Grain.PROPERTY,
    ),
    # Ratified 11/08 [Llys R1+R2 ACCEPT, welsh-heritage-predicates-ruling] — additive, within-only,
    # fold into the heritage-designations composite (Cadw, Wales). within_protected_wreck was HELD
    # (marine). Welsh CY_PENDING → Catrin harvest (safle treftadaeth y byd / tirwedd hanesyddol
    # gofrestredig). Anchors: Cadw / Cof Cymru; Historic Environment (Wales) Act 2016; UNESCO WH
    # Convention (WHS); OGL v3.0.
    PredicateDef("within_world_heritage_site", "text", "multi", ("building",),
                 "World Heritage Site whose inscribed area contains the property — verbatim "
                 "reference (UNESCO ref / site name; Cadw). The OGL designation fact; descriptive "
                 "text held VERIFY.",
                 description_cy="O fewn safle treftadaeth y byd",
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("within_registered_historic_landscape", "text", "multi", ("building",),
                 "Registered historic landscape containing the property — verbatim Cadw "
                 "reference (landscape-scale; a within-flag, not a proximity flag). The OGL "
                 "designation fact.",
                 description_cy="O fewn tirwedd hanesyddol gofrestredig",
        finest_grain=Grain.PROPERTY,
    ),
    # Ratified with the two above by Huw as Llys 01/09/2026 [sig:57ce9e14] ("Wrecks are NOT held");
    # 0.2.16 registered only two. Registered in 0.2.30 (phase 9 task 9.6, card c0615). Same
    # within-only shape; Welsh term to Catrin. Anchors: Cadw; Protection of Wrecks Act 1973; OGL v3.0.
    PredicateDef("within_protected_wreck", "text", "multi", ("building",),
                 "Protected wreck site (restricted area designated under the Protection of "
                 "Wrecks Act 1973) containing the property — verbatim Cadw reference. A "
                 "within-flag, not a proximity flag. The OGL designation fact.",
                 description_cy="O fewn llongddrylliad gwarchodedig",
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Heritage-designation ENRICHMENT predicates (Sail-Sale A1). The designated asset
# itself becomes an `area` entity (keyed by its list-entry reference), carrying what
# the authority publishes about it — so the dataset says WHAT the asset is, not just
# that it's near. heritage_class / heritage_site_type / heritage_period /
# designated_area_ha are ASSERTED (verbatim: Cadw BroadClass/SiteType/Period; the
# polygon area). `setting_scale` is DERIVED (binding: derived on the claim) — Awen's
# curated tier inferred from the area, kept distinct from the authority's facts.
# Welsh: CY_PENDING (VH-FUT-064..068 on Catrin's worklist).
# ---------------------------------------------------------------------------
_HERITAGE_ENRICHMENT: tuple[PredicateDef, ...] = (
    PredicateDef("heritage_class", "text", "single", ("area",),
                 "Broad class of a designated heritage asset, verbatim from the "
                 "authority (e.g. Cadw BroadClass 'Religious, Ritual and Funerary').",
                 description_cy="Dosbarth treftadaeth",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("heritage_site_type", "text", "single", ("area",),
                 "Site type of a designated heritage asset, verbatim (Cadw SiteType).",
                 description_cy="Math o safle treftadaeth",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("heritage_period", "text", "single", ("area",),
                 "Historic period of a designated heritage asset, verbatim (Cadw Period).",
                 description_cy="Cyfnod hanesyddol",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("designated_area_ha", "real", "single", ("area",),
                 "Designated area of a heritage asset in hectares (the polygon area) — "
                 "the objective scale signal for its setting.", description_cy="Arwynebedd dynodedig (hectarau)",
        finest_grain=Grain.AREA,
    ),
    PredicateDef("setting_scale", "text", "single", ("area",),
                 "DERIVED curated setting-scale tier (immediate | local | landscape) "
                 "inferred from designated_area_ha — Awen's judgment, emitted "
                 "binding=derived, NOT the authority's statement.",
                 description_cy="Graddfa gosodiad",
                 constraint_json='{"enum": ["immediate", "local", "landscape"]}',
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# Coal-mining search predicate (Sail-Sale Tier-A A3, CON29R) — per-UPRN on the
# existing 'building' kind, binding: asserted. OGL (Mining Remediation Authority,
# formerly the Coal Authority). A pure WITHIN flag: the source's Development High
# Risk Area is a dissolved composite (40,186 polygons sharing ONE constant
# FEATURE_TY label), so there is no per-asset identity to enrich — the claim's
# existence is the information, and the source's own "Subject to Change" wording
# travels as the value. COAL IS A SEPARATE REGIME from the BGS non-coal
# `mining_hazard` predicate. Additive, no constitution change.
# Welsh: CY_PENDING — on Catrin's worklist (VH-FUT-070).
# ---------------------------------------------------------------------------
_COAL_SEARCH: tuple[PredicateDef, ...] = (
    PredicateDef("in_coal_high_risk_area", "text", "single", ("building",),
                 "The property lies within the Mining Remediation Authority "
                 "Development High Risk Area — the part of the coal mining reporting "
                 "area containing recorded coal features at surface or shallow depth "
                 "(mine entries, shallow workings, mine gas sites, fissures, former "
                 "surface mining) that pose a potential risk to surface stability. "
                 "Value is the source's verbatim area label. ABSENCE is NOT 'no coal "
                 "mining': a property may be inside the coal reporting area but not "
                 "high-risk, or outside the coalfield entirely — this layer only "
                 "distinguishes the high-risk area. The detailed Coal Mining Report "
                 "is a separate (licensed) product.", description_cy="O fewn ardal risg uchel oherwydd datblygiad (glo)",
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Strategic-road proximity predicate (Sail-Sale Tier-A A4, CON29R) — per-UPRN on
# the existing 'building' kind, binding: asserted. Source: OS OPEN ROADS
# (OS OpenData / OGL) — NOT the National Highways SRN Network Model, which is
# derived from OS Highways (premium) and therefore not commons-releasable
# (DECISION A4, Decision Console 26/07).
#
# Value = the VERBATIM OS `roadClassification` of the nearby road ("Motorway",
# "A Road", …), multi-cardinality so a property can be near more than one class.
# Carrying the CLASS rather than a road number is deliberate: the inclusion rule is
# expressed in classes (A4 = Motorway + A Road; B roads excluded per Huw), so
# widening it later — e.g. B roads for Uniad Bro — is a CONFIG FLIP on the same
# predicate rather than a new one or a re-fetch. (The specific road number is a
# known, deliberate omission; a future enrichment if a consumer asks.)
# Welsh: CY_PENDING — VH-FUT-071.
# ---------------------------------------------------------------------------
_ROAD_PROXIMITY: tuple[PredicateDef, ...] = (
    PredicateDef("near_strategic_road_network", "text", "multi", ("building",),
                 "A road of this OS Open Roads classification lies within the "
                 "search radius (250 m) of the property — value is the verbatim OS "
                 "`roadClassification` ('Motorway', 'A Road', …). A PROXIMITY "
                 "indication for a search (noise, access, severance), NOT a "
                 "statement about any proposed scheme: OS Open Roads describes the "
                 "road network AS BUILT. Published road/rail PROPOSALS are a "
                 "separate question with no OGL national dataset — held. Absence "
                 "means no road of an included class within the radius, nothing more.",
                 description_cy="Yn agos at rwydwaith ffyrdd strategol",
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Reachability — the shared Valhalla/OSM routing capability (Decision Console
# VALHALLA, 26/07/2026). Three predicates cover it, because the travel mode rides in
# the `travel_mode` qualifier (constitution 0.1.4) rather than in the predicate name:
# mode is metadata ABOUT a claim, not a different kind of fact, and encoding it in
# names would multiply this block by the number of modes forever.
#
# Each requires BOTH `source_ran_at` (the routing-graph vintage — a travel time
# describes the network on a DATE, and a claim stamped with a guessed date is wrong
# invisibly) and `travel_mode` (a duration without its mode is meaningless). The
# grammar therefore refuses an unqualified routing claim; no layer has to remember.
#
# All are binding=derived at emit: routing is OUR computation, never an authority's
# fact. Over OSM the licence is ODbL (ruling 26/07 — permitted framework-wide with
# attribution + share-alike carried; ODbL-derived commons layers labelled ODbL, never
# relabelled OGL), carried once on the source citation rather than per claim.
# ---------------------------------------------------------------------------
_REACHABILITY: tuple[PredicateDef, ...] = (
    PredicateDef("travel_time_to_nearest", "real", "multi", ("building", "site", "area"),
                 "Travel time in MINUTES to the nearest feature of a named set, by the "
                 "qualified travel mode. `value_real` is the duration; `value_text` names the "
                 "destination reached (layer:id), so one predicate answers the question for "
                 "any destination set rather than needing one per amenity kind. Computed over "
                 "the routing graph at the stated `source_ran_at` vintage — a modelled "
                 "duration, not a guaranteed journey. Absence means no route was found under "
                 "that mode, which is NOT the same as no physical connection existing.",
                 required_qualifiers=("source_ran_at", "travel_mode"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("network_distance_to_nearest", "real", "multi", ("building", "site", "area"),
                 "Distance in METRES along the network to the nearest feature of a named set, "
                 "by the qualified travel mode. `value_real` is the distance; `value_text` "
                 "names the destination reached (layer:id). Distinct from travel time and NOT "
                 "a proxy for it: this is the predicate an OGL-only routing base can honestly "
                 "populate, because OS Open Roads carries topology and length but no speed "
                 "limits, one-ways or turn restrictions (confirmed against the shipped "
                 "GeoPackage 26/07). Never present a network distance as a drive time.",
                 required_qualifiers=("source_ran_at", "travel_mode"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("reachable_area", "geom", "multi", ("building", "site", "area"),
                 "The isochrone polygon reachable from the subject within a stated duration by "
                 "the qualified travel mode — the catchment itself, for publishing or "
                 "intersecting with other layers. The duration it represents belongs in the "
                 "claim id and the emitting layer's documentation; the geometry is the value. "
                 "Modelled from the routing graph at the stated vintage.",
                 required_qualifiers=("source_ran_at", "travel_mode"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Open access (Sail-Sale Tier-A A5, 2026-07-27) — Natural England, OGL v3.
# The ADJACENT open baseline, deliberately NOT the PRoW network: no consolidated
# open rights-of-way dataset exists (per-surveying-authority, mixed licence), so
# claiming these as "public access" in general would overstate what we hold.
#
# ENGLAND ONLY. Natural England's remit stops at the border and the coast path is
# English by definition, where every other Tier-A layer is E+W. Wales has
# equivalent open-access land published by NRW; its absence here is a real gap,
# not a coverage statement.
# ---------------------------------------------------------------------------
_OPEN_ACCESS: tuple[PredicateDef, ...] = (
    PredicateDef("in_open_access_land", "text", "multi", ("building", "site", "area"),
                 "The property lies within land mapped as open access land under the "
                 "Countryside and Rights of Way Act 2000 (England). Value is the "
                 "VERBATIM statutory category the mapping records — Open Country, "
                 "Registered Common Land, or Section 16 Dedicated Land — one claim per "
                 "category, because a parcel can qualify under more than one and "
                 "collapsing them into a single invented label would lose which statute "
                 "grants the right. A right of access on foot, NOT a right of way, and "
                 "not a statement about vehicular or equestrian access. Excepted land "
                 "(MoD byelaw, s.28 exclusions, racecourses, aerodromes) is already "
                 "removed by the source; the coastal margin is deliberately excluded "
                 "from it and carried separately.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("near_england_coast_path", "text", "multi", ("building", "site", "area"),
                 "An approved stretch of the King Charles III England Coast Path lies "
                 "within the stated radius of the property. Value is the source's "
                 "VERBATIM route status — 'Public footpath', 'Other existing walked "
                 "route', 'Not an existing walked route', and so on — because approval "
                 "is not the same as a path being physically there: roughly 900 of "
                 "16,667 approved segments are recorded as NOT an existing walked route, "
                 "and reporting those as a walkable amenity would over-claim. A "
                 "proximity indication for a search, not a designation and not a "
                 "guarantee of access at the property boundary.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Backfill (2026-07-27) — four AREA predicates that four PUBLISHED national
# layers have been emitting since July with no registry entry at all.
#
# Found by giving the build gate its grammar teeth: validation_gate validated
# only the JSON shape, never predicate-registry membership, so flood-coverage,
# elderly-demand, alc-predictive-wales and uprn-spine each shipped claims naming
# a predicate the grammar did not know. 1,608 committed claims across the four.
#
# The names, value types and cardinalities here are READ OFF the published data,
# not chosen: renaming would break consumers of already-registered layers, and
# the cardinalities were counted inside a single snapshot (flood_coverage 2 per
# LA — Flood Zone 2 and 3; population_estimate 2 per area — Aged 65+ and 85+;
# alc_grade and uprn_count 1 per area). required_qualifiers is empty to match
# convention: 103 of the existing predicates require none, and `binding` /
# `verification_method`, though present on all of these, are never required.
#
# NOTE for a consumer: flood_coverage and population_estimate carry their
# DIMENSION in the bilingual label (value_en 'Flood Zone 2' / 'Aged 65+') rather
# than in a qualifier, so telling the two claims on a subject apart means reading
# that label. That is how the layers were built and is recorded here rather than
# silently changed.
# ---------------------------------------------------------------------------
_AREA_BACKFILL: tuple[PredicateDef, ...] = (
    PredicateDef("flood_coverage", "real", "multi", ("area",),
                 "Share of a local authority's area falling within a named Environment "
                 "Agency / NRW flood zone, as a fraction 0-1. One claim per zone; the "
                 "zone is named in value_en / value_cy. An AREA-SHARE of the whole "
                 "authority, never a site assessment — a low share can still contain "
                 "highly flood-prone sites, and a specific site must be assessed "
                 "directly. Note FZ2 by definition contains FZ3, so the two shares "
                 "overlap and must not be summed.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("population_estimate", "int", "multi", ("area",),
                 "ONS mid-year population estimate for an area, for the age band named "
                 "in value_en / value_cy. An ABSOLUTE count (market size), NOT a "
                 "per-capita or age-standardised rate — a populous area scores high "
                 "simply by being large, so comparing areas on this alone measures size "
                 "rather than concentration.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    # Phase 9 task 9.5 (card c0615): PROPOSED through the one gate under Huw's 09/10/2026 13:29:51Z
    # ruling [sig:91605acd], which reverses triage B's intended answer (ii). Reuses the constitution
    # 0.1.6 projection keys (scenario = the publisher's variant, verbatim; horizon = the projected
    # year; baseline = the base year), so no constitution change. First source: Welsh Government
    # 2022-based LA projections (REQ-arloesidolgellau-5532ba, OGL v3).
    PredicateDef("population_projection", "int", "multi", ("area",),
                 "Projected population of an area for a future year, for the sex and single-year age "
                 "named in value_en / value_cy ('<Sex>, <Age>', e.g. 'Female, Age 47'; 'All ages' "
                 "alone is persons, all ages, the total). A PROJECTION, not a forecast: it extends past trends under "
                 "the publisher's stated assumptions. `scenario` carries the publisher's variant "
                 "name verbatim (e.g. 'Principal projection'), `horizon` the projected year and "
                 "`baseline` the base year. An absolute count like its observed sibling "
                 "population_estimate; never mix the two in one series.",
                 required_qualifiers=("scenario", "horizon", "baseline"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    # alc_grade WAS registered here by the 2026-07-27 backfill sweep, read off
    # the published data, and task 8.6 gave that entry finest_grain=area from
    # the catalogue's own spine declaration. It is SUPERSEDED by the _AREA entry
    # below, which is the pinned AWE-004 read-contract definition (2026-07-18):
    # same name, value_type, cardinality, entity type AND grain, plus the
    # bilingual gloss and the two qualifiers the live emitter already sends
    # (alc_predictive_wales.py: verification_method + semantics_caveat). A
    # second entry under the same name would shadow silently, so it is removed
    # rather than left beside it.
    PredicateDef("uprn_count", "int", "single", ("area",),
                 "Number of OS Open UPRNs falling within an area, derived by counting the "
                 "frozen UPRN spine against that area's boundary. A count of ADDRESSABLE "
                 "LOCATIONS, not of dwellings or of households — a UPRN can be a garage, "
                 "a mast or a subdivided flat.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# Backfill, second sweep (2026-07-27) — seven MORE predicates that published
# layers emit with no registry entry, found by scanning every module rather than
# by waiting for the next test to fail.
#
# The first sweep above caught four because they appeared in committed
# claims.json files. These seven do not: the UPRN spine's per-property emit and
# the GP and gazetteer layers keep their bulk off the committed artefacts, so
# reading the published snapshots was not enough. A source scan found them.
#
# BOTH FROZEN JOIN SPINES are affected. `os_toid` and `street_usrn` are the UPRN
# spine's own cross-identifier claims — the join keys the whole estate is built
# on — and `settlement_rank` is the gazetteer's OS size class. Neither spine
# could have re-materialised once the gate started checking the grammar.
#
# Every one is a fact about the world, not about a source or our fetch of it,
# which is precisely why these are REGISTERED where pub_date / method /
# granularity were moved into the citation instead. Value types are read off the
# emitters; entity types off the entities the modules actually create (GP
# practices are `building`, gazetteer settlements are `town`).
# ---------------------------------------------------------------------------
_SPINE_AND_GP_BACKFILL: tuple[PredicateDef, ...] = (
    PredicateDef("os_toid", "text", "single", ("building",),
                 "OS TOID for the building a UPRN sits in, from OS Open Linked Identifiers. "
                 "TEXT because a TOID is an identifier with a significant 'osgb' prefix, not "
                 "a quantity — the same reasoning that corrected `uprn` from int to text.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("street_usrn", "text", "single", ("building",),
                 "USRN of the street a UPRN is associated with, from OS Open Linked "
                 "Identifiers. An identifier, hence text.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("settlement_rank", "text", "single", ("town",),
                 "The source's own settlement size class for a populated place, VERBATIM from "
                 "OS Open Names (e.g. 'City', 'Town', 'Village', 'Hamlet'). OS's "
                 "classification, not ours, and not a population figure.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ods_code", "text", "single", ("building",),
                 "NHS Organisation Data Service code for an ODS-coded organisation or site (e.g. a "
                 "GP practice, a dialysis unit). An identifier. (A-1, Llys 05/10/2026 "
                 "[sig:75935d1b]: wording only; type, cardinality and applies_to unchanged.)",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("gp_location", "geom", "single", ("building",),
                 "Point location of a GP practice. DERIVED from the practice postcode via an "
                 "ONS postcode centroid, so it locates the POSTCODE UNIT, not the surgery "
                 "door — adequate for a search, not for a site plan.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("operational_status", "text", "single", ("building",),
                 "Whether an ODS-coded organisation or site is currently operational, verbatim "
                 "from the source's own "
                 "status vocabulary. A record status, not a statement about whether the "
                 "premises are open today.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("list_size", "int", "single", ("building",),
                 "Registered patient list size for a practice. A COUNT OF REGISTRATIONS at "
                 "the stated extract month, not of people resident in the area, and lists "
                 "overlap between neighbouring practices.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# Climate sweep — the v0.1.6 batched increment (Llys 07/08/2026 [sig:7508450d]).
# Adopt-and-cite standards; units + statistic ride the predicate NAME (the estate
# convention). Projection predicates require the G0 qualifier keys (scenario/horizon/
# baseline — constitution 0.1.6); the same predicate serves observation when it carries
# `uncertainty_basis=observed` and omits the projection axes. description_cy=CY_PENDING
# (vocabulary-harvest). All estate-originated national/shared layers (federate-don't-copy).
# ---------------------------------------------------------------------------
_CLIMATE_SWEEP: tuple[PredicateDef, ...] = (
    PredicateDef("water_quality_status", "text", "single", ("coastal_cell", "station"),
                 "WFD ecological status class of a water body/coastal cell. Adopt-and-cite the "
                 "Water Framework Directive status classes; source EA/NRW Water Quality Archive "
                 "(WIMS). A dedicated `water_body` spine is deferred (fork a) — rides coastal_cell/"
                 "station for now.",
                 required_qualifiers=(),
                 constraint_json='{"enum": ["High", "Good", "Moderate", "Poor", "Bad"]}',
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("air_temperature_mean_c", "real", "multi", ("area", "station"),
                 "Mean air temperature, degrees Celsius. GCOS ECV Surface Air Temperature; CF "
                 "standard_name air_temperature; QUDT unit DegreeCelsius; SOSA/O&M observation "
                 "result. Observed OR projected: a projection carries scenario/horizon/baseline + "
                 "uncertainty_basis; an observation carries uncertainty_basis=observed.",
                 # R1 (Llys, 23/08/2026), raised by ARL-022 09/08. The sentence above said this in
                 # PROSE and nothing enforced it — a bare number passed the gate, silently ambiguous
                 # between a measured reading and a modelled projection, which is the one conflation
                 # a climate evidence base must never make. `uncertainty_basis` ONLY: this predicate
                 # carries observations too, and requiring the projection keys would make an
                 # observation unemittable. SCH-CLAIM-001's dependentRequired already makes
                 # `scenario` pull in `horizon` and `baseline`, so requiring the key that declares
                 # WHICH KIND OF VALUE THIS IS is sufficient and complete.
                 required_qualifiers=("uncertainty_basis",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("sea_surface_temperature_c", "real", "multi", ("coastal_cell", "station"),
                 "Sea-surface temperature, degrees Celsius. GCOS ECV SST; CF standard_name "
                 "sea_water_temperature; QUDT DegreeCelsius; SOSA/O&M. Observed or projected "
                 "(as air_temperature_mean_c).",
                 required_qualifiers=("uncertainty_basis",),   # R1 — as air_temperature_mean_c
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("sea_level_rise_m", "real", "multi", ("coastal_cell",),
                 "Projected sea-level rise, metres, relative to the baseline period. GCOS ECV Sea "
                 "Level; UKCP18 marine / PSMSL; QUDT unit Meter; SOSA/O&M. PROJECTION — requires "
                 "scenario (IPCC RCP/SSP) + horizon + baseline (constitution 0.1.6 G0).",
                 required_qualifiers=("scenario", "horizon", "baseline"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("coastal_erosion_projection_m", "real", "multi", ("coastal_cell",),
                 "Projected shoreline retreat, metres, over the horizon relative to baseline. "
                 "Adopt-and-cite NCERM (National Coastal Erosion Risk Mapping, NRW / Cell Eleven). "
                 "PROJECTION — requires scenario + horizon + baseline (constitution 0.1.6 G0).",
                 required_qualifiers=("scenario", "horizon", "baseline"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("peatland_carbon_tco2", "real", "single", ("area",),
                 "Estimated peatland carbon stock, tonnes CO2e. Adopt-and-cite the IUCN UK Peatland "
                 "Programme / national peatland carbon mapping; SOSA/O&M estimate. Carry "
                 "uncertainty_basis; confidence_interval where the source states one.",
                 # R1 — "Carry" was an instruction to a person, not a constraint. Now it is one.
                 required_qualifiers=("uncertainty_basis",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("shoreline_management_policy", "text", "multi", ("coastal_cell",),
                 "Defra Shoreline Management Plan (SMP2) policy for a coastal cell, per epoch. "
                 "Multi-cardinality: one per epoch, distinguished by the `horizon` qualifier "
                 "(0-20/20-50/50-100 yr). Adopt-and-cite the four Defra SMP classes.",
                 required_qualifiers=("horizon",),
                 constraint_json='{"enum": ["hold-the-line", "managed-realignment", '
                                 '"no-active-intervention", "advance-the-line"]}',
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("properties_at_flood_risk_count", "int", "multi", ("area",),
                 "Count of properties at flood risk in an area. Adopt-and-cite EA NaFRA. RESOLVES "
                 "the `flood_coverage` false-friend (that is Flood-Zone AREA-SHARE, not a property "
                 "count — see FALSE_FRIENDS). Multi: distinguish source/vintage in the citation "
                 "(carries the contested 245k/273k NaFRA pair, NWC-CONTEST-001).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_rank", "int", "single", ("area",),
                 "Multiple-deprivation rank of an area (1 = most deprived). Adopt-and-cite WIMD "
                 "(Wales) / IMD (England); vintage in the citation. VERIFY-AT-REGISTRATION "
                 "(coordinator condition, Llys 07/08): WIMD 2019 keys on 2011 LSOAs — reconcile to "
                 "LSOA21 via the ONS 2011->2021 lookup, or make the join vintage-correct, before "
                 "loading data; registering LSOA21 against 2011-keyed data is a nominal-but-wrong "
                 "join where boundaries changed.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# Area predicates — applies to entity_type 'area' (spatial regions, not places).
# National-layer grammar added past the v0.1 Dolgellau town seed. `alc_grade` is
# the FIRST such addition (AWE-004, 2026-07-18). It is not a NEW name by the
# time it lands: the 2026-07-27 backfill sweep registered `alc_grade` off the
# published data while this branch was open, so the entry here SUPERSEDES that
# one (see _AREA_BACKFILL) rather than adding to it. The pinned agri read-contract
# (SharedData/alc_grade-claim-schema-PINNED-2026-07-17) routes the Predictive ALC
# Map 2 grade onto an `area` entity, grade VERBATIM in value_text (3a/3b intact),
# worded classes (Non-agricultural/Urban/…) bilingual on value_en/cy.
# ---------------------------------------------------------------------------
_AREA: tuple[PredicateDef, ...] = (
    PredicateDef(
        name="alc_grade",
        value_type="text",   # the grade label verbatim ("2","3a","3b","4","5","NA","U")
        cardinality="single",
        applies_to_types=("area",),
        description_en=(
            "Predictive Agricultural Land Classification (ALC) Map 2 grade for a "
            "land-quality zone. The source grade label travels verbatim, including "
            "the 3a/3b split (never re-bucketed); worded classes (e.g. "
            "Non-agricultural, Urban) also carry bilingual labels. A predictive 50m "
            "grid under MAFF 1988 criteria — not a site survey; a detailed ALC "
            "survey supersedes it. Emitted binding=asserted; the semantics_caveat "
            "carries the predictive limit."
        ),
        # description_cy: Anamaethyddol (the worded-class term) is coordinator-
        # attested in the pin; this predicate gloss is provided here and FLAGGED
        # pending the same tutor-attestation path the v0.1 set used
        # (Awen-Weave/awen-cards) before it is treated as locked vocab.
        description_cy=(
            "Gradd rhagfynegol Dosbarthiad Tir Amaethyddol (ALC Map 2) ar gyfer "
            "parth ansawdd tir — label y radd yn cael ei gadw'n union (gan gynnwys "
            "y rhaniad 3a/3b); grid rhagfynegol 50m yn ôl meini prawf MAFF 1988, "
            "nid arolwg safle. [Cymraeg i'w gadarnhau gan diwtor]"
        ),
        required_qualifiers=("verification_method", "semantics_caveat"),
        constraint_json=None,
        # `area`, not `property`: awen-source-catalogue declares
        # `"alc-predictive-wales": "gazetteer"` in spines.py — the place/GSS
        # spine, never the UPRN spine. Read off the catalogue's own
        # declaration (phase 8 task 8.6's method), not inferred from the name.
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# Welsh Government planning ALLOWANCES — a grammar-addition payload through the one gate
# (PROPOSAL-climate-allowances-grammar-2026-10-02-r2.md; Climate's [sig:7ed42030]; Huw as Llys
# accepted every recommendation 02/10/2026 [sig:dc82671f]). Awen-weave 0.2.27, the minor after
# constitution v0.1.9's pair (0.2.26). No constitution change: predicates are registry-tier.
#
# WHY A SEPARATE FAMILY. A Welsh Government allowance is a planning figure the source sets at a
# stated level for decisions; it is NOT a modelled projection for a coastal cell, a river reach or
# a gauge. Widening `sea_level_rise_m` to `area` would pass the grain rule (coarser is legal) but
# give one name two meanings that nothing the grammar REQUIRES separates (the
# `air_temperature_mean_c` route — one predicate plus a discriminating qualifier — needs a closed
# value meaning "planning allowance", which is Tier-1). So: one name, one meaning, and a FALSE_FRIENDS
# pair below.
#
# WHAT THE SOURCE STATES, AND THEREFORE WHAT IS REQUIRED (Climate's reading of the March 2026 PDF,
# [sig:9fdf7354]). Sea level (Table 3) states a scenario (RCP8.5, document-wide p.1), horizons and
# a baseline (UKCP18 1981-2000) — the full projection triple is required. The flow and rainfall
# tables (Tables 1 and 2) state NO scenario and NO baseline, so ONLY `horizon` is required: a
# required key the source does not state would make the figure unemittable or force the instance
# to supply it, and carrying p.1's scenario would pull in a baseline via SCH-CLAIM-001's
# dependentRequired. The document-wide scenario, the absent baseline and the allowance level
# ("Central", "Upper", "70th percentile", "H++") travel VERBATIM in `semantics_caveat` until
# constitution v0.1.10 gives the level its own key (design/climate-allowances-v0.1.10-and-blocked.md).
#
# SUBJECTS. `area` entities keyed by a gazetteer GSS code: councils (W06…) for sea level. River
# basin districts and Wales (W92000004) are NOT returnable yet — see the design note.
#
# WELSH. All three are CY_PENDING, so under the 31/08 ruling above they are UNEMITTABLE for an
# instance gated on bilingual parity (NWC-WLM-001) until a tutor attests each description_cy. No
# Welsh is written here.
# ---------------------------------------------------------------------------
_CLIMATE_ALLOWANCES: tuple[PredicateDef, ...] = (
    PredicateDef("sea_level_rise_allowance_m", "real", "multi", ("area",),
                 "Welsh Government planning allowance for sea-level rise, metres, for a local "
                 "authority, relative to the baseline the source states. A PLANNING FIGURE at a "
                 "stated allowance level, NOT a modelled projection for any coastal cell (that is "
                 "sea_level_rise_m). Adopt-and-cite: Welsh Government, Climate change allowances and "
                 "flood consequence assessments (March 2026), Table 3; QUDT unit Meter. The "
                 "allowance level travels verbatim in semantics_caveat until constitution v0.1.10.",
                 required_qualifiers=("scenario", "horizon", "baseline"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("peak_river_flow_allowance_pct", "real", "multi", ("area",),
                 "Welsh Government planning allowance for the change in peak river flow, percent, "
                 "for the area the source names, for the epoch it states. A PLANNING FIGURE at a "
                 "stated allowance level ('Central', 'Upper'), NOT a projection or observation of "
                 "flow (that is water_flow). The source states no scenario or baseline for this "
                 "table: both are recorded as the source gives them in semantics_caveat, never "
                 "supplied. Adopt-and-cite: Welsh Government, Climate change allowances and flood "
                 "consequence assessments (March 2026), Table 1; QUDT unit Percent.",
                 required_qualifiers=("horizon",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("rainfall_intensity_allowance_pct", "real", "multi", ("area",),
                 "Welsh Government planning allowance for the change in peak rainfall intensity, "
                 "percent, for the area the source names, for the epoch it states. A PLANNING "
                 "FIGURE at a stated allowance level ('Central', 'Upper'), NOT a projection or "
                 "observation of rainfall (that is rainfall). The source states no scenario or "
                 "baseline for this table: both are recorded as the source gives them in "
                 "semantics_caveat, never supplied. Adopt-and-cite: Welsh Government, Climate "
                 "change allowances and flood consequence assessments (March 2026), Table 2; QUDT "
                 "unit Percent.",
                 required_qualifiers=("horizon",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# Open Evidence (AWE-005) grammar — a one-gate grammar addition (PROPOSAL-open-evidence-grammar-
# 2026-10-03.md, on GitHub at Awen-Weave/open-evidence docs/, #4). Huw as Llys accepted all ten
# recommendations of its section 3 on 04/10/2026 [sig:a40a1dcd], answering question e544a95b.
# Awen-weave 0.2.28. No constitution change: predicates are registry-tier.
#
# MINTED: G1 decision_grant_share, G2 in_flood_zone, G3 within_article_4_direction, G4
# near_listed_building, G5 policy_cited, G6 cites_decision, G7 appeal_reference, G9
# median_price_paid_gbp. DEFERRED, NOT MINTED: G8 main_issue (until OE01's licence is settled; its
# text can carry names) and G10 hmo_share (its only source, OE05, is all rights reserved).
#
# PUBLICATION IS NOT THE GRAMMAR'S QUESTION. G2-G4 are estate grammar for property search; Open
# Evidence itself never publishes them per dwelling (Huw's 02/10 rule). G1 and G9 are area statistics
# only: a share of PAST decisions (never a prediction, OE-NOPREDICT) built from planning.data.gov.uk or
# council records and never PlanIt; a median of sales, never a single sale. Decision 10: licence
# register rows for planning.data.gov.uk planning-application (and any direct EA Flood Map read) come
# before G1 or G2 is used.
#
# G5-G7 are IDENTIFIERS ONLY: the policy or decision reference as cited, never the policy text.
#
# WELSH. Every description_cy is CY_PENDING; nothing here is emittable by a bilingual-parity instance
# (NWC-WLM-001) until a tutor attests it. No Welsh is written here.
# ---------------------------------------------------------------------------
_OPEN_EVIDENCE: tuple[PredicateDef, ...] = (
    PredicateDef("decision_grant_share", "real", "multi", ("area",),
                 "Share of DECIDED planning applications that were granted, as a fraction 0-1, for "
                 "the application type named in value_en and the period in the claim id and note "
                 "(n in the note). A record of PAST decisions, NOT a probability of approval for any "
                 "application. Sources: planning.data.gov.uk planning-application or council "
                 "registers; never PlanIt (discovery only).",
                 required_qualifiers=("source_ran_at",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("in_flood_zone", "text", "single", ("building", "site"),
                 "The flood zone (FZ1 / FZ2 / FZ3, England) the property or development site lies "
                 "in, per the stated source. A SITE fact, unlike flood_coverage (an area-share of a "
                 "whole authority, never a site assessment). Welsh zones to be added if a Welsh source "
                 "is registered.",
                 required_qualifiers=("source_ran_at",),
                 constraint_json='{"enum": ["FZ1", "FZ2", "FZ3"]}',
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("within_article_4_direction", "text", "multi", ("building", "site", "area"),
                 "Article 4 direction whose area contains the subject: the direction reference, "
                 "verbatim. A different designation from a conservation area (conservation_area is "
                 "not reused for it).",
                 required_qualifiers=("source_ran_at",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("near_listed_building", "text", "multi", ("building", "site"),
                 "Listed building(s) within the stated setting radius of the property or site: the "
                 "verbatim NHLE / Cadw list-entry reference of each (the radius and its basis in the "
                 "note). A proximity indication for a search, NOT a statement the subject is listed, "
                 "and NOT an along-network distance (that is network_distance_to_nearest).",
                 required_qualifiers=("source_ran_at",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("policy_cited", "text", "multi", ("event",),
                 "A development-plan policy the decision cites: the plan and policy identifier as "
                 "cited (e.g. 'Local Plan 2013-2033 H10'). The IDENTIFIER ONLY, never the policy "
                 "text. Not a consent or designation reference (that is consent_reference).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("cites_decision", "text", "multi", ("event",),
                 "Another decision this decision cites: its reference (an appeal reference, as in "
                 "appeal_reference, or an LPA application reference). Identifiers only. Not what an "
                 "event acts on (that is affects_entity).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("appeal_reference", "text", "single", ("event",),
                 "The Planning Inspectorate appeal reference, verbatim (APP/...). A different "
                 "identifier, issued by a different body, from the LPA's application_reference.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("median_price_paid_gbp", "real", "multi", ("area",),
                 "Median price paid, GBP, in the area for the period and property type named in "
                 "value_en (HM Land Registry Price Paid). An AREA statistic only, never a single "
                 "sale. Not UK HPI's mix-adjusted average price, which is an index measure.",
                 required_qualifiers=("source_ran_at",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# Lludd (AWE-009) dialysis access: the grammar decisions of
# PROPOSAL-lludd-dialysis-grammar-2026-10-05.md sections 3-4 (Awen-Weave/lludd #7, c91aebe),
# accepted as recommended by Huw as Llys 05/10/2026 [sig:75935d1b]. Awen-weave 0.2.29. No
# constitution change: predicates are registry-tier. A-1 (wording of ods_code and
# operational_status) is above, in _SPINE_AND_GP_BACKFILL, where those two predicates live.
#
# The subjects are organisations' premises, not people. Patients per centre is held
# [sig:7ffb48df]; station counts are for a later ruling; neither is minted here.
#
# G1 service_provided is a CLOSED enum the gate checks (it joins VALUE_CHECKED_PREDICATES, as
# decision_outcome did). The list is extendable by a later decision, for the cancer directory.
# G2 operated_by holds an IDENTIFIER (the operator's ODS organisation code); its name goes in
# value_en. G3 is a modelled share of residents, never a statement that a patient can reach a unit.
#
# WELSH. Every description_cy is CY_PENDING. No Welsh is written here.
# ---------------------------------------------------------------------------
_LLUDD_DIALYSIS: tuple[PredicateDef, ...] = (
    PredicateDef("service_provided", "text", "multi", ("building",),
                 "A service the premises provide, one claim per service, from a closed list: "
                 "haemodialysis-main-unit, haemodialysis-satellite-unit, home-therapies-training. "
                 "Asserted by the operator's or renal network's published unit list. NOT the "
                 "building's use (that is current_use).",
                 constraint_json=json.dumps({"enum": ["haemodialysis-main-unit",
                                                      "haemodialysis-satellite-unit",
                                                      "home-therapies-training"]}),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("operated_by", "text", "single", ("building",),
                 "The organisation that runs the premises: its ODS organisation code (an "
                 "identifier), with its name in value_en. A health board, or an independent-sector "
                 "provider running a unit under contract. NOT a source's authoring organisation "
                 "(organisation) and NOT a tenancy's organisation (tenant_organisation).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("population_share_within_travel_time", "real", "multi", ("area",),
                 "Share of the area's residents, as a fraction 0-1, within the threshold travel time "
                 "of the nearest feature of a named destination set, by the qualified travel mode. "
                 "value_text names the destination set (layer); the threshold goes in the claim id "
                 "and note, as reachable_area's does; the age band goes in value_en; n goes in the "
                 "note. Derived from population_estimate and travel_time_to_nearest, so labelled ODbL "
                 "when Valhalla (OSM) times are used. A MODELLED share of residents, NOT a statement "
                 "that any patient can reach a unit.",
                 required_qualifiers=("source_ran_at", "travel_mode"),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# ---------------------------------------------------------------------------
# Lludd step-0 HEALTH vocabulary (card c0616), PROPOSED in the phase 9 piece 1 one-gate release
# (card c0615, awen-weave 0.2.30). The 13 predicates are carried AS THE LLUDD SEAT WROTE THEM in
# its record (awen_signals.mac5.lludd.jsonl, 2026-10-09T14:01:34Z): names, types, grains, required
# qualifiers and English descriptions verbatim. Dimensions (register, sex/age band, site, period,
# programme, practice) ride value_en/value_cy, as population_estimate does: existing qualifier keys
# only, no constitution change. No Welsh written. Sources: LL02, LL14, LL16, LL17/LL18, LL15 and
# practice-by-LSOA counts (Lludd's own builds under the 09/10 data split [sig:fd927213]).
# ---------------------------------------------------------------------------
_LLUDD_HEALTH: tuple[PredicateDef, ...] = (
    PredicateDef("disease_register_count", "int", "multi", ('building', 'area'),
                 "Number of patients on a named GP disease register at the reference date (source_ran_at)."
                 " The register is named verbatim from the source in value_en/value_cy. A COUNT OF "
                 "REGISTERED PATIENTS, not of residents; lists overlap. Register definitions change "
                 "between years (QAIF to core contract, 2023), so segment before trending. Age-restricted "
                 "registers (e.g. diabetes 17+) count only patients in the age range their name states.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("disease_prevalence_crude_pct", "real", "multi", ('building', 'area'),
                 "Crude prevalence of a named GP disease register, as a percentage of a stated registered-"
                 "patient denominator, at the reference date. binding=asserted is the publisher's own rate"
                 " (its own, possibly age-restricted, denominator); binding=derived is register count / "
                 "registered_patients_count, with the denominator named in semantics_caveat. CRUDE, never "
                 "age-standardised; registered, not resident.",
                 required_qualifiers=('source_ran_at', 'semantics_caveat'),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("registered_patients_count", "int", "multi", ('building', 'area'),
                 "Patients registered with a GP practice (or summed to cluster/health board) at the "
                 "extract date, for the sex and five-year age band named in value_en/value_cy ('All "
                 "persons, all ages' for the total). Patients of indeterminate gender are excluded, as the"
                 " publisher excludes them. A count of REGISTRATIONS, not residents. Distinct from "
                 "list_size, which is single-valued and kept as is.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef("cancer_incidence_count", "int", "multi", ('area',),
                 "Number of new cancer registrations in an area for the cancer site, sex and diagnosis "
                 "period named in value_en/value_cy. Incidence, not prevalence and not provision.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("cancer_incidence_rate_per_100k_esp2013", "real", "multi", ('area',),
                 "Cancer incidence per 100,000, age-standardised to the 2013 European Standard Population,"
                 " for the site, sex and period named in value_en. Statistical spread in "
                 "confidence_interval.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("cancer_mortality_count", "int", "multi", ('area',),
                 "Number of deaths from cancer in an area for the site, sex and period named in "
                 "value_en/value_cy.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("cancer_mortality_rate_per_100k_esp2013", "real", "multi", ('area',),
                 "Cancer mortality per 100,000, age-standardised to the 2013 European Standard Population,"
                 " for the site, sex and period named in value_en. Spread in confidence_interval.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("cancer_net_survival_pct", "real", "multi", ('area',),
                 "Net survival, as a percentage, at the interval (e.g. 1-year, 5-year), for the site, sex "
                 "and diagnosis period named in value_en/value_cy. Spread in confidence_interval.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("screening_uptake_pct", "real", "multi", ('area',),
                 "Share of the eligible population invited who were screened, for the programme and period"
                 " named in value_en/value_cy.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("screening_coverage_pct", "real", "multi", ('area',),
                 "Share of the eligible population adequately screened within the programme's interval, "
                 "for the programme and date named in value_en/value_cy.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("cancer_pathway_within_target_pct", "real", "multi", ('area',),
                 "Share of patients starting first definitive cancer treatment within the Single Cancer "
                 "Pathway target (62 days), for the tumour site and month named in value_en/value_cy.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("cancer_pathway_patients_count", "int", "multi", ('area',),
                 "Number of patients starting first definitive cancer treatment on the Single Cancer "
                 "Pathway, for the tumour site and month named in value_en/value_cy.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("registered_patients_resident_count", "int", "multi", ('area',),
                 "Patients resident in an LSOA (the subject, GSS) who are registered with the GP practice "
                 "whose ODS code is named in value_en, at the extract date. The bridge from registered to "
                 "resident. Small cells: disclosure control applies before any publication (LLUDD-"
                 "SUPPRESS).",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# NHS organisations: where their premises are, who runs them, and their cluster. A NEW group,
# PROPOSED with constitution 0.1.10 (card c0944; step 1 of IDR-006 Awen/PROPOSAL-nhs-organisation-
# subject-kind-2026-10-10-r2.md, under its rulings of Llys 10/10/2026: Q1 [sig:8f0740b4], Q2 as
# amended [sig:3cc4cb54], Q3 [sig:dc513d4d], Q4 [sig:02dd6f4c], Q5 [sig:cc120f20]).
#
# WHY A NEW FAMILY AND NOT gp_location WIDENED (r2 section 3 step 1 proposed widening five
# predicates). An `nhs_org` is not a place, so its grain is `not_spatial`, and the registration rule
# in validation.py refuses any predicate that applies to both a place kind (`building`, `area`) and a
# `not_spatial` kind. So `gp_location`, `ods_code`, `list_size`, `unitary_authority` and `address`
# cannot take `nhs_org` as well as their present kinds. They stay exactly as they are, on `building`
# and `town`, until the served snapshots move off them; nothing served today becomes invalid.
#
# THE FIVE LOCATION CLAIMS (Q2 as amended: the physical location of every surgery and site must be
# known and served). One family serves practices and sites alike, so a site's point and a practice's
# point are the same predicate (r2's recommendation). The three "contained in" claims are references
# to `area` subjects, written with their type (`area:W01000123`), so the registry indexes them on the
# gazetteer spine it already has. Their shape is checked in validation.ENTITY_REF_SHAPES.
#
# "CONTAINED IN" IS NOT "RUN BY" (Q3). The board whose area contains a practice's premises is
# `premises_in_health_board`; the board that runs it is `run_by`. They differ for the 11
# cross-boundary practices, and neither may stand in for the other: two names, and a FALSE_FRIENDS
# pair below. Neither says whom a practice serves; no "serves" predicate exists until
# practice-by-LSOA counts are licensed.
#
# WELSH. All CY_PENDING, never self-attested, so under the 31/08 ruling they are unemittable for an
# instance gated on bilingual parity until a tutor attests each description_cy.
# ---------------------------------------------------------------------------
# + "service" (awen-weave 0.2.40, PROPOSED): Huw as Llys 14/10/2026 [sig:81e81fa4], option B of
# PROPOSAL-nhs-org-service-role-2026-10-14.md. His reading of SCH-ENTITY-001: nhs_org means an NHS
# organisation identified by its ODS code, and practice / site / health board are examples, so the role
# list widens here alone (it was never constitutional), with no constitution change.
# + community-pharmacy and dental-practice, 0.2.52 (card c1545; queued on c1537, Huw's yes [sig:f1f70215]).
NHS_ORG_ROLES: tuple[str, ...] = ("gp-practice", "site", "health-board", "service", "community-pharmacy",
                                  "dental-practice")

_NHS_ORG: tuple[PredicateDef, ...] = (
    PredicateDef("nhs_org_role", "text", "single", ("nhs_org",),
                 "What kind of NHS organisation this ODS code is, from a closed list: gp-practice, "
                 "site (a branch surgery or other premises of a practice or board), health-board, "
                 "service (an NHS body with its own ODS code that delivers care but holds no registered "
                 "patient list, for example an urgent primary care centre; never counted as a GP "
                 "practice), community-pharmacy (a community pharmacy on ODS edispensary, role RO182), "
                 "dental-practice (a general dental practice on ODS egdpprac, which lists NHS and private "
                 "practices alike, so never 'NHS dentist'). "
                 "The role is a claim, not a separate entity type (Q1). Read from the publisher's "
                 "own list the code appears on (epraccur, wlhbsite, the board list, edispensary, egdpprac), "
                 "never guessed from the shape of the code (Q4).",
                 constraint_json=json.dumps({"enum": list(NHS_ORG_ROLES)}),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("premises_point", "geom", "single", ("nhs_org",),
                 "A map point for the organisation's premises, as WKT in EPSG:4326. For a practice "
                 "or site built from its postcode it is the ONS postcode centroid: it locates the "
                 "POSTCODE UNIT, not the door, which is adequate for a search and not for a site "
                 "plan. semantics_caveat must say how the point was derived. The organisation is "
                 "not a place (Q2); this is a stated fact about where its premises are.",
                 required_qualifiers=("semantics_caveat",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("premises_postcode", "text", "single", ("nhs_org",),
                 "The postcode of the organisation's premises, as the publisher gives it (a "
                 "practice's epraccur postcode, a site's wlhbsite address postcode).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("premises_in_lsoa", "entity_ref", "single", ("nhs_org",),
                 "The 2021 LSOA that contains the organisation's premises point, written "
                 "`area:<LSOA GSS code>`. CONTAINMENT of the premises only: it does not say whom "
                 "the organisation serves.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("premises_in_authority", "entity_ref", "single", ("nhs_org",),
                 "The local authority (district or unitary) that contains the organisation's "
                 "premises point, written `area:<GSS code>`. CONTAINMENT only.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("premises_in_health_board", "entity_ref", "single", ("nhs_org",),
                 "The Welsh local health board whose area contains the organisation's premises, "
                 "written `area:<W11 GSS code>`. A fixed lookup from the containing authority: "
                 "each board is made of whole authorities. Wales only. CONTAINMENT, NOT GOVERNANCE: "
                 "the board that runs the organisation is run_by, and the two differ for "
                 "cross-boundary practices.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("run_by", "entity_ref", "single", ("nhs_org",),
                 "The NHS organisation this one is run by, written `nhs_org:<ODS code>`: a practice's "
                 "health board, a site's practice or board, as the publisher states it. GOVERNANCE, "
                 "NOT CONTAINMENT (that is premises_in_health_board), and not whom it serves (Q3). "
                 "Not a premises' operator (that is operated_by, on building).",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("in_cluster", "entity_ref", "single", ("nhs_org",),
                 "The GP cluster a practice belongs to, written `cluster:<publisher code>`, as the "
                 "publisher's cluster list states it. Membership, not location.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
)


# ---------------------------------------------------------------------------
# WIMD 2025 domain ranks (card c1012; PROPOSED in awen-weave 0.2.39). Option A of
# PROPOSAL-wimd-domains-grammar-2026-10-14.md (awen-shared, card c1007), ruled by Huw [sig:0c677900]:
# EIGHT predicates, one per domain, not one labelled predicate and not a `domain` qualifier, the
# one-predicate-per-thing pattern of the 10/10 WIMD-edition ruling Q3 [sig:1451bb92]. It answers the
# question Q5 [sig:b1dc51f4] deferred. Each is single, so a duplicate rank for one LSOA is refused, and
# the domain set is closed by the names, so no value check is needed. deprivation_rank stays the
# OVERALL rank (Q4 [sig:563f0c3c]) and does not move. No qualifier key, no constitution change.
# Licence: REQ-arloesidolgellau-069104 (wimd-2025, OGL v3), the same release.
#
# WELSH: all CY_PENDING, pending for Catrin; never self-attested.
# ---------------------------------------------------------------------------
_WIMD_DOMAIN_COMMON = (
    "WIMD 2025, LSOA 2021 boundaries: 1 = most deprived among Wales's 1,917 LSOAs. It is a RANK, not a "
    "score: equal gaps in rank are not equal gaps in deprivation. Domain ranks are not to be summed or "
    "averaged into an overall rank (WIMD weights its domains; the published overall rank is "
    "deprivation_rank). The edition is in the citation; not comparable with WIMD 2019 or earlier "
    "(different indicators, and 2011 LSOAs).")

_WIMD_DOMAINS: tuple[PredicateDef, ...] = (
    PredicateDef("deprivation_domain_rank_income", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Income domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_employment", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Employment domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_health", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Health domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_education", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Education domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_access_to_services", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Access to Services domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_housing", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Housing domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_community_safety", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Community Safety domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("deprivation_domain_rank_physical_environment", "int", "single", ("area",),
                 "Rank of an area on the WIMD 2025 Physical Environment domain. " + _WIMD_DOMAIN_COMMON,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)


# ---------------------------------------------------------------------------
# CIW care homes (card c1055; PROPOSED in awen-weave 0.2.41). Section 2 of
# PROPOSAL-care-home-predicates-2026-10-14.md (awen-shared, as merged in #809), ruled by Huw
# [sig:7d9c7466]: the 11 predicates approved, care_home_supports' six terms enforced, the as-of date of a
# rating is source_ran_at only (the extract has no inspection or rating date column). For the
# ciw-adult-care-homes layer (Care Home Service, Adults Without / With Nursing), keyed on the service
# address UPRN, so `building` at property grain. Values are CIW's verbatim. Licence: the CIW directory
# data extract, REQ-arloesidolgellau-ede820, countersigned [sig:a0ef1cd8]. No constitution change; no new
# qualifier key (source_ran_at and semantics_caveat already exist). `url` (source only) and
# `inspection_date` (on building, the EPC assessment date: a false friend) are NOT reused or touched.
#
# WELSH: all CY_PENDING, pending for Catrin; never self-attested.
# ---------------------------------------------------------------------------
CARE_HOME_SUPPORTS: tuple[str, ...] = ("dementia", "mental health", "learning disability",
                                       "short breaks/respite", "physical disability",
                                       "younger adults up to 25")

_CARE_HOMES: tuple[PredicateDef, ...] = (
    PredicateDef('care_home_urn', 'text', 'multi', ("building",),
                 "CIW's service reference for the care home, verbatim. An identifier, not a quantity. Multi: one service address UPRN can hold several CIW services (the 14 Denbighshire services on one UPRN); at a shared UPRN only care_home_urn, name_en and the semantics_caveat are served.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_type', 'text', 'single', ("building",),
                 "CIW's service type, verbatim (e.g. 'Care Home Service').",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_sub_type', 'text', 'single', ("building",),
                 "CIW's service sub-type, verbatim: 'Adults Without Nursing' or 'Adults With Nursing'.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_supports', 'text', 'multi', ("building",),
                 'One claim per need CIW lists the home as supporting, verbatim, from a closed list: dementia, mental health, learning disability, short breaks/respite, physical disability, younger adults up to 25. What CIW records, not an assessment of the care given.',
                 constraint_json=json.dumps({"enum": list(CARE_HOME_SUPPORTS)}),
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_max_places', 'int', 'single', ("building",),
                 "CIW's 'Maximum no. of places', verbatim: the home's registered capacity, never occupancy. It says how many people the home is registered to care for, not how many it holds or has free.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_language', 'text', 'single', ("building",),
                 'The language of the service as CIW records it, verbatim.',
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_website', 'text', 'single', ("building",),
                 "The service's website as CIW gives it, verbatim: a public URL, never a contact for a person.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_rating_well_being', 'text', 'single', ("building",),
                 "CIW's Well-being rating, verbatim, as published in CIW's extract at source_ran_at (the extract's own 'last updated' time, carried as the source_ran_at qualifier); not an inspection date. The extract holds the four ratings in one 'Service ratings' cell and no rating date, so none is claimed.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_rating_care_support', 'text', 'single', ("building",),
                 "CIW's Care and Support rating, verbatim, as published in CIW's extract at source_ran_at (the extract's own 'last updated' time, carried as the source_ran_at qualifier); not an inspection date. The extract holds the four ratings in one 'Service ratings' cell and no rating date, so none is claimed.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_rating_leadership_management', 'text', 'single', ("building",),
                 "CIW's Leadership and Management rating, verbatim, as published in CIW's extract at source_ran_at (the extract's own 'last updated' time, carried as the source_ran_at qualifier); not an inspection date. The extract holds the four ratings in one 'Service ratings' cell and no rating date, so none is claimed.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
    PredicateDef('care_home_rating_environment', 'text', 'single', ("building",),
                 "CIW's Environment rating, verbatim, as published in CIW's extract at source_ran_at (the extract's own 'last updated' time, carried as the source_ran_at qualifier); not an inspection date. The extract holds the four ratings in one 'Service ratings' cell and no rating date, so none is claimed.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.PROPERTY,
    ),
)


# ---------------------------------------------------------------------------
# False-friend register (v0.1.6, Decision 1). A false-friend is a predicate that
# SOUNDS like it means something it does not — so a consumer can silently reuse the
# wrong one. Landed beside the registry (predicate-gap resolution route) + guarded
# below. The naming analogue of the semantics_caveat rule.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FalseFriend:
    name: str            # the predicate that is easy to misread
    means: str           # what it actually asserts
    not_means: str       # the plausible-but-wrong reading to avoid
    use_instead: str     # the predicate to use for the wrong reading (or "-" if none yet)


FALSE_FRIENDS: tuple[FalseFriend, ...] = (
    FalseFriend(
        "flood_coverage",
        "the Flood-Zone AREA-SHARE of a place (what fraction of the area is in a flood zone)",
        "a count of properties at flood risk",
        "properties_at_flood_risk_count",
    ),
    FalseFriend(
        "condition_discharge_status",
        "a PLANNING condition's discharge state (whether a planning condition has been discharged)",
        "anything hydrological — a watercourse discharge / flow",
        "water_flow",
    ),
    # The allowance pair (02/10/2026 [sig:dc82671f]) — the two meanings the separate predicate keeps apart.
    FalseFriend(
        "sea_level_rise_m",
        "a MODELLED sea-level projection for a coastal cell (UKCP18 marine)",
        "a Welsh Government planning allowance for a council",
        "sea_level_rise_allowance_m",
    ),
    FalseFriend(
        "sea_level_rise_allowance_m",
        "a Welsh Government PLANNING ALLOWANCE for a council, at a stated level",
        "a modelled sea-level projection for a coastal cell",
        "sea_level_rise_m",
    ),
    # G2 (04/10/2026 [sig:a40a1dcd]): a second reading flood_coverage invites, for a site.
    FalseFriend(
        "flood_coverage",
        "the Flood-Zone AREA-SHARE of a place (what fraction of the area is in a flood zone)",
        "the flood zone a property or development site lies in",
        "in_flood_zone",
    ),
    # G1 and G2 (05/10/2026 [sig:75935d1b]): the readings the Lludd dialysis predicates keep apart.
    FalseFriend(
        "current_use",
        "a building's primary USE today",
        "a clinical service the premises provide (e.g. a dialysis service)",
        "service_provided",
    ),
    FalseFriend(
        "organisation",
        "a SOURCE's authoring or holding organisation",
        "the organisation that runs a premises",
        "operated_by",
    ),
    FalseFriend(
        "tenant_organisation",
        "a TENANCY's formal organisation name",
        "the organisation that runs a premises",
        "operated_by",
    ),
    # Q3 (Llys 10/10/2026 [sig:dc513d4d]), card c0944: containment and governance kept apart.
    FalseFriend(
        "premises_in_health_board",
        "the health board whose AREA CONTAINS an organisation's premises",
        "the health board that runs the organisation",
        "run_by",
    ),
    FalseFriend(
        "run_by",
        "the NHS organisation that RUNS this one (governance)",
        "the health board whose area contains its premises",
        "premises_in_health_board",
    ),
    FalseFriend(
        "operated_by",
        "the organisation that runs a PREMISES (a building subject)",
        "the organisation an NHS organisation is run by",
        "run_by",
    ),
)


# PROPOSED (cards c1125, c1130, c1132; phase 10 task 10.4, exit 4). Two sources, each register
# first: StatsWales Pathways of Care Delays (REQ-arloesidolgellau-9fdd66) and ONS labour demand by
# SOC 2020 (REQ-arloesidolgellau-f89d55 [sig:fd1a1adc]). The category and the period ride value_en,
# the cancer_pathway_patients_count pattern. The delays register row's rule, "provider health board
# and residence local authority ... never mixed, summed or joined across", is held by the NAMES: a
# board figure has its own predicates, so it can never sit beside an authority's figure in one.
_CARE_DELAYS_COMMON = (
    " on the monthly census day, for the reason for delay and the month named in value_en/value_cy "
    "(e.g. 'Assessment Issues, April 2023'), as StatsWales publishes it (Pathways of Care Delays, "
    "from April 2023, the first fully validated month; data provider the NHS Delivery Unit). Reasons "
    "nest: a reason category and its sub-reasons are both published, so a category is never added to "
    "its own sub-reasons. The provider-board and residence-authority views are two different counts "
    "of the same delays, never mixed, summed or joined across. Wales (W92000004) carries the national "
    "total.")
_CARE_DELAYS_PROVIDER = (
    " Attributed to the health board that PROVIDED the care (the subject, a W11 board): a provider "
    "board's figure can include patients who live outside its area.")
_CARE_DELAYS_RESIDENCE = (
    " Attributed to the local authority where the patient LIVES (the subject, a W06 authority).")
_CARE_DELAYS_AND_ADVERTS: tuple[PredicateDef, ...] = (
    PredicateDef("care_delays_count_by_provider_board", "int", "multi", ('area',),
                 "Number of pathway of care delays (patients whose discharge from hospital is delayed)"
                 + _CARE_DELAYS_COMMON + _CARE_DELAYS_PROVIDER,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("care_delays_days_by_provider_board", "int", "multi", ('area',),
                 "Number of days delayed, summed over the pathway of care delays"
                 + _CARE_DELAYS_COMMON + _CARE_DELAYS_PROVIDER,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("care_delays_count_by_residence_authority", "int", "multi", ('area',),
                 "Number of pathway of care delays (patients whose discharge from hospital is delayed)"
                 + _CARE_DELAYS_COMMON + _CARE_DELAYS_RESIDENCE,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("care_delays_days_by_residence_authority", "int", "multi", ('area',),
                 "Number of days delayed, summed over the pathway of care delays"
                 + _CARE_DELAYS_COMMON + _CARE_DELAYS_RESIDENCE,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("online_job_adverts_count", "int", "multi", ('area',),
                 "Number of NEW online job adverts in the area (the subject, a local authority "
                 "district) for the SOC 2020 occupation group and the period (a month or a quarter) "
                 "named in value_en/value_cy (e.g. 'SOC 2020 6135 Care workers and home carers, 2026 "
                 "Q1'), as ONS publishes it from Textkernel online job adverts (labour demand volumes "
                 "by SOC 2020, official statistics in development). It counts adverts, not vacancies "
                 "or posts: one advert can cover several posts and one post can be advertised many "
                 "times. A cell ONS suppresses ([x]) is not a zero and is never filled. Each monthly "
                 "edition revises the whole history, so the edition is in the citation.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED (card c1181; phase 11 scope 11.1, exit 1). P1: StatsWales "Deprivation at GP practice
# level" (REQ-arloesidolgellau-4e09d9, countersigned [sig:f8f167fa]), on the practice's nhs_org subject.
# F3: FSA Food Hygiene Rating Scheme open data (REQ-arloesidolgellau-7f5412, countersigned
# [sig:6c817dd7]), a count per Welsh authority by the FSA's business type. Date, method and type ride
# value_en; source_ran_at required.
_PRACTICE_DEPRIVATION_COMMON = (
    " for the GP practice (the subject, nhs_org:<ODS code>) at the extraction date named in "
    "value_en/value_cy, as StatsWales publishes it (Deprivation at GP practice level; data providers "
    "Welsh Government (WIMD) and NHS Wales Shared Services Partnership). It describes the practice's "
    "registered list, never any person on it.")
_PHASE11_ROUND2: tuple[PredicateDef, ...] = (
    PredicateDef("practice_population_count", "int", "multi", ('nhs_org',),
                 "Number of patients registered with the practice" + _PRACTICE_DEPRIVATION_COMMON,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("practice_patients_most_deprived_20pct_count", "int", "multi", ('nhs_org',),
                 "Number of the practice's registered patients whose resident LSOA is in the most "
                 "deprived 20% of Welsh LSOAs by WIMD (WIMD 2025 from April 2026; WIMD 2019, on 2011 "
                 "LSOAs, before)" + _PRACTICE_DEPRIVATION_COMMON,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("practice_patients_most_deprived_20pct_pct", "real", "multi", ('nhs_org',),
                 "Percentage of the practice's registered patients whose resident LSOA is in the most "
                 "deprived 20% of Welsh LSOAs by WIMD (the WIMD edition as for "
                 "practice_patients_most_deprived_20pct_count)" + _PRACTICE_DEPRIVATION_COMMON,
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("practice_deprivation_quintile", "int", "multi", ('nhs_org',),
                 "The practice deprivation quintile, 1 = the most deprived fifth of Welsh practices to "
                 "5 = the least, under the method named in value_en/value_cy (ranked by the number, or "
                 "by the percentage, of patients in the most deprived 20% of WIMD LSOAs)"
                 + _PRACTICE_DEPRIVATION_COMMON + " Quintiles are relative to the practices open at "
                 "that date, so a quintile is not to be compared across dates.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("food_outlets_count", "int", "multi", ('area',),
                 "Number of food businesses registered with the local authority (the subject, a W06 "
                 "authority) under the Food Hygiene Rating Scheme, for the FSA business type and the "
                 "extract date named in value_en/value_cy (e.g. 'Takeaway/sandwich shop, 2026-10-07'). "
                 "Counted from the FSA's open data list, so the count is derived; no business name or "
                 "address is served. It describes the area's food environment and is not a measure "
                 "of what anyone eats.",
                 required_qualifiers=('source_ran_at',),
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED (card c1181; phase 11 scope 11.1, F1 and P2). F1: Priority Places for Food Index v2.1
# (REQ-arloesidolgellau-e2c2c8), one predicate per thing (the WIMD-domains pattern, [sig:0c677900]).
# P2: Data Map Wales Primary Care Clusters (REQ-arloesidolgellau-5ba9fe): the LSOA's cluster.
_PPFI_COMMON = (
    " of the LSOA (LSOA 2021) within Wales, as published in PPFI v2.1 (Healthy & Sustainable Places Data "
    "Service, originally CDRC; DOI 10.82147/003). PPFI ranks each country separately, so a rank or decile "
    "is not comparable across countries. It describes the area's food environment and need, never any "
    "person or household in it.")
_PPFI_RANK = (
    " Ranks run 1 to 1,917; 1 = the highest priority for food (measured: rank 1 aligns with WIMD's most "
    "deprived LSOAs and combined decile 1 is ranks 1-192; the publisher's guide does not state the "
    "direction in words). Domain ranks can tie as published.")
_PPFI_DECILE = " Deciles run 1 to 10; decile 1 = the highest-priority tenth."
_PPFI_AND_CLUSTER: tuple[PredicateDef, ...] = (
    PredicateDef("ppfi_rank_combined", "int", "single", ('area',),
                 "Rank of the combined Priority Places for Food Index" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_supermarket_proximity", "int", "single", ('area',),
                 "Rank of the Proximity to supermarket retail facilities domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_supermarket_accessibility", "int", "single", ('area',),
                 "Rank of the Accessibility to supermarket retail facilities domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_ecommerce_access", "int", "single", ('area',),
                 "Rank of the Access to online deliveries domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_socio_demographic", "int", "single", ('area',),
                 "Rank of the Socio-demographic barriers domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_nonsupermarket_proximity", "int", "single", ('area',),
                 "Rank of the Proximity to non-supermarket food provision domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_food_for_families", "int", "single", ('area',),
                 "Rank of the Need for family food support domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_rank_fuel_poverty", "int", "single", ('area',),
                 "Rank of the Fuel poverty domain" + _PPFI_COMMON + _PPFI_RANK,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_combined", "int", "single", ('area',),
                 "Decile of the combined Priority Places for Food Index" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_supermarket_proximity", "int", "single", ('area',),
                 "Decile of the Proximity to supermarket retail facilities domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_supermarket_accessibility", "int", "single", ('area',),
                 "Decile of the Accessibility to supermarket retail facilities domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_ecommerce_access", "int", "single", ('area',),
                 "Decile of the Access to online deliveries domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_socio_demographic", "int", "single", ('area',),
                 "Decile of the Socio-demographic barriers domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_nonsupermarket_proximity", "int", "single", ('area',),
                 "Decile of the Proximity to non-supermarket food provision domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_food_for_families", "int", "single", ('area',),
                 "Decile of the Need for family food support domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("ppfi_decile_fuel_poverty", "int", "single", ('area',),
                 "Decile of the Fuel poverty domain" + _PPFI_COMMON + _PPFI_DECILE,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("area_in_cluster", "entity_ref", "single", ('area',),
                 "The GP primary care cluster whose footprint holds this LSOA (the subject, an LSOA 2021 "
                 "area), written `cluster:<publisher code>`, from Data Map Wales' Primary Care Clusters "
                 "(63 clusters as at October 2024). The footprint maps each LSOA to the cluster where "
                 "most of its residents are registered with a GP practice: a best fit by registration, "
                 "not an exact boundary, and never a statement of where any person is registered.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED, HOLD (card c1209; phase 11 scope 11.5): Census 2021 for Wales, register
# REQ-arloesidolgellau-7d070c (ONS tables via Nomis; the bulk files [sig:a7374d4e]). One predicate per
# thing, as the WIMD and PPFI groups: one per table, an area count by its LEAF category in value_en.
_C21_DAY = " on census day (21/03/2021)"
_C21_LEAF = (", for the leaf category named in value_en / value_cy, VERBATIM from ONS (subtotals not "
             "carried). ONS perturbs each Census 2021 table separately, so its total may differ by a "
             "few from another table's for the same area. Vintage in the citation.")
_C21_LSOA = (" SERVED at LSOA only, never at output area: the sensitivity Huw ruled for TS066's "
             "'long-term sick or disabled' [sig:691127c0], as proposed on card c1209.")
_C21_OA = " Served at output area, as proposed on card c1209."
_CENSUS_PHASE11: tuple[PredicateDef, ...] = (
    PredicateDef("usual_residents_general_health_count", "int", "multi", ("area",),
                 "Census 2021 count of all usual residents in an area by self-assessed general health "
                 "(TS037: very good, good, fair, bad, very bad)" + _C21_DAY + _C21_LEAF + _C21_LSOA,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("usual_residents_disability_count", "int", "multi", ("area",),
                 "Census 2021 count of all usual residents in an area by disability under the Equality "
                 "Act (TS038: day-to-day activities limited a lot or a little; not disabled with or "
                 "without a long-term condition)" + _C21_DAY + _C21_LEAF + _C21_LSOA,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("usual_residents_unpaid_care_count", "int", "multi", ("area",),
                 "Census 2021 count of usual residents aged 5 years and over in an area by unpaid care "
                 "provided a week (TS039: none, 9 hours or less, 10 to 19, 20 to 34, 35 to 49, 50 or "
                 "more). The published '19 hours or less' and '20 to 49 hours' are subtotals their "
                 "labels do not mark; they are proven against their leaves and not carried"
                 + _C21_DAY + _C21_LEAF + _C21_LSOA,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("usual_residents_welsh_language_skills_count", "int", "multi", ("area",),
                 "Census 2021 count of usual residents aged 3 years and over in a Welsh area by Welsh "
                 "language skills (TS032, the detailed table: each combination of understanding, "
                 "speaking, reading and writing Welsh, and no skills)" + _C21_DAY + _C21_LEAF + _C21_OA
                 + _LLEFELYS_GRAIN + _LLEFELYS_WELSH_WAIT,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("households_composition_count", "int", "multi", ("area",),
                 "Census 2021 count of HOUSEHOLDS in an area by household composition (TS003). Older "
                 "people living alone is the leaf 'One person household: Aged 66 years and over' (66, "
                 "the state pension age at the census, not 65); 'Single family household: All aged 66 "
                 "years and over' is older couples and families, not people alone" + _C21_DAY
                 + _C21_LEAF + _C21_OA,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# RATIFIED by Huw as Llys 17/10/2026 [sig:1ffc4503] (cards c1232/c1237; Llefelys AWE-011 build step 1). R1: ONS Output Area (2021)
# to PARNCP (December 2025) best-fit lookup (REQ-arloesidolgellau-e56561, countersigned [sig:607e58a8]).
_LLEFELYS_COMMUNITY: tuple[PredicateDef, ...] = (
    PredicateDef("area_in_community", "entity_ref", "single", ('area',),
                 "The community that holds this output area (the subject, an Output Area 2021), written "
                 "`area:<GSS code>`: a Welsh community (W04), an English parish (E04) or an English "
                 "non-civil-parished area (E43), from the ONS Output Area (2021) to PARNCP (December "
                 "2025) best-fit lookup. Each output area goes wholly to the community holding its "
                 "population-weighted centre: a best fit, not a statement that the whole output area "
                 "lies inside the community, so any community figure summed through it is approximate.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED, HOLD (cards c1272/c1281; Llefelys AWE-011 build item 2): Census 2021 TS067 under
# REQ-arloesidolgellau-7d070c, Llefelys consumer addition countersigned [sig:607e58a8].
_LLEFELYS_CENSUS: tuple[PredicateDef, ...] = (
    PredicateDef("usual_residents_highest_qualification_count", "int", "multi", ("area",),
                 "Census 2021 count of usual residents aged 16 years and over in an area by highest "
                 "level of qualification, for the leaf category named in value_en / value_cy (TS067: "
                 "no qualifications, level 1 and entry level, level 2, apprenticeship, level 3, level 4 "
                 "and above, other; VERBATIM from ONS). Served at LSOA and above; the output area "
                 "grain is built for Llefelys alone and is never served." + _LLEFELYS_GRAIN
                 + " Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED, HOLD (cards c1297/c1281; Llefelys AWE-011 build item 3, jobs and firms): ONS BRES open access
# (REQ-arloesidolgellau-551c2c) and UK Business Counts (REQ-arloesidolgellau-c1fbf7), both countersigned
# [sig:607e58a8]. Shown at MSOA and local authority only.
_JF_GRAIN = (" Served for an MSOA (2021) or a local authority only, never split to a community: the published "
             "figure is for that area as a whole. Vintage in the citation.")
_UKBC = (" Counted from the Inter Departmental Business Register at its March reference date, by the broad "
         "industry group and the employment size band named in value_en (e.g. '3 : Manufacturing (C), Total, "
         "2026'). ONS rounds every figure to avoid disclosure, so values may be rounded down to zero and zeros "
         "are not necessarily true zeros; totals across tables may differ by small amounts.")
_LLEFELYS_JOBS_FIRMS: tuple[PredicateDef, ...] = (
    PredicateDef("bres_employment_count", "int", "multi", ("area",),
                 "Business Register and Employment Survey (ONS), open access tier only and never the "
                 "safeguarded tier: jobs counted at the workplace in an area (not where people live), for the employment status, broad "
                 "industry group and year named in value_en (e.g. 'Employees, 3 : Manufacturing (C), 2024'). "
                 "Employment status is one of Employees, Full-time employees, Part-time employees or Employment "
                 "(employees plus working owners); the four are never summed. A count, rounded by ONS as "
                 "published; no confidential cell is ever served. The agriculture group excludes farm "
                 "agriculture (SIC 01000), and a figure ONS marks incomplete says so in its caveat." + _JF_GRAIN,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("enterprises_count", "int", "multi", ("area",),
                 "UK Business Counts (ONS): the number of enterprises (whole businesses, counted where they "
                 "are registered) in an area." + _UKBC + " Never mixed with local_units_count, which counts "
                 "each site." + _JF_GRAIN,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("local_units_count", "int", "multi", ("area",),
                 "UK Business Counts (ONS): the number of local units (each workplace or site of a business) "
                 "in an area." + _UKBC + " Never mixed with enterprises_count, which counts each business "
                 "once." + _JF_GRAIN,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED, HOLD (cards c1317/c1298; Llefelys AWE-011 build item 4, wages and work): ONS ASHE
# (REQ-arloesidolgellau-727844, Tables 5, 7 and 8 on ons.gov.uk) and the Annual Population Survey
# (REQ-arloesidolgellau-e14238), both countersigned [sig:607e58a8].
_BORROWED = (" Where an authority's own figure is not published (suppressed, or never broken down that far, as "
             "pay by industry is not), the page may show the Wales figure beside the authority: such a claim's "
             "semantics_caveat begins 'Borrowed from <area name> (<GSS code>)', naming the area the figure is for, "
             "and it is never presented as the authority's own. Served for a local authority or Wales.")
_ASHE = (" Annual Survey of Hours and Earnings (ONS), all employee jobs, the median, for the basis and industry "
         "named in value_en: workplace (Table 7, where people work) or residence (Table 8, where they live) "
         "for a local authority, and Wales by industry (Table 5, SIC 2007 section) at the workplace. A survey "
         "estimate: ONS withholds a cell marked 'x' (coefficient of variation above 20%) or '..' (disclosive), "
         "and no such cell is ever filled in or re-derived. Vintage (e.g. 2025 provisional) in value_en.")
_LLEFELYS_WAGES_WORK: tuple[PredicateDef, ...] = (
    PredicateDef("aps_estimate_pct", "real", "multi", ("area",),
                 "Annual Population Survey (ONS) estimate, a percentage, for the variable and period named in "
                 "value_en VERBATIM from Nomis (e.g. 'Employment rate - aged 16-64, Apr 2025-Mar 2026'). Its 95% "
                 "confidence interval rides the confidence_interval qualifier. A cell ONS marks '!' (sample "
                 "zero or disclosive) is never served; a cell marked '*' (sample 3-9) is served as unreliable, "
                 "with no interval, and says so. APS lost its accredited status for 2024 onwards; small-area "
                 "estimates need care." + _BORROWED,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("earnings_median_annual_gross_gbp", "int", "multi", ("area",),
                 "Median gross annual pay in pounds." + _ASHE + _BORROWED,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("earnings_median_hourly_excl_overtime_gbp", "real", "multi", ("area",),
                 "Median hourly pay excluding overtime, in pounds." + _ASHE + _BORROWED,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# PROPOSED, HOLD (cards c1318/c1304; Llefelys AWE-011 build item 6, missed local supply): Sell2Wales OCDS
# (REQ-arloesidolgellau-ed7120, countersigned [sig:607e58a8]; route the OCP Data Registry copy), placed by the
# ONS Postcode Directory (REQ-arloesidolgellau-c94857, Llefelys processing only [sig:df798785]).
_SUPPLY = (" For the buyers placed in the area (a local authority, or Wales), by where each supplier is relative to "
           "its buyer, named in value_en with the CPV division of the tender (or 'CPV not stated') and the range: one "
           "of in the buyer's community, in the buyer's authority, elsewhere in Wales, outside Wales, or location "
           "unknown (no postcode, or one the ONS Postcode Directory does not hold). Every figure is labelled "
           "'April 2022 to March 2026, Sell2Wales via the OCP Data Registry'. Supplier names and postcodes are used "
           "in processing only: no supplier is ever named, and no postcode is ever served [sig:e449210e]. A figure "
           "built from fewer than 5 awards is never served; the page says 'fewer than 5' [sig:e580fe02].")
_LLEFELYS_SUPPLY: tuple[PredicateDef, ...] = (
    PredicateDef("public_contract_supplier_awards_count", "int", "multi", ("area",),
                 "The number of Sell2Wales contract awards to suppliers, where each supplier named on an award counts "
                 "once (an award to a framework of three suppliers counts three)." + _SUPPLY,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("public_contract_award_value_gbp", "int", "multi", ("area",),
                 "The total value in pounds of those supplier awards, counted only where the award states a value in "
                 "pounds; value_en says how many of the awards carry one, so a total is never read as complete." + _SUPPLY,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# RATIFIED [sig:8e70be16] (card c1487, Llefelys Code seat 2; queued 2026-10-20T14:29:57Z): Llefelys AWE-011
# phase 13. TS033 under REQ-arloesidolgellau-7d070c for exit L1 (skills held); the BRES open access location
# quotient under REQ-arloesidolgellau-551c2c, one predicate for exits L2 (jobs nearby) and L6 (room to grow).
_LLEFELYS_PHASE13: tuple[PredicateDef, ...] = (
    PredicateDef("usual_residents_welsh_speaking_count", "int", "multi", ("area",),
                 "Census 2021 count of usual residents aged 3 years and over in a Welsh area by whether they "
                 "can speak Welsh (TS033, Welsh language skills: speaking)" + _C21_DAY + _C21_LEAF
                 + " Served at LSOA and above; the output area grain is built for Llefelys alone and is never "
                 "served." + _LLEFELYS_GRAIN + _LLEFELYS_WELSH_WAIT,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("bres_employment_location_quotient", "real", "multi", ("area",),
                 "The location quotient of an area's jobs in a broad industry group against Wales, from the "
                 "Business Register and Employment Survey (ONS), open access tier only: the area's share of its "
                 "jobs (employment status Employment: employees plus working owners) in the group over Wales's "
                 "share, for the group and year named in value_en (e.g. 'Employment, 3 : Manufacturing (C), "
                 "2024'). A quotient above 1 means the group is more concentrated in the area than in Wales. "
                 "Wales is the sum of the 22 local authorities' rounded figures, as the published file has no "
                 "Wales row, so a small area's quotient moves with rounding. Published evidence only: no "
                 "forecast is made from it." + _JF_GRAIN,
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# RATIFIED (card c1626, Llefelys Code seat 2): Llefelys AWE-011 phase 13 L2, the two predicates in the release queue.
# community_wider_area queued on Huw's ruling [sig:a884ac2d] (card c1595); residents_by_place_of_work_count ruled
# [sig:3c709fd0], under the Llefelys ODWP01EW transition on REQ-arloesidolgellau-7d070c countersigned [sig:a5012975].
_LLEFELYS_L2_FLOWS: tuple[PredicateDef, ...] = (
    PredicateDef("community_wider_area", "entity_ref", "single", ("area",),
                 "The MSOA (2021) wholly holding this Welsh community (the subject, a W04 community), written "
                 "`area:<GSS code>`, from the plan's pairs [sig:f0b1fb85]; the community's figures are never split "
                 "from it: figures served for the MSOA are 'the wider area', never apportioned to the community.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
    PredicateDef("residents_by_place_of_work_count", "int", "multi", ("area",),
                 "Census 2021 ODWP01EW (location of usual residence and place of work): the count of usual "
                 "residents aged 16 years and over in employment, or temporarily away from work, living in the "
                 "subject MSOA, by the place of work named in value_en as an MSOA or local authority code, on "
                 "census day (21/03/2021). Small flows suppressed as published, never filled. Served at MSOA "
                 "grain only, as 'the wider area', and never split to a community. Vintage in the citation.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.AREA,
    ),
)

# The complete seed set, in schema-document order; the Egni demand predicates
# (post-bootstrap, 2026-07-20) then the ratified EPC / planning / BGS-searches
# groups (2026-07-22) follow the v0.1 seed groups.
# PROPOSED, HOLD (card c1321; phase 11 scope 11.2, F2): Access to Healthy Assets and Hazards (AHAH),
# REQ-arloesidolgellau-9c29cf (v4 countersigned [sig:6c817dd7], redistributable [sig:fca1c0cd]). One
# predicate per thing, as the WIMD and PPFI groups. Units from the publisher's code (GeographicDataService/
# ahah): v4 times are ((length/1000)/speed_kph)*60 per road edge (cjber/ukroutes), so minutes.
_AHAH_COMMON = (
    ". Per LSOA (LSOA 2021), as published in Access to Healthy Assets and Hazards (AHAH; Geographic Data "
    "Service, formerly CDRC; version in the citation); not compared across AHAH versions, whose methods "
    "and inputs change. It describes the area's environment, never any person or household in it.")
_AHAH_DRIVE = (
    "Modelled drive time in MINUTES by car from the LSOA's postcodes to the nearest {what}: the LSOA's "
    "average over its postcodes (the median in v4, over OS Open Roads speed estimates; the mean from v5, "
    "over OpenStreetMap with Valhalla), a modelled time, not a journey anyone made{extra}")
_AHAH_HAZARD = "; for a hazard a shorter time means MORE exposure"
_AHAH_PCT = (
    "Percentile 1 to 100 within Great Britain (not Wales alone) of the {what}: "
    "100 = the least healthy environment, 1 = the most healthy")


def _ahah_drive(slug: str, what: str, extra: str = "") -> PredicateDef:
    return PredicateDef(f"ahah_drive_minutes_{slug}", "real", "single", ("area",),
                        _AHAH_DRIVE.format(what=what, extra=extra) + _AHAH_COMMON,
                        description_cy=CY_PENDING, finest_grain=Grain.AREA)


def _ahah_air(slug: str, what: str) -> PredicateDef:
    return PredicateDef(f"ahah_air_{slug}_ugm3", "real", "single", ("area",),
                        f"Modelled annual mean concentration of {what} in µg/m³ (DEFRA Pollution Climate "
                        "Mapping 1 km grid, averaged over the LSOA)" + _AHAH_COMMON,
                        description_cy=CY_PENDING, finest_grain=Grain.AREA)


def _ahah_pct(slug: str, what: str) -> PredicateDef:
    return PredicateDef(f"ahah_percentile_{slug}", "int", "single", ("area",),
                        _AHAH_PCT.format(what=what) + _AHAH_COMMON,
                        description_cy=CY_PENDING, finest_grain=Grain.AREA)


_AHAH: tuple[PredicateDef, ...] = (
    _ahah_drive("gp", "GP surgery"),
    _ahah_drive("dentist", "dentist"),
    _ahah_drive("pharmacy", "pharmacy"),
    _ahah_drive("hospital", "hospital",
                " (v5.1 narrows 'hospital' to a hospital with an A&E; earlier versions count any hospital "
                "site, so the two are different measures)"),
    _ahah_drive("leisure_centre", "leisure centre"),
    _ahah_drive("bluespace", "blue space (water)"),
    _ahah_drive("fast_food", "fast food outlet", _AHAH_HAZARD),
    _ahah_drive("gambling", "gambling venue", _AHAH_HAZARD),
    _ahah_drive("pub_bar", "pub or bar", _AHAH_HAZARD),
    _ahah_drive("tobacco", "tobacco or vape retailer", _AHAH_HAZARD),
    _ahah_air("no2", "nitrogen dioxide (NO2)"),
    _ahah_air("so2", "sulphur dioxide (SO2)"),
    _ahah_air("pm10", "particulate matter (PM10)"),
    PredicateDef("ahah_greenspace_ndvi", "real", "single", ("area",),
                 "Passive greenspace: the median Normalised Difference Vegetation Index (NDVI, about 0 to 1, "
                 "higher = greener) over the LSOA, from satellite imagery" + _AHAH_COMMON,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    _ahah_pct("combined", "combined AHAH index"),
    _ahah_pct("health_services", "health services domain (GP, dentist, pharmacy, hospital, leisure centre)"),
    _ahah_pct("green_blue_space", "green and blue space domain"),
    _ahah_pct("air_quality", "air quality domain (NO2, SO2, PM10)"),
    _ahah_pct("retail_hazards", "retail hazards domain (fast food, gambling, pubs and bars, tobacco)"),
)

# PROPOSED, HOLD (card c1332; phase 11 exit 6, scope 11.6): life expectancy, healthy life expectancy and fuel
# poverty. Registers countersigned [sig:55e8e1e2]: REQ-arloesidolgellau-837c00 (ONS HLE, UK), c4f429 (ONS LE/HLE
# by WIMD 2019 quintile, Wales) and 513c1d (Welsh Government fuel poverty, Wales level only [sig:aa8f1685]). One
# predicate per thing; the sex, age band, period and any quintile or breakdown ride value_en.
_EXIT6_PLACE = " Of the area's population, never any person or household in it."
_EXIT6_LIFE = (
    " A period life table figure in YEARS for the three-year period in value_en, for the sex and age band named "
    "there (at birth is age band '<1'): the years a person of that age would live if that period's death (and "
    "health) rates held for life, not a prediction for anyone. Per area as published: a Welsh local authority "
    "(W06), health board (W11) or Wales (W92), or Wales by WIMD 2019 deprivation quintile where value_en names "
    "the quintile (1 = most deprived). Where the source publishes a confidence interval beside the figure, it rides "
    "the confidence_interval qualifier, verbatim as published; otherwise it is in the citation's source.")
_EXIT6_GAP = (
    " The gap in YEARS between the most and least deprived fifths of Wales, by WIMD 2019 quintile, for the sex, "
    "age band and three-year period in value_en, as ONS publishes it: value_en names the measure, the 'range' "
    "(the least deprived quintile 5 minus the most deprived quintile 1, the years more in the least deprived "
    "fifth; ONS's note calls it the difference between quintile 1 and quintile 5) or the 'Slope Index of "
    "Inequality' (the difference across the population-"
    "weighted regression line from most to least deprived). A period life table figure, not a prediction for "
    "anyone.")
_EXIT6_FUEL = (
    " A modelled estimate for Wales as at the year in value_en (Welsh Government, BREDEM model on the Welsh "
    "Housing Conditions Survey 2017-18, full income definition), at Wales level only [sig:aa8f1685]: no local "
    "authority or LSOA figure is published. A household is fuel poor if it would need to spend more than 10% of "
    "its income on a satisfactory heating regime (severe: more than 20%; at risk: 8 to 10%); value_en names the "
    "status and, where published, the household or dwelling group. Definitions changed between 2018 and 2021, "
    "so years are compared with caution.")
_EXIT6: tuple[PredicateDef, ...] = (
    PredicateDef("life_expectancy_years", "real", "multi", ("area",),
                 "Life expectancy." + _EXIT6_LIFE + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    PredicateDef("healthy_life_expectancy_years", "real", "multi", ("area",),
                 "Healthy life expectancy: the years lived in 'good' or 'very good' general health, as people "
                 "self-reported it in the survey behind the estimate." + _EXIT6_LIFE + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    PredicateDef("good_health_life_share_pct", "real", "multi", ("area",),
                 "The proportion (per cent, 0 to 100) of remaining life spent in 'good' or 'very good' "
                 "self-reported health, as published beside healthy life expectancy, for the period, sex, age "
                 "band and any quintile in value_en." + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    PredicateDef("life_expectancy_gap_years", "real", "multi", ("area",),
                 "Life expectancy inequality gap." + _EXIT6_GAP + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    PredicateDef("healthy_life_expectancy_gap_years", "real", "multi", ("area",),
                 "Healthy life expectancy inequality gap ('good' or 'very good' self-reported health)."
                 + _EXIT6_GAP + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    PredicateDef("fuel_poverty_households_count", "int", "multi", ("area",),
                 "Number of households, rounded by the publisher to the nearest 1,000, by fuel poverty status "
                 "(value_en)." + _EXIT6_FUEL + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
    PredicateDef("fuel_poverty_households_share", "real", "multi", ("area",),
                 "Share of households, as a fraction 0 to 1 calculated by the publisher from unrounded figures, "
                 "by fuel poverty status (value_en)." + _EXIT6_FUEL + _EXIT6_PLACE,
                 description_cy=CY_PENDING, finest_grain=Grain.AREA),
)


# ---------------------------------------------------------------------------
# Emergency care facility type (RATIFIED by Huw [sig:3277a240]; phase 11 scope 11.4 / exit 4, card c1352 after c1334).
# Huw [sig:e8842016]: A&E sites come from REQ-arloesidolgellau-8fcae2 (StatsWales 3ce1cc28, OGL-3.0),
# extended by the c1342 use transition; a site is A&E when its Hospital Type is 'Major Emergency
# Departments' in the latest month, joined to ods-wlhbsite by ODS site code, with the month recorded on
# every flag. The two values are the publisher's own labels below its 'All Emergency Care Facilities'
# total, enforced (validation.py VALUE_CHECKED_PREDICATES), so a renamed label stops a build.
# ---------------------------------------------------------------------------
EMERGENCY_CARE_FACILITY_TYPES: tuple[str, ...] = (
    "Major Emergency Departments", "Other Emergency Departments/Minor Injury Units",
    "ECDS Type 1 & 2 (England)")                     # + the English ECDS value, 0.2.52 (card c1545)

_EMERGENCY_CARE: tuple[PredicateDef, ...] = (
    PredicateDef("emergency_care_facility_type", "text", "single", ("nhs_org",),
                 "The type of emergency care facility an NHS site reports under, VERBATIM from the "
                 "'Hospital Type' field of StatsWales' emergency department performance dataset "
                 "(3ce1cc28): 'Major Emergency Departments' or 'Other Emergency Departments/Minor Injury "
                 "Units'. The site is an A&E when the value is 'Major Emergency Departments'. Read for "
                 "one month, which semantics_caveat must name: a site's type can change between months "
                 "(Nevill Hall and Royal Gwent reported as major departments before the Grange opened). "
                 "The publisher's field, never inferred from a site's name, size or services; absence "
                 "means the site does not report emergency department performance, nothing more. "
                 "For an English site the value is 'ECDS Type 1 & 2 (England)': the site reports Type 1 & 2 "
                 "attendances in NHS England's ECDS site-level activity (REQ-arloesidolgellau-90d742), which "
                 "publishes Type 1 and Type 2 together at site level, and its trust reports Type 1 attendances "
                 "in the same month's A&E figures; semantics_caveat names the month.",
                 constraint_json=json.dumps({"enum": list(EMERGENCY_CARE_FACILITY_TYPES)}),
                 required_qualifiers=("semantics_caveat",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
)

# Card c1545 (Lludd Code seat 3; queued 2026-10-22T11:37:06Z on c1537, Huw's yes to all five c1537 questions
# [sig:f1f70215]): Lludd AWE-009 phase 12. Items 12.1 (pharmacies and dental practices as sites, each with a cluster)
# and 12.3 (English A&Es flagged as English). nhs_org_role and emergency_care_facility_type gain terms in place.
_LLUDD_PHASE12: tuple[PredicateDef, ...] = (
    PredicateDef("premises_in_cluster", "entity_ref", "single", ("nhs_org",),
                 "The GP primary care cluster whose footprint holds the LSOA of the organisation's premises, "
                 "written `cluster:<publisher code>`: the premises' premises_in_lsoa joined to that LSOA's "
                 "area_in_cluster (Data Map Wales' footprints, a best fit by registration). LOCATION, NOT "
                 "MEMBERSHIP: it does not say the organisation belongs to or serves the cluster (that is "
                 "in_cluster, for a GP practice, from the publisher's cluster list). semantics_caveat must say so. "
                 "Absent for premises in an LSOA no footprint holds (England).",
                 required_qualifiers=("semantics_caveat",),
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
    PredicateDef("premises_in_country", "entity_ref", "single", ("nhs_org",),
                 "The country that contains the organisation's premises, written `area:<country GSS code>` "
                 "(W92000004 Wales, E92000001 England), from the ONS Postcode Directory's country of the "
                 "premises postcode. CONTAINMENT only. It flags an English site carried as a destination "
                 "for Welsh areas, so a Welsh-only figure never counts it.",
                 description_cy=CY_PENDING,
        finest_grain=Grain.NOT_SPATIAL,
    ),
)

SEED_PREDICATES: tuple[PredicateDef, ...] = (
    _BUILDING + _TENANCY + _EVENT + _RESEARCH_QUESTION + _SOURCE + _TOWN
    + _ENERGY_DEMAND + _HYDROLOGY + _EPC + _PLANNING + _BGS_SEARCHES + _HERITAGE_SEARCHES
    + _HERITAGE_ENRICHMENT + _COAL_SEARCH + _ROAD_PROXIMITY + _REACHABILITY
    + _OPEN_ACCESS + _AREA_BACKFILL + _SPINE_AND_GP_BACKFILL + _CLIMATE_SWEEP + _AREA
    + _CLIMATE_ALLOWANCES + _OPEN_EVIDENCE + _LLUDD_DIALYSIS + _LLUDD_HEALTH + _NHS_ORG
    + _WIMD_DOMAINS + _CARE_HOMES + _CARE_DELAYS_AND_ADVERTS
    + _PHASE11_ROUND2 + _PPFI_AND_CLUSTER + _CENSUS_PHASE11 + _LLEFELYS_COMMUNITY
    + _LLEFELYS_CENSUS + _LLEFELYS_JOBS_FIRMS + _AHAH + _EXIT6 + _EMERGENCY_CARE + _LLEFELYS_WAGES_WORK + _LLEFELYS_SUPPLY
    + _LLEFELYS_PHASE13 + _LLUDD_PHASE12 + _LLEFELYS_L2_FLOWS
)

# Name -> PredicateDef, for fast lookup by the validation contract.
PREDICATE_REGISTRY: dict[str, PredicateDef] = {
    p.name: p for p in SEED_PREDICATES
}

# Import-time invariant: a duplicate predicate name would silently shadow
# in PREDICATE_REGISTRY. 143 distinct names expected: 60 v0.1 seed (58 +
# §10 item 7's verified_building_toid + location_verification_status), the
# 4 Egni demand predicates (_ENERGY_DEMAND, 2026-07-20), the 34 ratified
# 2026-07-22 additions — 17 EPC (_EPC), 15 planning (_PLANNING), 2 BGS
# searches (_BGS_SEARCHES) — the 4 heritage-designation search predicates
# (_HERITAGE_SEARCHES, 2026-07-24), + `near_scheduled_monument` (variable-radius,
# 2026-07-24; the fixed `_250m` deprecated-but-retained), + 5 heritage
# ENRICHMENT predicates (_HERITAGE_ENRICHMENT, 2026-07-24), + the coal
# Development-High-Risk-Area search predicate (_COAL_SEARCH, 2026-07-25), + the
# strategic-road proximity predicate (_ROAD_PROXIMITY, 2026-07-26), + the 3
# reachability predicates (_REACHABILITY, 2026-07-26, constitution 0.1.4) = 113, + the
# 2 open-access predicates (_OPEN_ACCESS, Tier-A A5, 2026-07-27) = 115, + the 4
# area predicates four published layers were already using unregistered
# (_AREA_BACKFILL, 2026-07-27) = 119, + the 7 found by scanning every module
# rather than only the committed snapshots — 2 UPRN-spine join identifiers,
# the gazetteer settlement rank, and 4 GP-layer predicates
# (_SPINE_AND_GP_BACKFILL, 2026-07-27) = 126, + the 4 EA Hydrology predicates on the
# new `station` kind (_HYDROLOGY, constitution 0.1.5, 2026-08-07, sig:c659a12f) = 130, + the 9
# climate-sweep predicates (_CLIMATE_SWEEP, constitution 0.1.6, 2026-08-07, sig:7508450d) = 139,
# + the 2 DESNZ predicates ratified Llys 09/08/2026 [sig:7577b7d1] into the EXISTING _ENERGY_DEMAND
# group (`off_gas_grid_properties`, `energy_efficiency_measures_installed`) = 141, + the 2 Welsh
# heritage predicates ratified 11/08/2026 [Llys R1+R2 ACCEPT, welsh-heritage-predicates-ruling] into
# the EXISTING _HERITAGE_SEARCHES group (`within_world_heritage_site`,
# `within_registered_historic_landscape`) = 143, + `tide_level` into the EXISTING _HYDROLOGY group
# (constitution 0.1.8, Llys 26/09/2026 [sig:c8426dc4]) = 144 — added inside a group, so named here.
# + `source_kind` into the EXISTING _SOURCE group (constitution 0.1.9, awen-weave 0.2.26) = 145 —
# also inside a group, so named here (0.2.26 did not extend this tally; recorded on its rebase).
# + the 3 Welsh Government allowance predicates (_CLIMATE_ALLOWANCES, a NEW group, Llys 02/10/2026
# [sig:dc82671f], awen-weave 0.2.27) = 148.
# + the 8 Open Evidence predicates (_OPEN_EVIDENCE, a NEW group, Llys 04/10/2026 [sig:a40a1dcd],
# awen-weave 0.2.28) = 156. P-1 and P-2 widen and close existing predicates; they add no name.
# + the 3 Lludd dialysis predicates (_LLUDD_DIALYSIS, a NEW group, Llys 05/10/2026 [sig:75935d1b],
# awen-weave 0.2.29) = 159. A-1 rewords ods_code and operational_status; it adds no name.
# + `within_protected_wreck` into the EXISTING _HERITAGE_SEARCHES group (Llys 01/09/2026
# [sig:57ce9e14]) and `population_projection` into the EXISTING _AREA_BACKFILL group (proposed
# under Llys 09/10/2026 [sig:91605acd]), awen-weave 0.2.30 = 161 — both inside groups, so named here.
# + the 13 Lludd step-0 health predicates (_LLUDD_HEALTH, a NEW group, card c0616, PROPOSED in the
# same 0.2.30 release) = 174.
# + `usual_residents_count` and `households_car_van_availability_count` into the EXISTING
# _ENERGY_DEMAND group beside heating_fuel_share (Census 2021, card c0628, PROPOSED in awen-weave
# 0.2.31) = 176 — inside a group, so named here.
# + the six Census 2021 wave 2 predicates into _ENERGY_DEMAND beside them (card c0840, PROPOSED in
# awen-weave 0.2.32) = 182 — also inside the group, so named here.
# + the 8 NHS organisation predicates (_NHS_ORG, a NEW group, card c0944, PROPOSED in awen-weave
# 0.2.37 with constitution 0.1.10) = 190.
# + the 8 WIMD 2025 domain ranks (_WIMD_DOMAINS, a NEW group, card c1012, ruled [sig:0c677900],
# PROPOSED in awen-weave 0.2.39) = 198.
# + the 11 CIW care home predicates (_CARE_HOMES, a NEW group, card c1055, ruled [sig:7d9c7466],
# PROPOSED in awen-weave 0.2.41) = 209.
# + the 4 care delays and 1 online job adverts predicates (_CARE_DELAYS_AND_ADVERTS, a NEW group,
# PROPOSED for the next release, cards c1125/c1130/c1132; not yet ruled) = 214.
# + 4 GP practice deprivation and 1 food outlets predicates (_PHASE11_ROUND2, a NEW group, PROPOSED,
# card c1181) = 219.
# + the 16 PPFI v2.1 rank and decile predicates and area_in_cluster (_PPFI_AND_CLUSTER, a NEW group,
# PROPOSED, card c1181) = 236.
# + 5 Census 2021 phase 11 predicates (_CENSUS_PHASE11, a NEW group, PROPOSED, HOLD, card c1209) = 241.
# + area_in_community (_LLEFELYS_COMMUNITY, a NEW group, card c1232, RATIFIED [sig:1ffc4503]) = 242.
# + usual_residents_highest_qualification_count (_LLEFELYS_CENSUS, a NEW group, PROPOSED, HOLD, cards c1272/c1281) = 243.
# + bres_employment_count, enterprises_count, local_units_count (_LLEFELYS_JOBS_FIRMS, a NEW group, PROPOSED, HOLD, cards c1297/c1281) = 246.
# + 19 AHAH predicates (_AHAH, a NEW group, PROPOSED, HOLD, card c1321; phase 11 scope 11.2, F2) = 265.
# + 7 exit 6 predicates (_EXIT6, a NEW group, PROPOSED, HOLD, card c1332): life and healthy life expectancy, their gaps, good-health share, fuel poverty = 272.
# + aps_estimate_pct, earnings_median_annual_gross_gbp, earnings_median_hourly_excl_overtime_gbp (_LLEFELYS_WAGES_WORK, a NEW group, RATIFIED [sig:018a430b], cards c1317/c1298), after emergency_care_facility_type (_EMERGENCY_CARE, card c1352, 273) = 276.
# + public_contract_supplier_awards_count, public_contract_award_value_gbp (_LLEFELYS_SUPPLY, a NEW group, RATIFIED [sig:018a430b], cards c1318/c1304), after _LLEFELYS_WAGES_WORK (#58, 276) = 278.
# + usual_residents_welsh_speaking_count, bres_employment_location_quotient (_LLEFELYS_PHASE13, a NEW group, RATIFIED [sig:8e70be16], card c1487); usual_residents_welsh_language_skills_count description only = 280.
# + premises_in_cluster, premises_in_country (_LLUDD_PHASE12, a NEW group, card c1545, Huw's yes [sig:f1f70215]); nhs_org_role and emergency_care_facility_type gain terms inside their groups = 282.
# + community_wider_area, residents_by_place_of_work_count (_LLEFELYS_L2_FLOWS, a NEW group, RATIFIED [sig:a884ac2d] and [sig:3c709fd0], card c1626) = 284.
#
# THOSE LAST FOUR ARE WHY THE TALLY WAS STALE, and the shape is worth naming rather than just
# correcting: every addition BEFORE them arrived as a NEW group, and adding a group is visible in
# the concatenation below, so the tally got updated. These four were added INSIDE two existing
# groups, which changes no line the tally mentions — so the running total silently stopped being a
# count of the code. Re-measured 12/09/2026 against 2f16659 (dispatch 199 §0): len(SEED_PREDICATES)
# == len(PREDICATE_REGISTRY) == 143, and the group sums agree. The tally is KEPT rather than
# replaced with a bare 143 — it is the file's provenance, and the invariant below is what actually
# enforces the number.
#
# 12/09/2026, AWE-004: alc_grade MOVED out of _AREA_BACKFILL into its own
# _AREA group, carrying the pinned read-contract definition and a declared
# finest_grain. The name count is unchanged at 143 — one entry superseded by
# one entry, not an addition — and _AREA_BACKFILL is now 3.
if len(PREDICATE_REGISTRY) != len(SEED_PREDICATES):
    raise RuntimeError("duplicate predicate name in SEED_PREDICATES")

# False-friend integrity: every register entry must name a REAL registered predicate,
# and its `use_instead` must be real (or "-"). A dangling entry would misdirect a consumer.
for _ff in FALSE_FRIENDS:
    if _ff.name not in PREDICATE_REGISTRY:
        raise RuntimeError(f"FALSE_FRIENDS names unregistered predicate {_ff.name!r}")
    if _ff.use_instead != "-" and _ff.use_instead not in PREDICATE_REGISTRY:
        raise RuntimeError(
            f"FALSE_FRIENDS[{_ff.name!r}].use_instead {_ff.use_instead!r} is not registered"
        )


# ---------------------------------------------------------------------------
# TASK 8.6 IS DONE — THE INTERIM IS GONE, AND 8.2 NOW APPLIES WITHOUT EXCEPTION
# ---------------------------------------------------------------------------
# WHAT WAS HERE AND WHY IT IS NOT. Between 8.5 and 8.6 this module carried a
# frozen `INTERIM_UNDECLARED` list — the 143 predicates registered before the
# grain rule existed, pinned by digest so the list could only ever SHRINK. Its
# own instruction was: "when the list empties, this block and the branch in
# `validate_predicate_def` that reads it are deleted and 8.2 applies without
# exception." Task 8.6 emptied it on 2026-09-12 (dispatch 200) and this is that
# deletion. The digest guard fired on the empty list exactly as designed, which
# is how the emptying was noticed rather than assumed.
#
# THE EXEMPTION IS NOT WIDENED, IT IS REMOVED. There is no longer any list a
# writer could add a name to, so the only way a predicate reaches the registry
# without a grain is if this assertion is deleted — a visible act, not a line
# appended to a register. `Grain.UNDECLARED` survives as the FIELD DEFAULT so
# that "absent" is still a typed, refusable state rather than a crash; what has
# gone is anything that forgives it.
def undeclared_predicates() -> tuple[str, ...]:
    """The registered predicates whose grain nobody has evidenced.

    EMPTY since task 8.6, and asserted empty at import below. Read this rather
    than asserting the rule is on — it is the reporting half that made 8.6's
    outstanding surface visible while it existed, and it is kept so that a
    future regression is reportable and not merely raisable.
    """
    return tuple(
        name for name, p in PREDICATE_REGISTRY.items()
        if p.finest_grain is Grain.UNDECLARED
    )


def _assert_grain_declarations(predicates: tuple[PredicateDef, ...]) -> None:
    """Import-time invariant: NO predicate may carry an undeclared grain.

    This is the registrar's second line (task 8.5): even a predicate added
    straight into this module — reaching no validator, no CLI and no gate —
    cannot carry a missing grain. Lifted out as a function so it can be tested
    against a hypothetical set rather than only against the real one.

    Before 8.6 this tolerated the frozen interim list. It no longer does, and
    that is the whole of what 8.6 changed here.
    """
    undeclared = sorted(p.name for p in predicates
                        if p.finest_grain is Grain.UNDECLARED)
    if undeclared:
        raise RuntimeError(
            f"predicate(s) {undeclared} carry no finest_grain — ABSENT IS NOT "
            f"A WILDCARD (phase 8 task 8.2, and the interim that once excused "
            f"this was removed by task 8.6 on 2026-09-12). Declare one of "
            f"{', '.join(g.value for g in sorted(DECLARED_GRAINS, key=lambda g: g.value))}: "
            f"the finest grain this predicate's SOURCE supports."
        )


_assert_grain_declarations(SEED_PREDICATES)
