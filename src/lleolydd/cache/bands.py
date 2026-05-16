"""
UPRN status-band classifier.

Per design/lleolydd.md §4, every UPRN gets one of five band labels:

  verified     a curator has placed/confirmed this UPRN against a TOID
               (a Craidd `verified_building_toid` claim). NOT computed
               in Phase 1 — Phase 2 viewer queries Craidd and upgrades
               in-memory; Phase 3 writes corrections back.
  auto-snapped UPRN point is inside exactly one building TOID polygon
               AND OS Linked Identifiers agrees that TOID belongs to
               this UPRN.
  unsnapped    UPRN point isn't inside any building TOID polygon
               (or there's no LIDS row at all and no spatial hit).
  contested    UPRN point is inside multiple building TOID polygons,
               OR LIDS says this UPRN belongs to a different TOID than
               the spatial match.
  non-postal   OS-allocated UPRN for a non-postal feature (substation,
               post box, defibrillator). v1 detected by absence from
               the LIDS BLPU-UPRN-TopographicArea-TOID file (LIDS only
               contains UPRNs that ARE linked to a building TOID; non-
               postal UPRNs aren't linked to a building).

Phase 1 sets every row's snap_band to one of {auto-snapped, unsnapped,
contested, non-postal}. The `verified` value never appears in the
cache table at v1 — it's a Phase 2 viewer-time computation.

The classifier runs as a single SQL pass once all four data sources
are loaded. No Python iteration over individual UPRNs — DuckDB's
spatial index handles the point-in-polygon work, and the whole
classifier completes in seconds for ~50k Gwynedd UPRNs.
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class BandStats:
    """Per-band UPRN counts produced by classify_bands(). Sum to
    total_uprns. Reported in completion brief and surfaced via
    `lleolydd-cache snapshot show`."""
    auto_snapped: int
    unsnapped: int
    contested: int
    non_postal: int

    @property
    def total(self) -> int:
        return (
            self.auto_snapped + self.unsnapped + self.contested + self.non_postal
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "auto-snapped": self.auto_snapped,
            "unsnapped": self.unsnapped,
            "contested": self.contested,
            "non-postal": self.non_postal,
            "total": self.total,
        }


def classify_bands(
    conn: duckdb.DuckDBPyConnection,
    snapshot_id: str,
) -> BandStats:
    """Populate uprn.snapped_toid + uprn.snap_band for every row in the
    cache. Returns per-band counts.

    Assumes the cache schema (uprn, toid, linked_id tables) is already
    populated by build.py's source-loading phase. Idempotent: re-runs
    overwrite the existing band assignments cleanly.

    Algorithm:
      1. Spatial match: for each UPRN point, find building TOID
         polygons that contain it. Aggregated by UPRN.
         - 0 spatial hits → candidate `unsnapped`
         - 1 spatial hit  → candidate `auto-snapped`, spatial_toid = that TOID
         - 2+ spatial hits → candidate `contested-spatial`
      2. LIDS match: lookup the UPRN in the linked_id table.
         - No LIDS row → candidate `non-postal` (per design §4 semantics)
         - LIDS row    → expected TOID = the linked TOID
      3. Combine:
         - non-postal LIDS  +  no spatial hit       → `non-postal`
         - non-postal LIDS  +  any spatial hit      → `non-postal`
                                                       (LIDS authority
                                                        overrides spatial
                                                        for non-postal
                                                        features)
         - LIDS row         +  0 spatial hits       → `unsnapped`
                                                       (LIDS knows about
                                                        a TOID but the
                                                        UPRN point doesn't
                                                        sit in it — the
                                                        rural-driveway
                                                        case)
         - LIDS row         +  1 spatial hit ==
           the linked TOID                          → `auto-snapped`
         - LIDS row         +  1 spatial hit !=
           the linked TOID                          → `contested`
                                                       (LIDS/spatial
                                                        disagree)
         - LIDS row         +  2+ spatial hits      → `contested`
    """
    # --- Step 1: spatial join. UPRN points inside building TOID polygons.
    # Stored in a temp table so step 3 can join it cleanly. ON_CONFLICT
    # isn't a thing for CREATE TEMP TABLE AS — we drop-create.
    conn.execute("DROP TABLE IF EXISTS _uprn_spatial")
    conn.execute(
        """
        CREATE TEMP TABLE _uprn_spatial AS
        SELECT
            u.uprn,
            -- COUNT(t.toid), NOT COUNT(*) — a LEFT JOIN with no match
            -- yields one NULL-padded row that COUNT(*) would still
            -- count as 1, miscategorising every unsnapped UPRN as
            -- having a single spatial hit. COUNT(<nullable>) drops
            -- NULL rows; this is the band classifier's load-bearing
            -- distinction between zero and one spatial match.
            COUNT(t.toid) AS spatial_hit_count,
            -- arbitrary-pick-one when there's exactly one match; NULL
            -- when 0 or when only NULL-padded rows exist (the
            -- contested-spatial case keeps spatial_toid_any meaningless
            -- — we ignore it for the band decision then).
            ANY_VALUE(t.toid) AS spatial_toid_any
        FROM uprn u
        LEFT JOIN toid t
          ON ST_Within(u.point_geom, t.polygon_geom)
        GROUP BY u.uprn
        """
    )

    # --- Step 2: collapse linked_id to one expected TOID per UPRN.
    # If a UPRN has multiple LIDS rows (multi-occupancy unit, etc.),
    # treat it as contested at the LIDS level. v1 keeps the simplest
    # model: one UPRN → one expected TOID.
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

    # --- Step 3: classify per UPRN using the combination matrix.
    # Update uprn.snap_band + uprn.snapped_toid in one pass.
    conn.execute(
        """
        UPDATE uprn AS u
        SET
            snapped_toid = CASE
                -- non-postal: LIDS gave us no row → no building linkage
                WHEN l.lids_row_count IS NULL OR l.lids_row_count = 0
                    THEN NULL
                -- LIDS + 0 or 2+ spatial hits → no single snap to record
                WHEN COALESCE(s.spatial_hit_count, 0) != 1
                    THEN NULL
                -- LIDS + 1 spatial match — record whichever TOID the
                -- spatial match found (will equal lids_toid when
                -- auto-snapped, differ when contested; storing the
                -- spatial answer is the more useful side for Phase 2
                -- viewer rendering)
                ELSE s.spatial_toid_any
            END,
            snap_band = CASE
                WHEN l.lids_row_count IS NULL OR l.lids_row_count = 0
                    THEN 'non-postal'
                WHEN COALESCE(s.spatial_hit_count, 0) = 0
                    THEN 'unsnapped'
                WHEN s.spatial_hit_count >= 2
                    THEN 'contested'
                WHEN s.spatial_hit_count = 1
                     AND l.lids_toid_any = s.spatial_toid_any
                    THEN 'auto-snapped'
                ELSE 'contested'
            END,
            snap_confidence = CASE
                WHEN l.lids_row_count IS NULL OR l.lids_row_count = 0
                    THEN 1.0  -- non-postal is a confident classification
                WHEN COALESCE(s.spatial_hit_count, 0) = 0
                    THEN 0.0
                WHEN s.spatial_hit_count >= 2
                    THEN 0.5
                WHEN s.spatial_hit_count = 1
                     AND l.lids_toid_any = s.spatial_toid_any
                    THEN 1.0
                ELSE 0.5
            END,
            snapshot_id = ?
        FROM _uprn_spatial s
        LEFT JOIN _uprn_lids l
          ON s.uprn = l.uprn
        WHERE u.uprn = s.uprn
        """,
        [snapshot_id],
    )

    conn.execute("DROP TABLE _uprn_spatial")
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
        contested=counts.get("contested", 0),
        non_postal=counts.get("non-postal", 0),
    )
