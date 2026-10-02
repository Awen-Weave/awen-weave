# Welsh Government flood allowances: what waits for constitution v0.1.10, and what stays blocked

**Status:** NOTE accompanying a grammar-addition payload (awen-weave 0.2.27, not yet merged, tagged or published). Nothing here mints or vendors anything in the constitution.

**Authority.** Huw as Llys accepted every recommendation in section 6 of `SharedData/PROPOSAL-climate-allowances-grammar-2026-10-02-r2.md` on 02/10/2026 [sig:dc82671f]. That answers Climate's grammar gap [sig:7ed42030] (north-wales-climate-instance@300eea1).

**Shipped in awen-weave 0.2.27**, the minor after constitution v0.1.9's pair (0.2.26): `sea_level_rise_allowance_m`, `peak_river_flow_allowance_pct` and `rainfall_intensity_allowance_pct` (`_CLIMATE_ALLOWANCES` in `src/craidd/schema/predicates.py`), plus a `FALSE_FRIENDS` pair.
- **No constitution change is needed for them.** Predicates are registry-tier.
- **They are unemittable for Climate until each `description_cy` is attested.** This is the 31/08 Welsh-gap ruling, and Climate's own requirement NWC-WLM-001.

## 1. Waits for constitution v0.1.10, not v0.1.9

These are new `SCH-CLAIM-001` qualifier keys, so they are Tier-1:
- the 0.1.8 qualifier set is closed by `additionalProperties: false`, and porth refuses any unknown key;
- each key also needs adding to `QUALIFIER_KEYS` (`src/craidd/schema/qualifiers.py`) in the paired awen-weave minor;
- the release needs the lockstep re-vendor of porth and the offline gate.

v0.1.9 is phase 4's `source_kind` release, and its release test pins 24 claim keys, so none of these ride it.

1. **The allowance-level key, in the source's own words.** An open-form, verbatim label such as `"70th percentile"`, `"95th percentile"`, `"Central"`, `"Upper"` or `"H++"`.
   - **It is not a number.** Tables 1 and 2 never give one, and turning "Central" or "Upper" into a percentile would be the instance's guess.
   - **It is not `confidence_interval`,** which at 0.1.6 means a spread.
   - **Until then,** the level rides verbatim in `semantics_caveat`.
2. **Need 11's three provenance keys** (`north-wales-climate-instance` `NEEDS-DRAFT.md` §11):
   - the model or ensemble that produced the figure;
   - where in the source it sits (DOI plus table, figure or page);
   - whether it is a projection or a storyline.

   **Until then,** the locator is `evidence_uri` with a `#page=` fragment, plus a `semantics_caveat` that carries a real limit on meaning. That is valid at 0.1.8 today.
3. **Need 12's warming-level key, if taken.** Offered, not pressed.

## 2. Stays blocked

- **River basin districts (Dee, West Wales, Severn):** they need a ruling on a river-basin key **and** an awen-registry read-path change. Today `claims_store._GSS_RE` is `^[EWSNLM]\d{8}$`, and `detect_grain` returns nothing for any other id, so the read path answers 400.
- **The Wales-wide rainfall figure:** it waits because `W92000004` has no gazetteer row. The spine stops at councils, so it fails the box-side join-integrity check until the nation level is added or `W92000004` is ruled an admitted spine key.
