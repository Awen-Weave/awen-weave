"""
UPRN status-band classifier — v1 (point-proximity).

Per design/lleolydd.md §4, every UPRN gets one of these band labels.
The semantics for v1 are point-proximity rather than point-in-polygon,
because OS Open TOID's 2026-04 release dropped the GEOMETRY column;
polygon data has moved to OS NGD (Phase 1.x work). When polygons
return via NGD integration, bands.py v1.x will restore the original
point-in-polygon semantics — see classify_bands_polygon docstring
below for the reference query that will go back in. This module is
shaped so that switch is small.

v1 bands (point-proximity, default 15m threshold):
  verified         a curator has placed/confirmed this UPRN against a
                   TOID (a Craidd `verified_building_toid` claim). NOT
                   computed in Phase 1 — Phase 2 viewer queries Craidd
                   and upgrades in-memory; Phase 3 writes corrections.
  auto-snapped     UPRN within SNAP_THRESHOLD_M of exactly one TOID
                   point AND OS Linked Identifiers agrees with that
                   TOID.
  unsnapped        UPRN has no TOID point within SNAP_THRESHOLD_M.
                   Rural-driveway case — the UPRN coordinate is on the
                   road junction, the building is 200m down the track.
  contested-prox   UPRN has multiple TOID points within SNAP_THRESHOLD_M.
                   Dense terrace / multi-building UPRN.
  contested-lids   UPRN has exactly one TOID point within threshold,
                   but LIDS disagrees with that TOID — genuine conflict
                   between the spatial and authority signals.
  non-postal       UPRN has no LIDS row at all (OS-allocated non-postal
                   feature: substation, post box, defibrillator).

Phase 1 sets every row's snap_band to one of the bottom five (`verified`
is a Phase 2 viewer-time computation, never appears in the cache).

The classifier runs as a single SQL pass once UPRN, TOID and LIDS
data are loaded. ST_DWithin uses DuckDB spatial's automatic indexing
on point_geom; for ~50–100k Gwynedd UPRNs against a similar count of
TOID points the classifier completes in a few seconds.

Threshold rationale (SNAP_THRESHOLD_M = 15 m):
  - Typical building footprint 10–30 m across; UPRN that sits inside
    a building is usually <15 m from the TOID centroid.
  - Dense town terraces may have adjacent buildings <5 m apart — a
    too-large threshold treats adjacent buildings as contested.
  - 15 m balances false-positives (over-snap) vs false-negatives
    (under-snap) for typical Welsh-town housing density. Tune for
    pilots that surface obviously-wrong band labels.

This is a TRIAGE shape, not a TRUTH shape. The walk-of-the-streets
curator workflow in Lleolydd Phase 3 is the truth-source; bands here
exist to direct curator attention.
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb


# Default snap threshold in metres (BNG units). Override per-call via
# classify_bands(snap_threshold_m=N).
SNAP_THRESHOLD_M: float = 15.0


@dataclass(frozen=True)
class BandStats:
    """Per-band UPRN counts produced by classify_bands(). Sum to
    total_uprns. Reported in completion brief and surfaced via
    `lleolydd-cache snapshot show`.

    `contested_prox` and `contested_lids` are v1's two contested
    variants — kept separate in the manifest because the
    distribution between them is diagnostically meaningful. v1.x
    (polygon-based) will collapse them back into one `contested`
    band, at which point this dataclass's shape will revisit.
    """
    auto_snapped: int
    unsnapped: int
    contested_prox: int
    contested_lids: int
    non_postal: int

    @property
    def total(self) -> int:
        return (
            self.auto_snapped
            + self.unsnapped
            + self.contested_prox
            + self.contested_lids
            + self.non_postal
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "auto-snapped": self.auto_snapped,
            "unsnapped": self.unsnapped,
            "contested-prox": self.contested_prox,
            "contested-lids": self.contested_lids,
            "non-postal": self.non_postal,
            "total": self.total,
        }


def classify_bands(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
    snap_threshold_m: float = SNAP_THRESHOLD_M,
) -> BandStats:
    """Populate uprn.snapped_toid + uprn.snap_band for every row in the
    cache. Returns per-band counts.

    Assumes the cache schema is populated by build.py's source phase:
      - uprn.point_geom is the UPRN coordinate (BNG).
      - toid.point_geom is the TOID representative point (BNG).
      - linked_id has the BLPU-UPRN-TopographicArea-TOID links.

    Idempotent: re-runs overwrite the existing band assignments cleanly.

    snap_threshold_m: maximum distance (metres, BNG) between UPRN and
    TOID point for the UPRN to be considered "near" the TOID. See
    module-level rationale; default 15 m.

    Algorithm:
      1. Proximity: for each UPRN, count TOID points within
         snap_threshold_m AND identify the nearest.
      2. LIDS: collapse linked_id to one expected TOID per UPRN.
      3. Combine into one of five bands per the table below.

    Decision matrix:
      LIDS absent (any spatial state)        → non-postal
      LIDS present, 0 within threshold       → unsnapped
      LIDS present, ≥2 within threshold      → contested-prox
      LIDS present, 1 within, LIDS agrees    → auto-snapped
      LIDS present, 1 within, LIDS disagrees → contested-lids
    """
    # --- Step 1: proximity join. UPRN points within snap_threshold_m
    # of any TOID point. ST_DWithin lets DuckDB pick a spatial index
    # automatically if one exists on toid.point_geom (an RTREE index
    # is the v1.x improvement to add when load shapes settle).
    # COUNT(t.toid) NOT COUNT(*) — see the LEFT JOIN gotcha note from
    # PR #14's commit message.
    # MIN_BY(<x>, <distance>) returns the toid with the smallest
    # distance — i.e. the nearest TOID for the 1-within-threshold case.
    conn.execute("DROP TABLE IF EXISTS _uprn_proximity")
    conn.execute(
        """
        CREATE TEMP TABLE _uprn_proximity AS
        SELECT
            u.uprn,
            COUNT(t.toid) AS toid_count_within_threshold,
            MIN_BY(t.toid, ST_Distance(u.point_geom, t.point_geom))
                AS nearest_toid,
            MIN(ST_Distance(u.point_geom, t.point_geom))
                AS nearest_distance_m
        FROM uprn u
        LEFT JOIN toid t
          ON ST_DWithin(u.point_geom, t.point_geom, ?)
        GROUP BY u.uprn
        """,
        [snap_threshold_m],
    )

    # --- Step 2: collapse linked_id to one expected TOID per UPRN.
    # If a UPRN has multiple LIDS rows (multi-occupancy unit, etc.),
    # ANY_VALUE picks one arbitrarily — v1 keeps the simplest model.
    conn.execute("DROP TABLE IF EXISTS _uprn_lids")
    conn.execute(
        """
        CREATE TEMP TABLE _uprn_lids AS
        SELECT
            uprn,
            COUNT(*) AS lids_row_count,
            ANY_VALUE(toid) AS lids_toid_any
        FROM linked_id
        GROUP BY uprn
        """
    )

    # --- Step 3: classify per UPRN using the v1 decision matrix.
    # Update uprn.snap_band + uprn.snapped_toid in one pass.
    conn.execute(
        """
        UPDATE uprn AS u
        SET
            snapped_toid = CASE
                -- non-postal (no LIDS row) → NULL: the UPRN doesn't
                -- represent a building address, so it has no "snap"
                -- by definition, even if it happens to sit near a
                -- TOID. Preserves the original Phase 1 contract that
                -- snapped_toid is the curator-meaningful answer to
                -- "which building does this UPRN belong to?"
                WHEN l.lids_row_count IS NULL OR l.lids_row_count = 0
                    THEN NULL
                -- Only record snapped_toid when there's a single
                -- proximity match. Otherwise it's ambiguous (multiple
                -- candidates, no candidate, or LIDS-spatial conflict).
                WHEN COALESCE(p.toid_count_within_threshold, 0) = 1
                    THEN p.nearest_toid
                ELSE NULL
            END,
            snap_band = CASE
                WHEN l.lids_row_count IS NULL OR l.lids_row_count = 0
                    THEN 'non-postal'
                WHEN COALESCE(p.toid_count_within_threshold, 0) = 0
                    THEN 'unsnapped'
                WHEN p.toid_count_within_threshold >= 2
                    THEN 'contested-prox'
                WHEN p.toid_count_within_threshold = 1
                     AND l.lids_toid_any = p.nearest_toid
                    THEN 'auto-snapped'
                ELSE 'contested-lids'  -- exactly 1 within, LIDS disagrees
            END,
            snap_confidence = CASE
                WHEN l.lids_row_count IS NULL OR l.lids_row_count = 0
                    THEN 1.0  -- non-postal is a confident classification
                WHEN COALESCE(p.toid_count_within_threshold, 0) = 0
                    THEN 0.0
                WHEN p.toid_count_within_threshold >= 2
                    THEN 0.5
                WHEN p.toid_count_within_threshold = 1
                     AND l.lids_toid_any = p.nearest_toid
                    THEN 1.0
                ELSE 0.5
            END,
            snapshot_id = ?
        FROM _uprn_proximity p
        LEFT JOIN _uprn_lids l
          ON p.uprn = l.uprn
        WHERE u.uprn = p.uprn
        """,
        [snapshot_id],
    )

    conn.execute("DROP TABLE _uprn_proximity")
    conn.execute("DROP TABLE _uprn_lids")

    # --- Step 4: collect per-band counts for the return value.
    rows = conn.execute(
        """
        SELECT snap_band, COUNT(*)
        FROM uprn
        GROUP BY snap_band
        """
    ).fetchall()
    counts = {band: n for band, n in rows}
    return BandStats(
        auto_snapped=counts.get("auto-snapped", 0),
        unsnapped=counts.get("unsnapped", 0),
        contested_prox=counts.get("contested-prox", 0),
        contested_lids=counts.get("contested-lids", 0),
        non_postal=counts.get("non-postal", 0),
    )


# ---------------------------------------------------------------------------
# REFERENCE — Phase 1.x polygon-based classifier (deferred, NGD-dependent)
# ---------------------------------------------------------------------------
#
# When OS NGD integration lands (Phase 1.x), the toid table's
# polygon_geom column gets populated and the canonical Lleolydd
# semantics return: point-in-polygon, not point-proximity. The two
# `contested-prox`/`contested-lids` variants collapse back into a single
# `contested` band (multiple polygon hits OR LIDS-spatial disagreement).
#
# The reference query — what classify_bands_polygon will look like:
#
#     CREATE TEMP TABLE _uprn_spatial AS
#     SELECT u.uprn,
#            COUNT(t.toid) AS spatial_hit_count,
#            ANY_VALUE(t.toid) AS spatial_toid_any
#     FROM uprn u
#     LEFT JOIN toid t
#       ON ST_Within(u.point_geom, t.polygon_geom)
#     GROUP BY u.uprn;
#
#     UPDATE uprn AS u SET snap_band = CASE
#         WHEN <no LIDS>                                  THEN 'non-postal'
#         WHEN COALESCE(s.spatial_hit_count, 0) = 0       THEN 'unsnapped'
#         WHEN s.spatial_hit_count >= 2                   THEN 'contested'
#         WHEN s.spatial_hit_count = 1
#              AND l.lids_toid_any = s.spatial_toid_any   THEN 'auto-snapped'
#         ELSE 'contested'
#     END, ...
#
# This module is shaped so the switch is mechanical when polygons return:
# the data dependency (toid.polygon_geom non-null) is the signal; the
# rest of the surface (BandStats fields, manifest band labels, CLI
# printing) is what we'll need to refactor in that PR.
