"""Every single-descriptor description_cy begins with a capital (card c0900).

Huw's rule, 12/10/2026, in chat to the Mac 5 builder: "when starting a sentence or as a single
descriptor then O should be used". 0.2.33 (#35) and 0.2.34 (#36) applied it to the 'o fewn' values;
this applies it to every other single descriptor. ONLY the first letter changes: no other character,
no Welsh composed. Running sentences, and a value that begins with a code identifier, are left alone
and listed in LEFT with the reason. awen-weave 0.2.35 (PROPOSED, HOLD)."""
from __future__ import annotations

from craidd.schema.predicates import CY_PENDING, PREDICATE_REGISTRY, SEED_PREDICATES

# as they stood at 0.2.34 (#36 head e5e5b60), before the capital
BEFORE = {
    'address': 'cyfeiriad post',
    'geometry': 'geometreg yr adeilad - ôl troed yr adeilad',
    'building_type': 'math o adeilad',
    'floor_area_m2': 'cyfanswm arwynebedd llawr mewnol mewn metrau sgwâr',
    'original_use': 'defnydd(iau) gwreiddiol',
    'current_use': 'defnydd presennol',
    'listed_grade': 'gradd restredig statudol',
    'listed_id': 'cyfeirnod cofrestr Cadw neu adeiladau rhestredig Prydain',
    'conservation_area': 'ardal gadwraeth',
    'name_cy': 'enw Cymraeg',
    'name_en': 'enw Saesneg',
    'historical_note': 'nodyn hanesyddol — testun rhydd',
    'architectural_description': 'disgrifiad pensaernïol strwythuredig',
    'material_primary': 'prif ddeunydd wal allanol',
    'roof_type': 'math o do — ffurf a deunydd',
    'storeys': 'nifer y lloriau llawn',
    'adjacent_to': "adeilad arall sy'n gyfagos yn gorfforol i hwn",
    'contemporary_with': "adeilad o'r un cyfnod adeiladu",
    'group_value_with': "adeilad sy'n rhannu rheswm rhestru (gwerth grŵp)",
    'location_verification_status': "statws gwirio lleoliad — band sy'n deillio o honiadau byw a haen ddarlledu Lleolydd",
    'tenancy_of': "yr adeilad (neu'r ardal) y mae'r denantiaeth hon yn ei feddiannu",
    'tenant_name': 'enw cyffredin y tenant',
    'tenant_organisation': "enw'r sefydliad yn ffurfiol, lle bo'n berthnasol",
    'tenancy_type': 'math o denantiaeth',
    'tenant_business_type': "natur busnes y tenant, e.e. 'siop bapurau newydd a llyfrau'",
    'period_start': 'dechrau cynharaf credadwy y denantiaeth',
    'event_type': 'math o ddigwyddiad',
    'event_start': "dyddiad dechrau'r digwyddiad",
    'affects_entity': "endid y mae'r digwyddiad hwn yn ei effeithio",
    'funder': "arianwr, lle bo'r arianwr ei hun yn endid sydd wedi'i gofnodi",
    'funder_text': "arianwr, lle'i nodir fel llinyn yn unig",
    'scope_description': 'disgrifiad y digwyddiad - beth wnaeth y digwyddiad',
    'consent_reference': 'cyfeirnod cydsynio adeilad rhestredig, cynllunio, neu ddynodi',
    'question_text': 'y cwestiwn ymchwil ei hun',
    'relates_to_entity': "pwnc y mae'r cwestiwn yn ei gylch",
    'suggested_sources': 'ble i edrych — testun rhydd',
    'priority': 'blaenoriaeth cwestiwn',
    'status': 'statws cwestiwn',
    'title_cy': "teitl Cymraeg, lle bo'n berthnasol",
    'title_en': 'teitl Saesneg',
    'citation': 'mynegai cyfeirio',
    'organisation': 'sefydliad awduriaethol neu storfa',
    'licence': 'trwydded — OGL, CC-BY-SA, mewnol, ac yn y blaen',
    'accessed_at': 'dyddiad agor mwyaf diweddar',
    'material_tradition': "traddodiad deunyddiau adeiladu'r dref",
    'street_pattern': 'disgrifiad naratif o batrwm strydoedd y dref',
    'notable_event': 'digwyddiad nodedig yn hanes y dref',
    'conservation_authority': 'awdurdod cynllunio lleol ar gyfer cydsynio cadwraeth',
    'unitary_authority': 'cyngor unedol',
    'listed_building_count': 'nifer yr adeiladau rhestredig yn y dref',
    'parish': "plwyf eglwysig, lle bo'n berthnasol",
    'near_scheduled_monument': 'yn agos at heneb gofrestredig (o fewn dalgylch ei gosodiad)',
    'heritage_class': 'dosbarth treftadaeth',
    'heritage_site_type': 'math o safle treftadaeth',
    'heritage_period': 'cyfnod hanesyddol',
    'designated_area_ha': 'arwynebedd dynodedig (hectarau)',
    'setting_scale': 'graddfa gosodiad',
    'near_strategic_road_network': 'yn agos at rwydwaith ffyrdd strategol',
}

# left exactly as they are, with the reason (listed in the PR as unsure)
LEFT = {
    'build_year': "blwyddyn adeiladu — defnyddiwch dim ond pan fo'r dyddiad yn fanwl gywir",
    'period_end': 'diwedd cynharaf credadwy y denantiaeth; gadael yn wag ar gyfer tenantiaeth cyfredol',
    'event_end': 'dyddiad diwedd y digwyddiad; gadael yn wag ar gyfer digwyddiad cyfredol',
    'alc_grade': "gradd rhagfynegol Dosbarthiad Tir Amaethyddol (ALC Map 2) ar gyfer parth ansawdd tir — label y radd yn cael ei gadw'n union (gan gynnwys y rhaniad 3a/3b); grid rhagfynegol 50m yn ôl meini prawf MAFF 1988, nid arolwg safle. [Cymraeg i'w gadarnhau gan diwtor]",
    'answered_by_claim': 'claim_id yr honiad a ddatrysodd y cwestiwn',
}


def test_each_single_descriptor_gains_a_capital_first_letter_and_nothing_else():
    for name, old in BEFORE.items():
        assert PREDICATE_REGISTRY[name].description_cy == old[0].upper() + old[1:], name


def test_the_identifier_is_untouched_and_the_sentences_moved_to_c0906():
    # c0906 [sig:a99523cf]: the four running sentences take a capital (test_cy_running_sentence_capitals);
    # answered_by_claim, beginning with the code identifier claim_id, stays as it is
    assert PREDICATE_REGISTRY["answered_by_claim"].description_cy == LEFT["answered_by_claim"]


def test_every_written_description_cy_now_begins_with_a_capital_unless_left():
    lower = [p.name for p in SEED_PREDICATES if isinstance(p.description_cy, str)
             and p.description_cy != CY_PENDING and p.description_cy[:1].islower()]
    assert sorted(lower) == ["answered_by_claim"]       # c0906 capitalised the other four
