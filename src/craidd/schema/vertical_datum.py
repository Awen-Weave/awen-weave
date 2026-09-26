"""
The publisher-unit -> `vertical_datum` table, and the per-layer datum count.

Constitution 0.1.8 (Llys 26/09/2026 [sig:c8426dc4], Option C with the 424 pass's amendments)
makes `vertical_datum` a CLOSED qualifier REQUIRED on `tide_level` and `water_level`. One of its
four values is `unstated`, and a required field with an honest "don't know" is only as good as the
producer's discipline in reaching for it. So a producer does not TYPE the datum: it passes the
publisher's own unit string through `datum_for_unit`, and the table below decides (424 pass, N3).

THE TABLE IS TOTAL OVER WHAT HAS BEEN MEASURED AND REFUSES THE REST. The Environment Agency's
flood-monitoring reference defines each unit (read 26/09/2026): mAOD "metres relative to the
Ordnance Survey datum", mASD "metres relative to the local stage datum", and bare `m` "metres with
an unspecified datum"; one tidal measure is served in mACD (metres above Chart Datum), and 243
stage measures carry `---`. `unstated` therefore arises ONLY where the publisher itself declares no
datum. An unmapped unit raises `UnknownUnit` — it is a gap to report and a table row to add by a
reviewed change, never a reason to reach for `unstated` or the nearest datum. Matching is exact:
`MAOD` or ` mAOD` is not silently normalised, because a publisher that changed its spelling has
changed something worth a human look.

`mBDAT` (97 EA groundwater measures) is deliberately absent: it is a sign convention below a
datum, not a datum, and `groundwater_level` does not require `vertical_datum`.
"""
from __future__ import annotations

import json
from typing import Iterable, Mapping, Optional

from craidd.schema.qualifiers import VERTICAL_DATUMS

#: The predicates whose claims must carry `vertical_datum` (their `required_qualifiers`).
DATUM_REQUIRED_PREDICATES: frozenset[str] = frozenset({"tide_level", "water_level"})

#: Publisher unit string -> vertical_datum value. Exact match only.
UNIT_TO_DATUM: Mapping[str, str] = {
    "mAOD": "ordnance-datum-newlyn",
    "mASD": "local-stage-datum",
    "mACD": "chart-datum",
    "m": "unstated",
    "---": "unstated",
}

if set(UNIT_TO_DATUM.values()) - VERTICAL_DATUMS:        # pragma: no cover — import-time guard
    raise RuntimeError("UNIT_TO_DATUM maps to a value outside VERTICAL_DATUMS")


class UnknownUnit(ValueError):
    """A publisher unit the table does not map. Report it; do not guess a datum."""


def datum_for_unit(unit: Optional[str]) -> str:
    """The `vertical_datum` a publisher's unit string declares. Raises `UnknownUnit` otherwise."""
    if not isinstance(unit, str) or unit not in UNIT_TO_DATUM:
        raise UnknownUnit(
            f"publisher unit {unit!r} has no vertical_datum mapping; known units: "
            f"{sorted(UNIT_TO_DATUM)}. Add a reviewed row to UNIT_TO_DATUM — never guess."
        )
    return UNIT_TO_DATUM[unit]


def _qualifiers(claim: Mapping) -> Mapping:
    q = claim.get("qualifiers") or claim.get("qualifiers_json") or {}
    if isinstance(q, str):
        q = json.loads(q) if q.strip() else {}
    return q


def datum_counts(claims: Iterable[Mapping]) -> Optional[dict[str, int]]:
    """Per-datum claim counts for one layer, every value present (`unstated` included, at 0).

    Counts claims on a datum-requiring predicate or carrying a `vertical_datum`. Returns None when
    the layer has none, so a layer with nothing to count reports nothing and every existing
    snapshot manifest stays byte-identical.
    """
    counts = {d: 0 for d in sorted(VERTICAL_DATUMS)}
    seen = False
    for claim in claims:
        datum = _qualifiers(claim).get("vertical_datum")
        if claim.get("predicate") in DATUM_REQUIRED_PREDICATES or datum is not None:
            seen = True
            if datum in counts:
                counts[datum] += 1
    return counts if seen else None
