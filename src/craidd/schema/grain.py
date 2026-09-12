"""
src/craidd/schema/grain.py — the grain vocabulary and its ORDER.

    A predicate declares the finest grain its source supports. A claim may be
    at that grain or coarser, NEVER finer. A predicate registered with no
    `finest_grain` is refused, because absent is not a wildcard.

Accepted by Huw as Llys on 25/08/2026 against
`IDR-006 Awen/GRAIN-ENFORCEMENT-grammar-proposal-2026-08-19.md`; PHASES.yaml
phase 8, tasks 8.1-8.5. Enforced in `validation.py`; this module holds only the
vocabulary, the order, and the entity-type classification the rule reads.

THE VALUE SET — RULED BY HUW AS LLYS, 12/09/2026, THREE EXPLICIT VALUES
(`RULING-to-199-seat-grain-value-set-2026-09-12.md`; coordinator record
`[sig:00fa9f13]`). The 25/08 acceptance fixed that grain lives on the
PREDICATE; it did not fix the set.

    property     — finer than —
    area           the ordered pair for SPATIAL subjects. "At that grain or
                   coarser" is defined over these two and only these two.
    not_spatial  — predicates whose subjects are not places: `event`,
                   `tenancy`, `source`, `research_question`. EXPLICIT, NEVER A
                   DEFAULT. A grain check against a `not_spatial` predicate is
                   not applicable and says so — it is not a pass and not a
                   wildcard.

`station` and `coastal_cell` subjects are point/cell ASSETS and sit at the
`property` (finest) end, per the same ruling; task 8.6 flags any predicate
whose source evidence disagrees.

The third value exists so that "absent is not a wildcard" can be true of every
one of the 143 registered predicates without forcing a FALSE value on the 54
whose subjects are not places (measured 12/09/2026: 44 non-spatial + 10 asset
grain — see ENTITY_TYPE_GRAIN). Absent stays refused for all 143: task 8.2 is
unchanged by the third value.

A FOURTH VALUE IS A RULING, NOT AN EDIT. That is why the enumeration and its
order live here, in one place, and why no caller holds a classification of its
own — the refusal logic in `validation.py` reads this module and nothing else.

WHY THE ORDER IS THE POINT, and why this is not three strings. The rule is "at
that grain or coarser", which is a comparison. Interchangeable strings would
make every caller re-derive which is finer, and the first caller to get it
backwards would refuse every legitimate roll-up in the estate. So the order is
declared once and `is_finer_than` is the only way to ask.

WHY THIS IS REGISTRY-TIER AND NOT A CONSTITUTION CHANGE, verified rather than
assumed (PHASES.yaml phase 8 `tier_verification_do_not_lose_this`, and
re-affirmed by the 12/09 ruling): the constitution's qualifier key set is CLOSED
at 23 with `additionalProperties: false` at v0.1.7, so a per-CLAIM grain field
would be Tier-1. Grain sits on the PREDICATE, and predicates are an open
registry — the same tier as adding a predicate, an awen-weave minor. If a later
reading proposes moving grain onto the claim, that is Tier-1 and it goes back to
Llys.

NAMING NOTE, recorded because the estate holds a near-neighbour vocabulary:
awen-source-catalogue's `spines.py` types its two join spines `property` and
`PLACE`, not `property` and `AREA`. That field is the spine's grain, this one is
the source's grain, and they are not the same field — but a reader will meet
both, and 8.6's method reads the catalogue's value to evidence this one. The
accepted grammar says `area`, so `area` is what this module uses; the
divergence is reported rather than reconciled unilaterally.
"""
from __future__ import annotations

from enum import Enum

from .entity_types import VALID_ENTITY_TYPES


class UndeclaredGrainError(ValueError):
    """Raised when a grain ORDER comparison is attempted against a value that
    has no position in the order — `UNDECLARED` or `NOT_SPATIAL`.

    UNDECLARED is a staging marker for task 8.6; NOT_SPATIAL is a real ruled
    value that is deliberately outside the order. If either could be ordered it
    would quietly become a third point on the scale, and "we have not
    established this predicate's grain" (or "this subject is not a place")
    would start reading as a fact about spatial resolution. It raises instead.
    """


class Grain(str, Enum):
    """The CLOSED value set — three ruled values and a staging marker.

    `property`    — the finest: one identified thing on the ground (a property,
                    a parcel, a gauge, a coastal cell). The UPRN spine.
    `area`        — a bounded/administrative/statistical area. The gazetteer
                    GSS spine.
    `not_spatial` — the subject is not a place at all (an event, a tenancy, a
                    citation, a research question). The grain check is NOT
                    APPLICABLE and says so.

    Ruled by Huw as Llys 12/09/2026. A fourth value is a ruling, not an edit.
    """

    PROPERTY = "property"
    AREA = "area"
    NOT_SPATIAL = "not_spatial"

    #: NOT A RULED VALUE. The interim marker carried by the predicates
    #: registered before the rule existed, which task 8.6 replaces with a value
    #: evidenced against each predicate's source. It is inside the enum so the
    #: field's type stays closed — an arbitrary string is still refused — and
    #: outside GRAIN_ORDER so it can never be compared.
    UNDECLARED = "undeclared"


#: The order IS the rule, and it is defined over the SPATIAL pair only: finest
#: first. NOT_SPATIAL and UNDECLARED are absent by construction.
GRAIN_ORDER: tuple[Grain, ...] = (Grain.PROPERTY, Grain.AREA)

#: The three values a predicate may actually declare once task 8.6 has run.
DECLARED_GRAINS: frozenset[Grain] = frozenset(GRAIN_ORDER) | {Grain.NOT_SPATIAL}


def grain_rank(grain: Grain) -> int:
    """Position in GRAIN_ORDER — smaller is finer. Raises for any value with no
    position in the order (`not_spatial`, `undeclared`)."""
    try:
        return GRAIN_ORDER.index(grain)
    except ValueError:
        raise UndeclaredGrainError(
            f"{grain!r} has no position in the grain order — it cannot be "
            f"compared (the order is defined over the spatial pair, finest "
            f"first: {', '.join(g.value for g in GRAIN_ORDER)})"
        ) from None


def is_finer_than(candidate: Grain, declared: Grain) -> bool:
    """True iff `candidate` is FINER than `declared` — the refusal condition.

    Equal grain is not finer, and coarser is not finer: both are legal. Raises
    if either side has no position in the order, so an undeclared predicate can
    never be silently treated as permitting everything and a `not_spatial` one
    can never be silently ranked against a place.
    """
    return grain_rank(candidate) < grain_rank(declared)


# ---------------------------------------------------------------------------
# Entity type -> grain. TOTAL over VALID_ENTITY_TYPES, asserted at import.
# ---------------------------------------------------------------------------
# A claim's grain is the grain of its SUBJECT, and the subject's grain follows
# from its entity type. The map is TOTAL and its totality is asserted below:
# entity type thirteen cannot be added without classifying it, because an
# unclassified type would make the grain rule silently inapplicable to every
# claim about it — "the gate whose input set can be empty must fail loud on
# empty" (the standing lesson task 8.2 cites). There is no `None` and no
# default: every entity type carries one of the three ruled values.
#
# MEASURED 12/09/2026 against awen-weave 0.2.20 at 2f16659, over the 143
# registered predicates' `applies_to_types` — this is the shape of task 8.6's
# surface, and it is why the third value was ruled:
#   property-end  building 58 · (building, site, area) 5 · station 4
#                 · coastal_cell 3 · (coastal_cell, station) 2 · (area, station) 1
#   area-end      area 18 · town 8
#   not_spatial   event 23 · source 8 · tenancy 7 · research_question 6  = 44
# `applies_to_types` is EVIDENCE OF THE SUBJECT, not of the source's
# resolution, so it constrains task 8.6 rather than deciding it: a predicate
# may apply to `building` and still have an area-grain source (that is exactly
# the `alc-predictive-wales` fault), and the registration check below is what
# refuses that combination once a grain is declared.
ENTITY_TYPE_GRAIN: dict[str, Grain] = {
    # the two join spines the estate already runs — not judgement calls
    "building": Grain.PROPERTY,      # UPRN spine
    "area": Grain.AREA,              # gazetteer GSS spine
    "town": Grain.AREA,
    # point/cell assets — ruled to the `property` (finest) end, 12/09/2026
    "station": Grain.PROPERTY,
    "coastal_cell": Grain.PROPERTY,
    # this seat's reading, stated as a reading: a parcel is one identified
    # thing on the ground; a street is an extent and says nothing about any
    # single address on it. `site` co-occurs only with `building` in the
    # registry (5 predicates) and `street` carries none, so neither changes a
    # verdict today.
    "site": Grain.PROPERTY,
    "street": Grain.AREA,
    # not places at all — the ruled third value, explicit and never a default
    "tenancy": Grain.NOT_SPATIAL,
    "event": Grain.NOT_SPATIAL,
    "research_question": Grain.NOT_SPATIAL,
    "source": Grain.NOT_SPATIAL,
    "person": Grain.NOT_SPATIAL,
}

_missing = VALID_ENTITY_TYPES - set(ENTITY_TYPE_GRAIN)
_extra = set(ENTITY_TYPE_GRAIN) - VALID_ENTITY_TYPES
if _missing or _extra:
    raise RuntimeError(
        "ENTITY_TYPE_GRAIN must classify EVERY entity type and no others — "
        f"unclassified: {sorted(_missing)}; not an entity type: {sorted(_extra)}. "
        "An unclassified entity type makes the grain rule silently inapplicable "
        "to every claim about it."
    )
_offset = {t: g for t, g in ENTITY_TYPE_GRAIN.items() if g not in DECLARED_GRAINS}
if _offset:
    raise RuntimeError(
        f"ENTITY_TYPE_GRAIN may only use the ruled values "
        f"{sorted(g.value for g in DECLARED_GRAINS)} — found {_offset}"
    )
del _missing, _extra, _offset


def grain_of_entity_type(entity_type: str) -> Grain:
    """The grain of a subject of this entity type — one of the three ruled
    values, never None.

    Raises KeyError for an unknown entity type, so a typo cannot read as
    "nothing to check here".
    """
    return ENTITY_TYPE_GRAIN[entity_type]
