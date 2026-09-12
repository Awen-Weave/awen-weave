"""Phase 8 tasks 8.1–8.5 — grain enforcement at registration.

THE RULE (accepted by Huw as Llys, 25/08/2026, on
`IDR-006 Awen/GRAIN-ENFORCEMENT-grammar-proposal-2026-08-19.md`):

    A predicate declares the finest grain its source supports. A claim may be
    at that grain or coarser, NEVER finer. A predicate registered with no
    `finest_grain` is refused, because absent is not a wildcard.

EVERY ASSERTION IN THIS FILE WAS RUN AGAINST THE PRE-RULE CODE FIRST and seen
to fail; the pre-rule run is quoted in the dispatch-199 report. That is exit
condition 2's own wording — "proven to fail BEFORE the rule was added" — and it
is why the "the old code accepted this" tests below are kept rather than
deleted once green: they are the before-side of the diff, expressed as code.

THE VALUE SET IS THREE, RULED BY HUW AS LLYS 12/09/2026 (`RULING-to-199-seat-
grain-value-set-2026-09-12.md`, coordinator record `[sig:00fa9f13]`):
`property` finer than `area` for spatial subjects, and `not_spatial` for
predicates whose subjects are not places. The ORDER is defined over the spatial
pair and is the rule itself, so it is encoded as an order and never as
interchangeable strings. Absent stays refused for all 143.
"""
from __future__ import annotations

import pytest

from craidd.schema.grain import (
    DECLARED_GRAINS,
    ENTITY_TYPE_GRAIN,
    GRAIN_ORDER,
    Grain,
    UndeclaredGrainError,
    grain_of_entity_type,
    grain_rank,
    is_finer_than,
)
from craidd.schema.entity_types import VALID_ENTITY_TYPES
from craidd.schema.predicates import (
    INTERIM_UNDECLARED,
    PREDICATE_REGISTRY,
    PredicateDef,
)
from craidd.schema.validation import validate_claim, validate_predicate_def


# --------------------------------------------------------------------------
# 8.1 — `finest_grain` on the predicate, a CLOSED value set that is ORDERED
# --------------------------------------------------------------------------

def test_the_value_set_is_closed_and_the_spatial_pair_is_ordered_finest_first():
    """THREE ruled values (Huw as Llys, 12/09/2026): `property` finer than
    `area` for spatial subjects, plus `not_spatial`. The ORDER is defined over
    the spatial pair only. A fourth value is a ruling, not an edit, so the set
    is asserted by identity rather than by membership."""
    assert DECLARED_GRAINS == {Grain.PROPERTY, Grain.AREA, Grain.NOT_SPATIAL}
    assert GRAIN_ORDER == (Grain.PROPERTY, Grain.AREA)
    assert grain_rank(Grain.PROPERTY) < grain_rank(Grain.AREA)
    assert is_finer_than(Grain.PROPERTY, Grain.AREA)
    assert not is_finer_than(Grain.AREA, Grain.PROPERTY)
    assert not is_finer_than(Grain.AREA, Grain.AREA)


def test_nothing_outside_the_spatial_pair_can_be_ordered():
    """UNDECLARED is a staging marker for task 8.6 and NOT_SPATIAL is a ruled
    value deliberately outside the order. If either could be ranked it would
    silently become a third point on the scale — a claim would compare against
    it and get an answer. Both raise instead."""
    assert Grain.UNDECLARED not in GRAIN_ORDER
    assert Grain.NOT_SPATIAL not in GRAIN_ORDER
    for off_scale in (Grain.UNDECLARED, Grain.NOT_SPATIAL):
        with pytest.raises(UndeclaredGrainError):
            grain_rank(off_scale)
        with pytest.raises(UndeclaredGrainError):
            is_finer_than(Grain.PROPERTY, off_scale)


def test_a_predicate_carries_finest_grain():
    p = PredicateDef("t", "text", "single", ("building",), "d", "c",
                     finest_grain=Grain.PROPERTY)
    assert p.finest_grain is Grain.PROPERTY


def test_every_entity_type_is_classified_and_the_map_is_total():
    """The gate whose input set can be empty must fail loud on empty. A new
    entity type with no grain classification would make the rule silently
    inapplicable to it, so the map is TOTAL over VALID_ENTITY_TYPES and this
    test is the thing that fails when entity type thirteen arrives."""
    assert set(ENTITY_TYPE_GRAIN) == set(VALID_ENTITY_TYPES)
    assert grain_of_entity_type("building") is Grain.PROPERTY
    assert grain_of_entity_type("area") is Grain.AREA
    # point/cell assets sit at the finest end (ruled 12/09/2026)
    assert grain_of_entity_type("station") is Grain.PROPERTY
    assert grain_of_entity_type("coastal_cell") is Grain.PROPERTY
    # subjects that are not places carry the EXPLICIT third value — never a
    # default, and never None.
    assert grain_of_entity_type("source") is Grain.NOT_SPATIAL
    assert all(g in DECLARED_GRAINS for g in ENTITY_TYPE_GRAIN.values())


def test_an_unknown_entity_type_is_an_error_not_a_silent_none():
    with pytest.raises(KeyError):
        grain_of_entity_type("not-an-entity-type")


# --------------------------------------------------------------------------
# 8.2 — absent is REFUSED at registration; absent is not a wildcard
# --------------------------------------------------------------------------

def test_a_predicate_with_no_finest_grain_is_refused_at_registration():
    """THE CORE OF 8.2. Before the rule this predicate validated clean — that
    run is quoted in the report. The refusal must NAME the predicate."""
    grainless = PredicateDef("brand_new_predicate", "text", "single",
                             ("building",), "d", "c")
    errors = validate_predicate_def(grainless)
    assert errors, "a grain-less predicate must be refused"
    assert any("finest_grain" in e and "brand_new_predicate" in e
               for e in errors), errors


def test_the_refusal_says_absent_is_not_a_wildcard():
    errors = validate_predicate_def(
        PredicateDef("another_new_one", "text", "single", ("area",), "d", "c"))
    assert any("NOT A WILDCARD" in e.upper() for e in errors), errors


def test_a_grain_outside_the_closed_set_is_refused():
    """A closed set nothing checks is an open set with a comment."""
    errors = validate_predicate_def(
        PredicateDef("bad_grain", "text", "single", ("area",), "d", "c",
                     finest_grain="parish"))          # type: ignore[arg-type]
    assert any("finest_grain" in e for e in errors), errors


def test_a_declared_predicate_passes():
    assert validate_predicate_def(
        PredicateDef("fine_one", "text", "single", ("building",), "d", "c",
                     finest_grain=Grain.PROPERTY)) == []


def test_a_predicate_may_not_accept_an_entity_type_finer_than_its_source():
    """The registration-time half of the rule, and the one that would have
    caught `alc-predictive-wales` at registration rather than at build: a
    predicate whose source is AREA grain may not declare that it applies to
    `building`, because that is a standing permission to emit property-grain
    claims from an area-grain source."""
    errors = validate_predicate_def(
        PredicateDef("alc_grade_but_per_property", "text", "single",
                     ("area", "building"), "d", "c",
                     finest_grain=Grain.AREA))
    assert any("finest_grain" in e and "building" in e for e in errors), errors


def test_a_property_grain_predicate_may_apply_to_area_because_coarser_is_legal():
    assert validate_predicate_def(
        PredicateDef("rolls_up", "text", "single", ("building", "area"),
                     "d", "c", finest_grain=Grain.PROPERTY)) == []


# --------------------------------------------------------------------------
# 8.2 interim — the 143 already-registered predicates (task 8.6's surface)
# --------------------------------------------------------------------------

def test_the_interim_list_is_exactly_the_predicates_carrying_undeclared():
    """The grandfather list and the registry cannot drift: every name on the
    list is undeclared in the registry, and every undeclared predicate is on
    the list. Task 8.6 removes a name and declares a grain in the SAME commit,
    or this fails."""
    undeclared = {n for n, p in PREDICATE_REGISTRY.items()
                  if p.finest_grain is Grain.UNDECLARED}
    assert set(INTERIM_UNDECLARED) == undeclared


def test_the_interim_list_is_frozen_by_digest_so_nothing_new_can_be_grandfathered():
    """A new predicate cannot be waved through by adding its name here. The
    list is pinned by content; 8.6 shrinks it and updates the pin, and the
    only direction the pin may ever move is smaller."""
    from craidd.schema.predicates import INTERIM_UNDECLARED_DIGEST, _interim_digest
    assert _interim_digest(INTERIM_UNDECLARED) == INTERIM_UNDECLARED_DIGEST
    assert len(INTERIM_UNDECLARED) == 143


def test_a_grandfathered_predicate_is_not_refused_but_is_not_silent_either():
    """The seed is not refused at import — but the interim is visible, not
    implied. `validate_predicate_def` accepts it; `undeclared_predicates()`
    reports it by name so nobody can claim the rule is fully enforced."""
    from craidd.schema.predicates import undeclared_predicates
    some_existing = INTERIM_UNDECLARED[0]
    assert validate_predicate_def(PREDICATE_REGISTRY[some_existing]) == []
    assert some_existing in undeclared_predicates()
    assert len(undeclared_predicates()) == 143


# --------------------------------------------------------------------------
# 8.3 — a claim FINER than its predicate's grain is refused
#       (proven against the real `alc-predictive-wales` shape)
# --------------------------------------------------------------------------

_ALC_SUBJECT = "area:alc-wales-3f5c9a1b"     # the real minted shape, alc/dissolve.py::_entity_id


def _alc_claim(subject_id: str, predicate: str = "alc_grade") -> dict:
    """A claim in the real emitted shape — awen-source-catalogue
    modules/alc/snapshot.py emits `alc_grade` with the grade VERBATIM in
    value_text and binding=asserted."""
    return {
        "claim_id": f"{subject_id}-alc_grade",
        "subject_id": subject_id,
        "predicate": predicate,
        "value_text": "3b",
        "source_id": "src:datamapwales-wg-predictive-alc2",
        "recorded_by": "awen-source-catalogue",
        "confidence": "high",
        "qualifiers": {"binding": "asserted"},
    }


_ALC_AREA_GRAIN = PredicateDef(
    "alc_grade", "text", "single", ("area",),
    "Predictive ALC grade zone.", "gradd ALC",
    finest_grain=Grain.AREA)

# The predicate as it WOULD have to be declared for a per-UPRN ALC claim — the
# thing the rule refuses at registration. Kept as a fixture so 8.3 can be shown
# refusing the CLAIM even where a mis-declared predicate got through.
_ALC_IF_IT_CLAIMED_PROPERTY = PredicateDef(
    "alc_grade", "text", "single", ("area", "building"),
    "Predictive ALC grade zone.", "gradd ALC",
    finest_grain=Grain.AREA)


def test_the_real_alc_claim_at_its_own_grain_is_accepted():
    """The layer that motivated the rule keeps working. If this fails the
    guard is wrong, not the layer."""
    assert validate_claim(_alc_claim(_ALC_SUBJECT),
                          subject_entity_type="area",
                          predicate_registry={"alc_grade": _ALC_AREA_GRAIN}) == []


def test_a_property_grain_alc_claim_is_refused_by_the_GRAIN_rule():
    """8.3, against the real shape. The predicate here lists `building` in
    applies_to precisely so that applies_to CANNOT be what refuses it — the
    refusal must come from the grain rule and must name both grains."""
    errors = validate_claim(
        _alc_claim("1000000123456"),           # a bare UPRN — property grain
        subject_entity_type="building",
        predicate_registry={"alc_grade": _ALC_IF_IT_CLAIMED_PROPERTY})
    assert errors, "a property-grain claim on an area-grain predicate must be refused"
    grain_errors = [e for e in errors if "finest_grain" in e]
    assert grain_errors, f"refused, but not by the grain rule: {errors}"
    assert "alc_grade" in grain_errors[0]
    assert "property" in grain_errors[0] and "area" in grain_errors[0]
    # and it is the ONLY thing wrong with this claim — applies_to passes.
    assert len(errors) == 1, errors


# --------------------------------------------------------------------------
# 8.4 — COARSER stays legal. The blast-radius half.
# --------------------------------------------------------------------------

def test_an_aggregation_from_property_to_area_registers_untouched():
    """A property-grain source rolled up to an area is a normal, wanted
    derivation. A guard that refused this would break every roll-up in the
    estate and the next person's fix would be to delete the guard."""
    epc_per_property = PredicateDef(
        "epc_certificate_count", "int", "single", ("building", "area"),
        "EPC certificates.", "tystysgrifau EPC", finest_grain=Grain.PROPERTY)
    rolled_up = {
        "claim_id": "W06000004-epc_certificate_count",
        "subject_id": "W06000004",              # a GSS code — area grain
        "predicate": "epc_certificate_count",
        "value_int": 41207,
        "source_id": "src:epc-domestic",
        "recorded_by": "awen-source-catalogue",
        "confidence": "high",
        "qualifiers": {"binding": "derived"},
    }
    assert validate_claim(rolled_up, subject_entity_type="area",
                          predicate_registry={
                              "epc_certificate_count": epc_per_property}) == []


def test_a_claim_at_exactly_the_declared_grain_is_accepted():
    pred = PredicateDef("flood_coverage_share", "real", "single", ("area",),
                        "d", "c", finest_grain=Grain.AREA)
    claim = {
        "claim_id": "W06000004-flood_coverage_share",
        "subject_id": "W06000004", "predicate": "flood_coverage_share",
        "value_real": 0.0731, "source_id": "src:nrw-flood-map",
        "recorded_by": "awen-source-catalogue", "confidence": "high",
        "qualifiers": {"binding": "derived"},
    }
    assert validate_claim(claim, subject_entity_type="area",
                          predicate_registry={
                              "flood_coverage_share": pred}) == []


def test_a_claim_on_a_non_spatial_subject_is_not_grain_checked():
    """A citation has no spatial grain. Refusing it would be nonsense, and
    `source` is enumerated as non-spatial rather than falling through a
    default."""
    pred = PredicateDef("source_url", "text", "single", ("source",),
                        "d", "c", finest_grain=Grain.NOT_SPATIAL)
    claim = {
        "claim_id": "src:x-source_url", "subject_id": "source:x",
        "predicate": "source_url", "value_text": "https://example.gov.uk",
        "source_id": "src:x", "recorded_by": "code", "confidence": "high",
        "qualifiers": {"binding": "asserted"},
    }
    assert validate_claim(claim, subject_entity_type="source",
                          predicate_registry={"source_url": pred}) == []


def test_the_143_grandfathered_predicates_do_not_refuse_their_own_claims():
    """THE BLAST RADIUS, MEASURED RATHER THAN ASSERTED. Every claim in the
    estate cites one of the 143, all of which are UNDECLARED until 8.6. If an
    undeclared predicate refused claims, every snapshot build on the estate
    would hard-stop — `validation_gate.grammar_violations` runs `validate_claim`
    over EVERY record materialised into EVERY snapshot. The rule cannot be
    enforced for a predicate whose grain nobody has yet evidenced; it is
    reported as unchecked instead, and 8.6 is what turns the check on."""
    claim = {
        "claim_id": "1000000123456-uprn", "subject_id": "1000000123456",
        "predicate": "uprn", "value_text": "1000000123456",
        "source_id": "src:os-open-uprn", "recorded_by": "awen-source-catalogue",
        "confidence": "high", "qualifiers": {"binding": "asserted"},
    }
    assert PREDICATE_REGISTRY["uprn"].finest_grain is Grain.UNDECLARED
    assert validate_claim(claim, subject_entity_type="building") == []


# --------------------------------------------------------------------------
# 8.5 — THE REGISTRAR ASKS. Proven over the real registration paths, not over
#       validate_predicate_def()/validate_claim() called directly.
# --------------------------------------------------------------------------

def test_registration_path_1_craidd_init_refuses_a_grain_less_seed(monkeypatch, tmp_path):
    """PATH 1 OF 2 FOR PREDICATES: `craidd-init` is the ONLY code path that
    writes rows into the `predicate` table (cli/craidd_init.py::_INSERT_PREDICATE).
    It is driven here through `main()` with a real argv and a real temp data
    dir — not by calling the validator — so a future caller that skipped the
    validator would fail this test."""
    from cli import craidd_init
    from craidd.schema import predicates as P

    grainless = PredicateDef("sneaked_in", "text", "single", ("building",),
                             "d", "c")
    # Patch ONLY the name craidd-init reads. If the CLI validated some other
    # module's tuple — as it did until 12/09/2026 — this test would see the
    # grain-less predicate reach the INSERT, which is exactly the bypass 8.5
    # is about.
    monkeypatch.setattr(craidd_init, "SEED_PREDICATES",
                        P.SEED_PREDICATES + (grainless,))

    rc = craidd_init.main(["--data-dir", str(tmp_path), "--json"])
    assert rc != 0, "craidd-init must refuse to bootstrap a grain-less seed set"
    assert rc == 2, "refused by the seed validation, not by a database error"
    assert not (tmp_path / "craidd.duckdb").exists(), \
        "craidd-init must not have written a predicate row"


def test_registration_path_2_the_import_time_invariant_holds_the_same_line():
    """PATH 2 OF 2 FOR PREDICATES: predicates.py asserts its own invariants at
    import. The interim list is one of them, so a predicate added to the module
    without a grain and without being on the frozen list cannot reach any
    caller at all."""
    from craidd.schema import predicates as P
    with pytest.raises(RuntimeError, match="finest_grain"):
        P._assert_grain_declarations(
            P.SEED_PREDICATES + (PredicateDef("late_addition", "text", "single",
                                              ("building",), "d", "c"),))


def test_registration_path_3_the_build_gate_refuses_a_finer_claim():
    """THE CLAIM PATH THAT REAL BUILDS TAKE. Every snapshot builder on the
    estate reaches the grammar through `validation_gate.grammar_violations`,
    never through `validate_claim` directly — that indirection is deliberate
    (`there is no GrammarGate(...) for a builder to omit`). So the refusal is
    proven THERE."""
    from craidd.validation_gate import grammar_violations
    from craidd.schema import predicates as P

    # Use a real registered predicate declared at area grain for the duration.
    original = P.PREDICATE_REGISTRY["alc_grade"]
    P.PREDICATE_REGISTRY["alc_grade"] = _ALC_IF_IT_CLAIMED_PROPERTY
    try:
        violations, unchecked = grammar_violations(
            "claim", _alc_claim("1000000123456"),
            subject_entity_type="building")
    finally:
        P.PREDICATE_REGISTRY["alc_grade"] = original
    assert any("finest_grain" in v for v in violations), (violations, unchecked)


def test_the_build_gate_reports_grain_unchecked_when_it_cannot_resolve_the_subject():
    """The honest limit, reported rather than quietly passed — the same
    treatment `applies_to` already gets. A search-layer builder usually cannot
    resolve its subject's entity type, and a clean result must say which rules
    it could not decide."""
    from craidd.validation_gate import grammar_violations
    violations, unchecked = grammar_violations(
        "claim", _alc_claim(_ALC_SUBJECT), subject_entity_type=None)
    assert "finest_grain" in unchecked
    assert "applies_to" in unchecked
