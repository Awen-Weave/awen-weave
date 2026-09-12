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
    PREDICATE_REGISTRY,
    PredicateDef,
    SEED_PREDICATES,
    undeclared_predicates,
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
# 8.6 — THE INTERIM IS GONE: absent is refused for the SEED too
# --------------------------------------------------------------------------
# These three replace the three interim tests that stood here until 2026-09-12
# (dispatch 200). They asserted that the 143 pre-rule predicates were excused,
# that the excuse list was digest-frozen, and that an excused predicate was
# reported rather than silent. Task 8.6 evidenced all 143 and removed the list,
# so what must now be pinned is the OPPOSITE: that nothing is excused.

def test_EVERY_registered_predicate_now_carries_a_declared_grain():
    """Task 8.6's exit, asserted against the real registry rather than a count
    in a comment. Nothing is UNDECLARED and nothing is off the value set."""
    undeclared = sorted(n for n, p in PREDICATE_REGISTRY.items()
                        if p.finest_grain is Grain.UNDECLARED)
    assert undeclared == [], undeclared
    assert len(PREDICATE_REGISTRY) == 143
    off_set = {n: p.finest_grain for n, p in PREDICATE_REGISTRY.items()
               if p.finest_grain not in DECLARED_GRAINS}
    assert off_set == {}, off_set


def test_undeclared_predicates_reports_EMPTY_and_is_kept_as_the_reporting_half():
    """The reporting function survives the interim's deletion deliberately: a
    future regression must be REPORTABLE, not merely raisable. It is empty now
    and an import-time assertion keeps it so."""
    assert undeclared_predicates() == ()


def test_ABSENT_IS_REFUSED_FOR_THE_SEED_TOO_seen_to_fail_on_a_fixture_copy():
    """§2's required proof, and the one the interim used to prevent. Delete one
    predicate's grain from a COPY of the seed and the registry refuses to
    build — before 8.6 this passed silently for any of the 143.

    A COPY, never the real tuple: mutating the module's own seed would leave
    every later test in the session running against a corrupted registry.
    """
    from dataclasses import replace
    from craidd.schema.predicates import _assert_grain_declarations

    victim = SEED_PREDICATES[0]
    assert victim.finest_grain is not Grain.UNDECLARED, "pre-state: it IS declared"
    _assert_grain_declarations(SEED_PREDICATES)          # the real set still passes

    broken = (replace(victim, finest_grain=Grain.UNDECLARED),) + SEED_PREDICATES[1:]
    with pytest.raises(RuntimeError) as e:
        _assert_grain_declarations(broken)
    assert victim.name in str(e.value)
    assert "ABSENT IS NOT A WILDCARD" in str(e.value)

    # and the registration validator refuses it too — both lines, not one
    assert validate_predicate_def(broken[0]) != []
    assert validate_predicate_def(victim) == []


def test_there_is_no_list_a_writer_could_add_a_name_TO():
    """The interim's real hazard was that it was a register: a new predicate
    could be waved through by appending one line. Pinned by ABSENCE, so
    re-introducing an exemption under any name fails here."""
    import craidd.schema.predicates as P
    import craidd.schema.validation as V
    for mod in (P, V):
        leftovers = [n for n in dir(mod) if "INTERIM" in n.upper()]
        assert leftovers == [], (mod.__name__, leftovers)


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


def test_turning_the_check_ON_did_not_start_refusing_the_estates_own_claims():
    """THE BLAST RADIUS, MEASURED RATHER THAN ASSERTED — AND RE-MEASURED AFTER
    8.6 TURNED THE CHECK ON. Every claim in the estate cites one of the 143.
    Until 2026-09-12 they were all UNDECLARED and the rule was reported as
    unchecked; task 8.6 evidenced every one, so from now on this test measures
    the thing that actually matters: that turning the check ON did not start
    refusing the estate's own claims.

    `uprn` is the case with teeth — it is emitted per-property by epc-domestic
    (epc_domestic.py:203) on the UPRN spine, and 8.6 gave it `property`. Its
    own claim is at property grain, which is EQUAL and therefore legal. Had
    8.6 taken the layer's spine as the grain wherever they differed, the five
    gp-locations predicates would have been declared `area` and every one of
    that layer's claims would now be REFUSED — which is why those five were
    resolved by reading the module instead."""
    claim = {
        "claim_id": "1000000123456-uprn", "subject_id": "1000000123456",
        "predicate": "uprn", "value_text": "1000000123456",
        "source_id": "src:os-open-uprn", "recorded_by": "awen-source-catalogue",
        "confidence": "high", "qualifiers": {"binding": "asserted"},
    }
    assert PREDICATE_REGISTRY["uprn"].finest_grain is Grain.PROPERTY
    assert validate_claim(claim, subject_entity_type="building") == []

    # the gp-locations five: property-grain claims on a gazetteer-spine layer
    for name in ("gp_location", "name_en", "operational_status", "ods_code", "list_size"):
        assert PREDICATE_REGISTRY[name].finest_grain is Grain.PROPERTY, name
    gp = {
        "claim_id": "A81001-ods_code", "subject_id": "A81001",
        "predicate": "ods_code", "value_text": "A81001",
        "source_id": "src:nhs-ods", "recorded_by": "awen-source-catalogue",
        "confidence": "high", "qualifiers": {"binding": "asserted"},
    }
    assert validate_claim(gp, subject_entity_type="building") == []


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


# --------------------------------------------------------------------------
# EXIT 7 — THE FLOOD PREDICATES ARE REGISTERED UNDER THE NEW RULE
# --------------------------------------------------------------------------
# Dispatch 200 §4. Both registered flood predicates were already in the seed,
# so exit 7 is met by 8.6 giving them an EVIDENCED grain and by these tests
# showing a finer claim against them is refused. The RoFRS band predicates the
# dispatch asks about are NOT registered — confirmed against PREDICATE_REGISTRY,
# reported rather than registered here, because registering a predicate is its
# own ruled act and §4 does not commission one.
#
# THE DOCTRINE IS WHY THE VALUE IS `area` AND NOT A CONVENIENCE. The 17/08
# grain rulings and flood-grain-doctrine-note-2026-08-17.md record that flood
# zone data is served AT AREA GRAIN ONLY and is explicitly not for "identifying
# whether an individual property will flood". A property-grain flood claim is
# precisely the thing the doctrine forbids, so it must be REFUSED and not
# merely undeclared.

_FLOOD = ("flood_coverage", "properties_at_flood_risk_count")


def test_exit7_the_flood_predicates_carry_an_evidenced_AREA_grain():
    for name in _FLOOD:
        pred = PREDICATE_REGISTRY[name]
        assert pred.finest_grain is Grain.AREA, name
        assert pred.applies_to_types == ("area",), name


def test_exit7_a_PROPERTY_grain_flood_claim_is_REFUSED():
    """The doctrine's own prohibition, enforced rather than documented. A claim
    whose subject is a `building` is property grain — FINER than the area-grain
    source — so it is refused. This is the assertion exit 7 turns on."""
    for name in _FLOOD:
        claim = {
            "claim_id": f"1000000123456-{name}", "subject_id": "1000000123456",
            "predicate": name, "value_real": 0.42,
            "source_id": "src:ea-flood-map", "recorded_by": "awen-source-catalogue",
            "confidence": "high", "qualifiers": {"binding": "derived"},
        }
        violations = validate_claim(claim, subject_entity_type="building")
        assert violations, f"{name}: a property-grain flood claim must NOT pass"
        assert any("grain" in v.lower() for v in violations), (name, violations)


def test_exit7_the_SAME_claim_at_AREA_grain_is_legal():
    """The control. Without it, the refusal above is indistinguishable from the
    predicate being broken in some other way."""
    claim = {
        "claim_id": "W06000004-flood_coverage", "subject_id": "W06000004",
        "predicate": "flood_coverage", "value_real": 0.42,
        "source_id": "src:ea-flood-map", "recorded_by": "awen-source-catalogue",
        "confidence": "high", "qualifiers": {"binding": "derived"},
    }
    assert validate_claim(claim, subject_entity_type="area") == []


def test_exit7_the_RoFRS_band_predicates_are_NOT_registered_reported_not_fixed():
    """§4 asks which predicates these are. Answer, measured: the RoFRS bands are
    not in the registry at all, so they cannot be 'registered under the new
    rule' by this dispatch. Pinned so that whoever registers them later must
    delete this test deliberately — and by then the rule makes a grain
    mandatory, which is the whole point of the ordering."""
    flood_ish = sorted(n for n in PREDICATE_REGISTRY if "flood" in n or "rofrs" in n.lower())
    assert flood_ish == ["flood_coverage", "properties_at_flood_risk_count"], flood_ish
