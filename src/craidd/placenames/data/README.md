# Standardised Welsh place-names — data snapshot

This directory holds the captured snapshot of the Welsh Language
Commissioner's **List of Standardised Welsh Place-names** that the
`craidd.placenames` authority loads at import time.

## Current snapshot

| Filename | Vintage | Rows | Source |
|---|---|---:|---|
| `standardised-welsh-place-names-2026-05-22.csv` | 2026-05-22 | 3,615 names (3,616 lines incl. header) | <https://www.welshlanguagecommissioner.wales/standard-welsh-place-names> |

## Licence

**Open Government Licence v3.0** — per the publisher's "Standard Welsh
Place-names" page assertion: *"This information is licenced under the
Open Government Licence 3.0 except where otherwise stated."*

Required attribution when reproducing names downstream:

> Source: Welsh Language Commissioner / Comisiynydd y Gymraeg — List of Standardised Welsh Place-names (Open Government Licence v3).

## Columns

Welsh-first (matches the source's column order):

| column | meaning |
|---|---|
| Ffurf safonol | standard Welsh form (welsh_name) |
| Ffurf safonol arall | alternative standard Welsh form, where one exists |
| Ffurf Saesneg | English / anglicised form |
| Cyfeirnod grid | OS National Grid reference, alphanumeric (e.g. `SH7217`) |
| Math (Cymraeg) | place type in Welsh (e.g. `Anheddiad` = settlement) |
| Math (Saesneg) | place type in English |
| Awdurdod lleol (Cymraeg) | local authority in Welsh |
| Awdurdod lleol (Saesneg) | local authority in English |

## Refresh policy

The Place-names Standardisation Panel publishes rolling updates; no
fixed cadence. To refresh:

1. Download the latest CSV from the publisher page (download button
   triggers a Microsoft Azure Logic-App endpoint that returns CSV).
2. Save as `standardised-welsh-place-names-YYYY-MM-DD.csv` alongside
   the existing snapshot.
3. Update `CSV_FILENAME` + `CSV_VINTAGE` in `craidd.placenames.authority`.
4. Optionally retain the prior snapshot for diffing; the authority
   loads only the current `CSV_FILENAME`.
5. Smoke-test: spot-check `Dolgellau`, `Bermo / Barmouth`, `Tywyn`,
   `Aberdyfi` resolve cleanly via the lookup API.

## Out-of-scope downstream behaviours

This authority is **suggest/validate** only. Auto-rewriting Craidd
`name_cy` fields from this data is not appropriate — the curator /
tutor retains authority over what is claimed for a specific entity.
The authority's role is to surface the standardised form for human
review, not to overwrite attested names.

## Welsh-first attribution detail

The CSV's UTF-8 BOM is preserved in the file (`encoding="utf-8-sig"`
on read) so the source's first column reads `Ffurf safonol` cleanly
rather than `﻿Ffurf safonol`. Welsh-language fidelity at the
byte level: diacritics, hyphens, and apostrophes preserved verbatim
in both columns. The lookup keys lowercase + collapse whitespace but
do NOT strip diacritics or hyphens — those carry meaning in Welsh
and removing them would conflate distinct names.
