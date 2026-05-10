"""
Craidd Client — v0 file-backed Python interface to the Dolgellau Town
Dataset Craidd.

The contract this implements is documented in design/client-contract.md.
The function signatures here are the durable interface. When v1 replaces
files with HTTP-and-mTLS, the same `Craidd(...).method(...)` calls will
work; only the constructor and internals change.

USAGE
-----
    from client.craidd_client import Craidd

    craidd = Craidd()  # auto-detects repo and proposal paths

    # READ: get the canonical UPRN lookup
    df = craidd.uprn_lookup()
    print(f"{len(df)} buildings, {df['uprn'].notna().sum()} with UPRNs")

    # READ: look up a building by survey identity (segment + property name)
    row = craidd.find_by_survey(segment=1, property_name="Dylanwad")
    print(row["uprn"], row["match_confidence"])

    # WRITE: submit a proposal claim
    path = craidd.propose_claim(
        submitter="dolgellau-energy-study",
        subject_hint={"uprn": 10070355430, "segment_id": 1,
                      "property_name": "Dylanwad"},
        predicate="floor_area_m2",
        value=227.0,
        source={
            "id": "TDS-DOL-SRC-DOLGELLAU-ENERGY-STUDY",
            "title_en": "Dolgellau Energy Study, May 2026",
            "organisation": "Arloesi Dolgellau CIC",
        },
        confidence="medium",
        note="Floor area from EPC match audit.",
        evidence_uri="file://.../Dolgellau_epc_match_audit.csv#row=2",
    )
    print(f"Proposal written to {path}")

CONSTRAINTS
-----------
- Read paths are read-only from the client's perspective. Don't write
  to seed/output/ files from a client — propose changes instead.
- A proposal must have EITHER `subject` (a known entity_id) OR
  `subject_hint` (a dict identifying the building by other keys).
  In v0 most clients use subject_hint because entity_ids aren't yet
  populated for most buildings.
- predicate must be in the v0.1 starter set (see v0.1-schema.md §3.5).
  This module does not currently validate predicate names against the
  registry — that check happens at curator review.
- confidence must be one of: high, medium, low.
"""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


VALID_CONFIDENCES = ("high", "medium", "low")


class Craidd:
    """V0 file-backed Craidd client.

    Auto-detects the Town Dataset repo root by looking at this module's
    location (it sits at {repo_root}/client/craidd_client.py). The default
    proposals output directory is at
    {repo_root}/../handovers/dolgellau-energy-study/proposals-out/
    — adjust the `proposals_out` parameter if your client is not the
    energy study.
    """

    def __init__(
        self,
        repo_root: Path | str | None = None,
        proposals_out: Path | str | None = None,
    ):
        if repo_root is None:
            repo_root = Path(__file__).resolve().parents[1]
        self.repo_root = Path(repo_root)

        if proposals_out is None:
            proposals_out = (
                self.repo_root.parent
                / "handovers"
                / "dolgellau-energy-study"
                / "proposals-out"
            )
        self.proposals_out = Path(proposals_out)
        self.proposals_out.mkdir(parents=True, exist_ok=True)

    # =================================================================
    # Reads — canonical reference data from the Town Dataset
    # =================================================================

    def uprn_lookup(self) -> pd.DataFrame:
        """Return the canonical UPRN lookup table as a DataFrame.

        Columns: Segment, Property Name, Property Type, uprn,
        match_source, match_confidence, match_score, matched_at, notes.
        The uprn column is the pandas nullable Int64 dtype, so missing
        UPRNs are pd.NA rather than NaN-as-float.
        """
        path = self.repo_root / "seed" / "output" / "uprn-lookup.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"UPRN lookup not found at {path}. "
                "Run seed/uprn-from-epc.py first to generate it."
            )
        return pd.read_csv(path, dtype={"uprn": "Int64"})

    def find_by_survey(
        self, segment: int, property_name: str
    ) -> dict[str, Any] | None:
        """Find a building by its energy-study survey identity.

        Returns the matching row as a dict, or None if no match.
        Raises ValueError if multiple matches (which shouldn't happen
        in clean data).
        """
        df = self.uprn_lookup()
        matches = df[
            (df["Segment"] == segment) & (df["Property Name"] == property_name)
        ]
        if len(matches) == 0:
            return None
        if len(matches) > 1:
            raise ValueError(
                f"Multiple matches for segment={segment}, "
                f"property_name={property_name!r}; ambiguous survey identity."
            )
        return matches.iloc[0].to_dict()

    def find_by_uprn(self, uprn: int) -> dict[str, Any] | None:
        """Find a building by UPRN. Returns the matching row as a dict,
        or None if no match. UPRN lookup is unique by construction."""
        df = self.uprn_lookup()
        matches = df[df["uprn"] == uprn]
        if len(matches) == 0:
            return None
        return matches.iloc[0].to_dict()

    # =================================================================
    # Writes — proposal claims, written to the proposals-out directory
    # =================================================================

    def propose_claim(
        self,
        submitter: str,
        predicate: str,
        value: Any,
        source: dict[str, Any],
        confidence: str,
        subject: str | None = None,
        subject_hint: dict[str, Any] | None = None,
        note: str | None = None,
        evidence_uri: str | None = None,
    ) -> Path:
        """Write a proposal-claim JSON file to the proposals-out directory.

        Returns the Path of the file written.

        Parameters
        ----------
        submitter : the client identifier (e.g. "dolgellau-energy-study").
        predicate : a v0.1 predicate name (see v0.1-schema.md §3.5).
        value : the claim value, type appropriate to the predicate.
        source : dict identifying the source entity. Must include `id`;
            should include `title_en`, `organisation`, optionally `url`.
        confidence : "high", "medium", or "low".
        subject : entity_id of the subject building/entity (if known).
        subject_hint : dict identifying the building by other keys
            (uprn, segment_id, property_name, etc.) when entity_id
            isn't yet known.
        note : optional curator-readable note explaining the claim.
        evidence_uri : optional pointer to raw evidence (file path,
            archived URL, etc.).

        Raises
        ------
        ValueError if neither subject nor subject_hint is provided, or
            if confidence is not in the valid set, or if source lacks `id`.
        """
        if subject is None and subject_hint is None:
            raise ValueError(
                "propose_claim requires either subject (entity_id) "
                "or subject_hint (dict identifying the subject)."
            )
        if confidence not in VALID_CONFIDENCES:
            raise ValueError(
                f"confidence must be one of {VALID_CONFIDENCES}, "
                f"got {confidence!r}."
            )
        if not isinstance(source, dict) or "id" not in source:
            raise ValueError(
                "source must be a dict including an 'id' field."
            )

        now = datetime.now(timezone.utc)
        proposal_id = (
            f"P-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        )
        proposal = {
            "proposal_id": proposal_id,
            "schema_version": "v0.1",
            "submitter": submitter,
            "submitted_at": now.isoformat(timespec="seconds"),
            "subject": subject,
            "subject_hint": subject_hint,
            "predicate": predicate,
            "value": value,
            "source": source,
            "confidence": confidence,
            "evidence_uri": evidence_uri,
            "note": note,
            "status": "pending",
        }

        path = self.proposals_out / f"{proposal_id}.json"
        path.write_text(json.dumps(proposal, indent=2, default=_json_default))
        return path

    # =================================================================
    # Convenience
    # =================================================================

    def list_pending_proposals(self) -> list[Path]:
        """List all pending proposal files in the proposals-out
        directory. Useful for curators previewing the review queue."""
        return sorted(self.proposals_out.glob("P-*.json"))


def _json_default(obj: Any) -> Any:
    """Fallback JSON serialiser for things json doesn't natively handle
    (datetimes, pandas NaN, numpy ints, etc.)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if pd.isna(obj):
        return None
    if hasattr(obj, "item"):  # numpy scalars
        return obj.item()
    return str(obj)
