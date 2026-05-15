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
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

# The schema layer lives under src/; craidd_client.py sits at client/.
# Put src/ on the path so `craidd.schema` resolves however this module is
# imported (the energy-study recipe puts the repo root on the path, not
# src/). This is the back-compat seam noted in CLAUDE.md — the client
# stays at top-level, but it now depends on the foundation's validation
# contract so proposals are checked at submit, not deferred to review.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from craidd.schema import (  # noqa: E402 — import after the sys.path insert
    PREDICATE_REGISTRY,
    QUALIFIER_KEYS,
    validate_proposal,
    value_from_claim_columns,
)


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
        qualifiers: dict[str, Any] | None = None,
    ) -> Path:
        """Write a proposal-claim JSON file to the proposals-out directory.

        Returns the Path of the file written. The assembled proposal is
        run through craidd.schema.validate_proposal before it is written;
        an invalid proposal raises ValueError and no file is created.

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
        qualifiers : optional mapping of v0.1 qualifier keys to values
            (dialect, name_type, date_precision, floor_scope).

        Raises
        ------
        ValueError if neither subject nor subject_hint is provided, or
            if confidence is not in the valid set, or if source lacks
            `id`, or if the assembled proposal fails schema validation.
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
        proposal = {
            "proposal_id": _new_proposal_id(now),
            "schema_version": "v0.1",
            "submitter": submitter,
            "submitted_at": now.isoformat(timespec="seconds"),
            "subject": subject,
            "subject_hint": subject_hint,
            "predicate": predicate,
            "value": value,
            "source": source,
            "confidence": confidence,
            "qualifiers": qualifiers or {},
            "evidence_uri": evidence_uri,
            "note": note,
            "status": "pending",
        }
        return self._validate_and_write(proposal)

    def propose_from_claim(
        self,
        claim: dict[str, Any],
        submitter: str,
        *,
        note: str | None = None,
    ) -> Path:
        """Write a proposal from a claim-shaped record — the BRA ->
        proposal-queue adapter (design/bra-proposal-handoff.md).

        A claim-shaped record (e.g. BRA v2's DraftClaim.to_jsonable())
        carries its value spread across type-tagged value_* columns and
        identifies its subject and source by bare id. This method
        collapses the columns into the single proposal `value` via
        craidd.schema.value_from_claim_columns, wraps the source id,
        keeps only v0.1-vocabulary qualifiers (non-v0.1 qualifier keys
        are recorded in the note rather than silently dropped), and
        writes the result through the same validated path as
        propose_claim.

        Returns the Path of the file written.

        Parameters
        ----------
        claim : a claim-shaped mapping. Must carry `predicate`,
            `subject_id`, `source_id`, and the appropriate value_*
            column(s). `confidence`, `qualifiers`, `evidence_uri`, and
            `raw_value` are used if present.
        submitter : the contributor identifier.
        note : optional note. If omitted, the claim's `raw_value` (the
            preserved source text) becomes the note.

        Raises
        ------
        ValueError if the claim's predicate is unknown to the v0.1
            registry (e.g. a pending_schema='v0.2' draft — callers must
            filter those out first), if the value columns are
            inconsistent with the predicate, if the subject or source
            id is missing, or if the assembled proposal fails schema
            validation.
        """
        predicate = claim.get("predicate")
        pred = PREDICATE_REGISTRY.get(predicate) if predicate else None
        if pred is None:
            raise ValueError(
                f"propose_from_claim: predicate {predicate!r} is not in the "
                f"v0.1 registry. A pending_schema='v0.2' draft cannot enter "
                f"the v0.1 queue — filter those out before calling."
            )

        value, value_errors = value_from_claim_columns(claim, pred)
        if value_errors:
            raise ValueError(
                "propose_from_claim: claim value columns are inconsistent "
                "with the predicate — " + "; ".join(value_errors)
            )

        subject_id = claim.get("subject_id")
        if not subject_id:
            raise ValueError("propose_from_claim: claim has no subject_id")
        source_id = claim.get("source_id")
        if not source_id:
            raise ValueError("propose_from_claim: claim has no source_id")

        # Keep only v0.1-vocabulary qualifiers; record any others in the
        # note so they are preserved for the curator rather than lost.
        raw_qualifiers = claim.get("qualifiers") or {}
        v0_1_qualifiers = {
            k: v for k, v in raw_qualifiers.items() if k in QUALIFIER_KEYS
        }
        non_v0_1 = {
            k: v for k, v in raw_qualifiers.items() if k not in QUALIFIER_KEYS
        }

        note_parts: list[str] = []
        if note is not None:
            note_parts.append(note)
        elif claim.get("raw_value"):
            note_parts.append(f"source text: {claim['raw_value']}")
        if non_v0_1:
            note_parts.append(
                "non-v0.1 qualifiers (await v0.2): "
                + json.dumps(non_v0_1, ensure_ascii=False)
            )
        final_note = " | ".join(note_parts) if note_parts else None

        now = datetime.now(timezone.utc)
        proposal = {
            "proposal_id": _new_proposal_id(now),
            "schema_version": "v0.1",
            "submitter": submitter,
            "submitted_at": now.isoformat(timespec="seconds"),
            "subject": subject_id,
            "subject_hint": None,
            "predicate": predicate,
            "value": value,
            "source": {"id": source_id},
            "confidence": claim.get("confidence") or "medium",
            "qualifiers": v0_1_qualifiers,
            "evidence_uri": claim.get("evidence_uri"),
            "note": final_note,
            "status": "pending",
        }
        return self._validate_and_write(proposal)

    def _validate_and_write(self, proposal: dict[str, Any]) -> Path:
        """Validate an assembled proposal against the schema layer and,
        if it passes, write it to the proposals-out directory. Shared by
        propose_claim and propose_from_claim so both entry points get the
        same submit-time validation guarantee."""
        errors = validate_proposal(proposal)
        if errors:
            raise ValueError(
                "proposal failed schema validation — "
                + "; ".join(errors)
            )
        path = self.proposals_out / f"{proposal['proposal_id']}.json"
        path.write_text(json.dumps(proposal, indent=2, default=_json_default))
        return path

    # =================================================================
    # Convenience
    # =================================================================

    def list_pending_proposals(self) -> list[Path]:
        """List all pending proposal files in the proposals-out
        directory. Useful for curators previewing the review queue."""
        return sorted(self.proposals_out.glob("P-*.json"))


def _new_proposal_id(now: datetime) -> str:
    """Proposal id: P-<YYYYMMDD-HHMMSS>-<uuid8>. Shared by every
    proposal-writing method so the id format is single-sourced."""
    return f"P-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


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
