"""
src/craidd/readers/dolgellau.py — the Dolgellau Town Dataset gazetteer reader.

The reference reader for S1's first target (brief §6): materialise Dolgellau's
place-anchor(s) from the governed Town Dataset (`/srv/town-dataset/craidd.duckdb`
on craidd), plus the federated name_* claims and the one gazetteer stamp, into a
`SnapshotRecords` the engine-agnostic `SnapshotBuilder` then validates and writes.

An instance keeps its OWN reader (which entities, which columns, the geolocation
method); only the shared record shape lives in the framework (gazetteer.py). So
this module is deliberately Dolgellau-specific — Y Bala gets its own reader when
its dataset exists — while everything it produces is a core SCH-* record.

Two layers, so the build is testable off-craidd:
  - `build_gazetteer(buildings, name_claims, ...)` is PURE — it turns already-read
    rows into records. Unit tests and the committed sample feed it fixture rows.
  - `read_from_duckdb(con)` runs the actual queries against the live store on
    craidd. `resolve_source_ran_at(root)` reads the source's OWN recorded run
    state (its git HEAD commit time) — verify-not-recall, never a wall clock.

county_gss is the one safe constant: every Dolgellau UPRN sits in Gwynedd
(W06000002). ward/community/lsoa stay null until Lleolydd boundary coverage
resolves them (the place-anchor schema is null-tolerant).
"""
from __future__ import annotations

import subprocess
from typing import Optional

from ..federation import SourceOfRecord
from ..gazetteer import federated_name_claim, gazetteer_stamp, place_anchor
from ..snapshot import SnapshotRecords

GWYNEDD_COUNTY_GSS = "W06000002"

# Preference order for choosing a single display label per language from the
# several name claims a building may carry (each with its own name_type).
_LABEL_PREFERENCE = ("current_local", "vernacular", "listed_register", "historic")


def _pick_label(name_claims: list, subject_id: str, predicate: str) -> Optional[str]:
    """Choose one display label for a subject+language by name_type preference."""
    candidates = [
        c for c in name_claims
        if c["subject_id"] == subject_id and c["predicate"] == predicate
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda c: _LABEL_PREFERENCE.index(c["name_type"])
        if c.get("name_type") in _LABEL_PREFERENCE else len(_LABEL_PREFERENCE)
    )
    return candidates[0]["value"]


def build_gazetteer(
    buildings: list,
    name_claims: list,
    *,
    source: SourceOfRecord,
    consumer_instance: str,
    recorded_by: str,
    craidd_node: Optional[str] = None,
    craidd_source: Optional[str] = None,
    grade: str = "B",
    county_gss: str = GWYNEDD_COUNTY_GSS,
    federated_utc: Optional[str] = None,
) -> SnapshotRecords:
    """Turn read building + name-claim rows into a validated-shape record set.

    `buildings` items: {subject_id, uprn(int|None), lat(float|None), lng(float|None)}.
    `name_claims` items: {subject_id, predicate('name_cy'|'name_en'), value,
        source_id, name_type, dialect(optional), confidence(optional)}.

    Pure: no I/O, no wall-clock except the caller-supplied federated_utc. Emits a
    place-anchor per building that carries at least one of uprn / geometry /
    label (skips a wholly-empty row), a federated claim per name row, and one
    gazetteer stamp over the whole read."""
    if source.ran_at_utc is None or not str(source.ran_at_utc).strip():
        # verify-not-recall: refuse to build a gazetteer with no source run-UTC.
        raise ValueError(
            "Dolgellau gazetteer read has no source ran_at_utc — read it from "
            "the source's own recorded state (resolve_source_ran_at); do not "
            "manufacture one"
        )

    anchors: list = []
    for b in buildings:
        uprn = b.get("uprn")
        lat, lng = b.get("lat"), b.get("lng")
        label_cy = _pick_label(name_claims, b["subject_id"], "name_cy")
        label_en = _pick_label(name_claims, b["subject_id"], "name_en")
        if uprn is None and lat is None and lng is None and not (label_cy or label_en):
            continue  # nothing joinable — don't emit a hollow anchor
        anchors.append(place_anchor(
            uprn=str(uprn) if uprn is not None else None,
            county_gss=county_gss,
            lat=lat, lng=lng,
            label_cy=label_cy, label_en=label_en,
        ))

    claims = [
        federated_name_claim(
            subject_id=c["subject_id"], predicate=c["predicate"], value=c["value"],
            source_id=c["source_id"], recorded_by=recorded_by, source=source,
            name_type=c["name_type"], confidence=c.get("confidence", "high"),
            dialect=c.get("dialect"),
        )
        for c in name_claims
    ]

    stamp = gazetteer_stamp(
        source=source, consumer_instance=consumer_instance,
        craidd_node=craidd_node, craidd_source=craidd_source, grade=grade,
        counts={"place_anchors": len(anchors), "claims": len(claims)},
        federated_utc=federated_utc,
        aoi="dolgellau", crs="EPSG:4326",
    )

    return SnapshotRecords(
        place_anchors=anchors, claims=claims, stamps=[stamp],
        source_ran_at={source.instance: source.ran_at_utc},
    )


def read_from_duckdb(con) -> tuple:
    """Read building + name-claim rows from a Town Dataset craidd.duckdb.

    Runs on craidd where the store lives. `con` is an open (read-only) duckdb
    connection. Returns (buildings, name_claims) in the shape build_gazetteer
    expects. Geometry is read from the `geometry` claim as lat/lng."""
    buildings = []
    rows = con.execute(
        "SELECT entity_id, uprn FROM entity WHERE entity_type = 'building' "
        "ORDER BY entity_id"
    ).fetchall()
    for entity_id, uprn in rows:
        geo = con.execute(
            "SELECT ST_Y(value_geom), ST_X(value_geom) FROM current_claim "
            "WHERE subject_id = ? AND predicate = 'geometry' "
            "AND value_geom IS NOT NULL LIMIT 1",
            [entity_id],
        ).fetchone()
        lat, lng = (geo[0], geo[1]) if geo else (None, None)
        buildings.append({
            "subject_id": entity_id,
            "uprn": int(uprn) if uprn is not None else None,
            "lat": lat, "lng": lng,
        })

    name_claims = []
    for entity_id, predicate, value, source_id, conf, q in con.execute(
        "SELECT subject_id, predicate, value_text, source_id, confidence, "
        "qualifiers_json FROM current_claim "
        "WHERE predicate IN ('name_cy', 'name_en') AND value_text IS NOT NULL "
        "ORDER BY subject_id, predicate, value_text"
    ).fetchall():
        import json
        quals = json.loads(q) if q else {}
        name_claims.append({
            "subject_id": entity_id, "predicate": predicate, "value": value,
            "source_id": source_id, "confidence": conf or "high",
            "name_type": quals.get("name_type", "current_local"),
            "dialect": quals.get("dialect"),
        })
    return buildings, name_claims


def resolve_source_ran_at(root: str) -> str:
    """The source's OWN recorded run state: the town-dataset git HEAD commit
    time (ISO-8601). Verify-not-recall — a real recorded fact about the source
    checkout, never a manufactured build-time clock. Fail-loud if `root` is not
    a git working tree (then the caller must pass an explicit --source-ran-at
    from a source manifest)."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "log", "-1", "--format=%cI"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ValueError(
            f"cannot read source ran_at_utc from {root!r} git HEAD ({exc}); "
            f"pass --source-ran-at from the source's run manifest instead"
        ) from exc
    stamp = out.stdout.strip()
    if not stamp:
        raise ValueError(f"empty git HEAD time for {root!r}")
    return stamp
