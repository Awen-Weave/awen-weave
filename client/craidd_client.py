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
import contextlib
import json
import os
import sys
import tempfile
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
    validate_entity_proposal,
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
    # Entity proposals — design/entity-proposal-shape.md §6
    # =================================================================

    def propose_entity(
        self,
        submitter: str,
        entity_type: str,
        names: list[dict[str, str]],
        source: dict[str, Any],
        note: dict[str, str] | str | None = None,
        confidence: str = "high",
        *,
        address_text: str | None = None,
        external_refs: list[dict[str, str]] | None = None,
        qualifiers: dict[str, Any] | None = None,
        field_session_id: str | None = None,
        bundle_id: str | None = None,
    ) -> str:
        """Write an entity proposal to the proposals-out directory.

        Returns the proposal_id, a string of shape
        EP-<YYYYMMDD>-<HHMM>-<8-hex>. The file lands at
        proposals_out/<proposal_id>.json.

        See design/entity-proposal-shape.md for the proposal shape. The
        bundle_id parameter binds this proposal to a bundle assembled
        separately — under normal use, propose_bundle is the entry point
        for bundles and this parameter stays None.

        Validates via craidd.schema.validate_entity_proposal before
        writing. Raises ValueError with the error list on validation
        failure, same pattern as propose_claim. The write is atomic
        (tempfile + os.rename); a mid-write disk failure leaves no
        partial file at the proposal's final path.

        Parameters
        ----------
        submitter : the curator/client identifier (e.g.
            "huw@arloesidolgellau.com" for human curators or
            "lleolydd-serve" for components).
        entity_type : one of the v0.1 entity types (see VALID_ENTITY_TYPES).
            v1 expected use is "building"; the validator accepts any
            v0.1 type, with the UI in Lleolydd scoping to building only.
        names : non-empty list of {value, language, name_type} dicts.
            language is "cy" or "en"; name_type is from NAME_TYPES.
        source : dict identifying the source entity. Must include `id`
            (matches the canonical claim-proposal shape — see completion
            brief notes; validate_entity_proposal also accepts `source_id`
            for forward-compat).
        note : optional bilingual note. Pass a dict like
            {"cy": "...", "en": "..."} for explicit bilingual content,
            or a plain string as shorthand for English-only.
        confidence : "high" (default), "medium", or "low". Curators
            creating entities are presumed confident; override for
            uncertain cases.
        address_text : optional free-text address (no format validation).
        external_refs : optional list of {scheme, value} dicts. Schemes
            from KNOWN_EXTERNAL_REF_SCHEMES (uprn, toid, cadw, blb, nhle,
            osm-id). Values get per-scheme shape checks.
        qualifiers : optional mapping of v0.1 qualifier keys to values.
            Closed-domain values must be in their domain. Cross-rule:
            co_signed_by requires field_session_id in the same mapping.
        field_session_id : optional FS- session identifier for synchronous
            field-session work (design/lleolydd.md §12.A).
        bundle_id : optional B- bundle identifier; used by propose_bundle
            when this method is called on its behalf.

        Raises
        ------
        ValueError : if the assembled proposal fails schema validation.
        """
        proposal_id = _new_ep_id(datetime.now(timezone.utc))
        proposal = _assemble_entity_proposal(
            proposal_id=proposal_id,
            submitter=submitter,
            entity_type=entity_type,
            names=names,
            source=source,
            note=note,
            confidence=confidence,
            address_text=address_text,
            external_refs=external_refs,
            qualifiers=qualifiers,
            field_session_id=field_session_id,
            bundle_id=bundle_id,
        )
        errors = validate_entity_proposal(proposal)
        if errors:
            raise ValueError(
                "entity proposal failed schema validation — "
                + "; ".join(errors)
            )
        path = self.proposals_out / f"{proposal_id}.json"
        _atomic_write_json(path, proposal)
        return proposal_id

    def propose_bundle(
        self,
        submitter: str,
        entity_proposal: dict[str, Any],
        claim_proposals: list[dict[str, Any]],
        *,
        field_session_id: str | None = None,
    ) -> str:
        """Submit an entity proposal + N claim proposals as an atomic bundle.

        Returns the bundle_id, a string of shape
        B-<YYYYMMDD>-<HHMM>-<8-hex>. Every proposal in the bundle carries
        the bundle_id so craidd-review can present and act on them as a
        unit (see design/entity-proposal-shape.md §4).

        Atomicity:
          - Validation: all proposals validate before any file is written.
            If any single proposal fails, no files exist on disk and the
            full error list is raised in a ValueError.
          - Write phase: each proposal is written to a temp file in
            proposals_out using tempfile.NamedTemporaryFile, then renamed
            into its final position with os.rename (atomic on POSIX,
            same-filesystem). If any rename fails partway through, the
            temp files for un-renamed proposals are removed, but already-
            renamed files stay in place — craidd-review can detect partial
            state via the shared bundle_id and surface for cleanup.

        Parameters
        ----------
        submitter : the client identifier — propagated to every proposal
            in the bundle.
        entity_proposal : a dict of the keyword args for propose_entity
            (entity_type, names, source, etc.). The submitter and
            bundle_id are filled in by this method.
        claim_proposals : a list of dicts each shaped like the keyword
            args for propose_claim, minus subject identification. Each
            claim attaches to the bundled entity (subject_hint='<bundle>'
            sentinel, resolved at acceptance time per
            design/entity-proposal-shape.md §5).
        field_session_id : optional FS- identifier propagated to every
            proposal in the bundle (so a single co-signed field session
            covers all members).

        Raises
        ------
        ValueError : if any single proposal in the bundle fails
            validation. Carries the full per-proposal error list.
        OSError : if a disk operation fails (caller can interrogate
            the proposals_out directory for partial state via the
            bundle_id).
        """
        bundle_id = _new_bundle_id(datetime.now(timezone.utc))

        # --- Phase 1: assemble + validate ALL proposals before writing any.
        # If any one fails, raise ValueError with the consolidated errors
        # and write nothing.
        assembled: list[tuple[str, dict[str, Any]]] = []
        all_errors: list[str] = []

        ep_id = _new_ep_id(datetime.now(timezone.utc))
        ep = _assemble_entity_proposal(
            proposal_id=ep_id,
            submitter=submitter,
            entity_type=entity_proposal["entity_type"],
            names=entity_proposal["names"],
            source=entity_proposal["source"],
            note=entity_proposal.get("note"),
            confidence=entity_proposal.get("confidence", "high"),
            address_text=entity_proposal.get("address_text"),
            external_refs=entity_proposal.get("external_refs"),
            qualifiers=entity_proposal.get("qualifiers"),
            field_session_id=(
                field_session_id
                or entity_proposal.get("field_session_id")
            ),
            bundle_id=bundle_id,
        )
        ep_errors = validate_entity_proposal(ep)
        if ep_errors:
            all_errors.extend(f"EP {ep_id}: {e}" for e in ep_errors)
        assembled.append((ep_id, ep))

        for i, claim_args in enumerate(claim_proposals):
            claim_id = _new_proposal_id(datetime.now(timezone.utc))
            claim = _assemble_bundled_claim(
                proposal_id=claim_id,
                submitter=submitter,
                claim_args=claim_args,
                bundle_id=bundle_id,
                field_session_id=field_session_id,
            )
            claim_errors = validate_proposal(claim)
            if claim_errors:
                all_errors.extend(
                    f"claim[{i}] {claim_id}: {e}" for e in claim_errors
                )
            assembled.append((claim_id, claim))

        if all_errors:
            raise ValueError(
                "bundle failed schema validation — "
                + "; ".join(all_errors)
            )

        # --- Phase 2: atomic-ish write. Each proposal goes to a temp
        # file in proposals_out first; all temps are written and fsync'd
        # before any rename. Then rename each into its final position.
        # The EP renames first so any partial-bundle state visible to a
        # concurrent craidd-review still has an entity to attach claims
        # to (per brief §3 "order of writes matters").
        proposals_dir = self.proposals_out
        temps: list[tuple[str, Path]] = []
        try:
            for proposal_id, proposal in assembled:
                tmp = tempfile.NamedTemporaryFile(
                    dir=proposals_dir,
                    prefix=f".{proposal_id}-",
                    suffix=".json.tmp",
                    delete=False,
                    mode="w",
                )
                try:
                    json.dump(
                        proposal, tmp, indent=2, default=_json_default
                    )
                    tmp.flush()
                    os.fsync(tmp.fileno())
                finally:
                    tmp.close()
                temps.append((tmp.name, proposals_dir / f"{proposal_id}.json"))

            # All temp files exist; promote each to its final name.
            # EP is first in `assembled`, so its rename happens first.
            for tmp_path, final_path in temps:
                os.rename(tmp_path, final_path)
        except Exception:
            # Clean up any remaining temp files. Already-renamed files
            # stay in place — craidd-review can find them by bundle_id
            # and decide whether to accept or cleanup.
            for tmp_path, _ in temps:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(tmp_path)
            raise

        return bundle_id

    # =================================================================
    # Convenience
    # =================================================================

    def list_pending_proposals(self) -> list[Path]:
        """List all pending proposal files in the proposals-out
        directory. Useful for curators previewing the review queue."""
        return sorted(self.proposals_out.glob("P-*.json"))

    def list_pending_entity_proposals(self) -> list[Path]:
        """List all pending entity-proposal files (EP-*.json) in the
        proposals-out directory. Companion to list_pending_proposals;
        keeps the two shapes separately enumerable for craidd-review."""
        return sorted(self.proposals_out.glob("EP-*.json"))


def _new_proposal_id(now: datetime) -> str:
    """Proposal id: P-<YYYYMMDD-HHMMSS>-<uuid8>. Shared by every claim-
    proposal-writing method so the id format is single-sourced.

    Note the second-precision timestamp — claim proposals can be created
    at sub-minute cadence (BRA stage-2 listings runs produce dozens per
    minute) so the HHMMSS form is necessary. Entity proposals (see
    _new_ep_id) use minute precision because curators don't create
    entities at sub-minute cadence."""
    return f"P-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _new_ep_id(now: datetime) -> str:
    """Entity-proposal id: EP-<YYYYMMDD>-<HHMM>-<uuid8>. Matches the
    regex enforced by craidd.schema.validate_entity_proposal
    (^EP-\\d{8}-\\d{4}-[0-9a-fA-F]{8}$).

    The minute-precision timestamp is deliberate — curators do not
    create entities at sub-minute cadence, so the slightly-shorter form
    matches the design-document examples and reads cleanly to humans."""
    return f"EP-{now.strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:8]}"


def _new_bundle_id(now: datetime) -> str:
    """Bundle id: B-<YYYYMMDD>-<HHMM>-<uuid8>. Same shape as entity-
    proposal ids (minute precision, 8-hex suffix) — distinguished only
    by the prefix character. Matches the regex enforced by
    craidd.schema.validate_proposal / validate_entity_proposal
    (^B-\\d{8}-\\d{4}-[0-9a-fA-F]{8}$)."""
    return f"B-{now.strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:8]}"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON file atomically using tempfile + os.rename.

    The temp file lives in path.parent (same filesystem), so the rename
    is atomic on POSIX. On any exception during write or rename, the
    temp file is removed and the original path is untouched.

    Used by propose_entity for single-file writes. propose_bundle does
    NOT call this helper because it needs to assemble all temp files
    before any rename — bundle-level atomicity requires the
    open-coded two-phase pattern."""
    tmp = tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".json.tmp",
        delete=False,
        mode="w",
    )
    try:
        try:
            json.dump(data, tmp, indent=2, default=_json_default)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.rename(tmp.name, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp.name)
        raise


def _normalise_note(
    note: dict[str, str] | str | None,
) -> dict[str, str] | None:
    """Accept either a bilingual mapping ({cy, en}) or a plain string
    shorthand (assumed English-only). Returns the mapping form, or None
    when no note was supplied."""
    if note is None:
        return None
    if isinstance(note, str):
        return {"en": note}
    return dict(note)


def _assemble_entity_proposal(
    *,
    proposal_id: str,
    submitter: str,
    entity_type: str,
    names: list[dict[str, str]],
    source: dict[str, Any],
    note: dict[str, str] | str | None,
    confidence: str,
    address_text: str | None,
    external_refs: list[dict[str, str]] | None,
    qualifiers: dict[str, Any] | None,
    field_session_id: str | None,
    bundle_id: str | None,
) -> dict[str, Any]:
    """Assemble an entity_proposal dict per
    design/entity-proposal-shape.md §3. Pure shape-building; validation
    is the caller's job (propose_entity calls validate_entity_proposal
    on the result)."""
    now = datetime.now(timezone.utc)
    proposal: dict[str, Any] = {
        "proposal_type": "entity",
        "proposal_id": proposal_id,
        "submitted_at": now.isoformat(timespec="seconds"),
        "submitter": submitter,
        "entity": {
            "entity_type": entity_type,
            "names": list(names),
        },
        "source": source,
        "confidence": confidence,
    }
    # Optional top-level fields — omit when absent so the file shape
    # matches the schema doc's worked examples (avoid null clutter).
    if field_session_id is not None:
        proposal["field_session_id"] = field_session_id
    if bundle_id is not None:
        proposal["bundle_id"] = bundle_id

    if address_text is not None:
        proposal["entity"]["address_text"] = address_text
    if external_refs is not None:
        proposal["entity"]["external_refs"] = list(external_refs)

    note_mapping = _normalise_note(note)
    if note_mapping is not None:
        proposal["note"] = note_mapping
    if qualifiers is not None:
        proposal["qualifiers"] = dict(qualifiers)

    return proposal


def _assemble_bundled_claim(
    *,
    proposal_id: str,
    submitter: str,
    claim_args: dict[str, Any],
    bundle_id: str,
    field_session_id: str | None,
) -> dict[str, Any]:
    """Assemble a claim proposal that is a member of a bundle. Differs
    from propose_claim's assembly in two ways: (1) subject_hint is the
    sentinel '<bundle>' string (validate_proposal recognises this when
    bundle_id is also present, deferring subject resolution to
    craidd-review), and (2) the bundle_id is set so the proposals can
    be grouped at review time."""
    now = datetime.now(timezone.utc)
    qualifiers = dict(claim_args.get("qualifiers") or {})
    # field_session_id on the bundle propagates to each claim's
    # qualifiers if not already present — saves the caller from
    # repeating it per-claim.
    if field_session_id is not None and "field_session_id" not in qualifiers:
        qualifiers["field_session_id"] = field_session_id

    proposal: dict[str, Any] = {
        "proposal_id": proposal_id,
        "schema_version": "v0.1",
        "submitter": submitter,
        "submitted_at": now.isoformat(timespec="seconds"),
        "subject": None,
        "subject_hint": "<bundle>",
        "bundle_id": bundle_id,
        "predicate": claim_args["predicate"],
        "value": claim_args["value"],
        "source": claim_args["source"],
        "confidence": claim_args.get("confidence", "high"),
        "qualifiers": qualifiers,
        "evidence_uri": claim_args.get("evidence_uri"),
        "note": claim_args.get("note"),
        "status": "pending",
    }
    return proposal


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
