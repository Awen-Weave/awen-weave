"""The four running-sentence description_cy begin with a capital (card c0906).

Huw's rule, 12/10/2026: "when starting a sentence or as a single descriptor then O should be used";
on c0900's question he ruled [sig:a99523cf] that the four running sentences take a capital and that
answered_by_claim, which begins with the code identifier claim_id, is left unchanged. First letter
only, no other character, no Welsh composed. awen-weave 0.2.36 (PROPOSED, HOLD)."""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES

# as they stood at 0.2.35 (#37), before the capital
BEFORE = {
    'build_year': "blwyddyn adeiladu — defnyddiwch dim ond pan fo'r dyddiad yn fanwl gywir",
    'period_end': 'diwedd cynharaf credadwy y denantiaeth; gadael yn wag ar gyfer tenantiaeth cyfredol',
    'event_end': 'dyddiad diwedd y digwyddiad; gadael yn wag ar gyfer digwyddiad cyfredol',
    'alc_grade': "gradd rhagfynegol Dosbarthiad Tir Amaethyddol (ALC Map 2) ar gyfer parth ansawdd tir — label y radd yn cael ei gadw'n union (gan gynnwys y rhaniad 3a/3b); grid rhagfynegol 50m yn ôl meini prawf MAFF 1988, nid arolwg safle. [Cymraeg i'w gadarnhau gan diwtor]",
}
IDENTIFIER = 'claim_id yr honiad a ddatrysodd y cwestiwn'


def test_each_running_sentence_gains_a_capital_first_letter_and_nothing_else():
    for name, old in BEFORE.items():
        assert PREDICATE_REGISTRY[name].description_cy == old[0].upper() + old[1:], name


def test_answered_by_claim_keeps_its_identifier_unchanged():
    assert PREDICATE_REGISTRY['answered_by_claim'].description_cy == IDENTIFIER


def test_only_answered_by_claim_still_begins_lower_case():
    lower = [p.name for p in SEED_PREDICATES if isinstance(p.description_cy, str)
             and p.description_cy != CY_PENDING and p.description_cy[:1].islower()]
    assert lower == ['answered_by_claim']
