#!/usr/bin/env python3
"""
craidd-propose — submit a proposal claim into the queue (cli-design.md §4.2).

A proposal is a candidate claim awaiting curator review. craidd-propose
assembles one — from a file, from flags, or from interactive prompts —
validates it against the schema layer, and writes it as a JSON file into
the proposals queue. It is the curator's manual entry point; client code
(the energy study) reaches the same proposal format through
client/craidd_client.py.

WHAT IT DOES NOT DO
-------------------
It does not accept, review, or fetch. It does not touch the canonical
database — proposals are files until craidd-review reads them. It does
not resolve a subject_hint to an entity; that, the predicate's applies_to
check, and single-cardinality conflicts all need the live store and are
craidd-review's job. A clean run here means the proposal is well formed
enough to enter the queue — never that it will be accepted.

VALIDATION IS PARTIAL BY DESIGN
-------------------------------
craidd.schema.validate_proposal checks everything decidable without the
database: the predicate exists and is not deprecated, the value's type
matches the predicate, required qualifiers are present, confidence is
valid, the source carries an id, and the subject is identified. The
DB-dependent checks are deferred to craidd-review.

NOTE — Prawf entry: the architecture.md §3 register row for craidd-propose
reads "Proposal file + Prawf entry". The Prawf logger (architecture.md
§6.11) is not built yet, so — exactly as craidd-init does for its genesis
entry — craidd-propose writes the proposal file with submitter and
timestamp recorded inside it, and the Prawf entry is deferred until the
Prawf logger ships. This is a known deferral, not a silent gap.

USAGE
-----
    # from a JSON or YAML file
    python3 src/cli/craidd_propose.py --from-file proposal.json

    # from flags
    python3 src/cli/craidd_propose.py \\
        --subject TDS-DOL-B-00001 --predicate floor_area_m2 \\
        --value 142.6 --source-id TDS-DOL-SRC-DOL-ENERGY-2026 \\
        --confidence medium --note "EPC match audit"

    # interactive — prompts field by field
    python3 src/cli/craidd_propose.py

    --from-file PATH     a JSON (.json) or YAML (.yaml/.yml) proposal
    --subject ID         subject entity_id (use this OR --subject-hint)
    --subject-hint K=V   subject hint pair, repeatable (uprn=..., segment_id=...)
    --predicate NAME     a v0.1 predicate name
    --value V            the claim value (coerced to the predicate's type)
    --value-cy TEXT      Welsh value, for bilingual predicates
    --value-en TEXT      English value, for bilingual predicates
    --source-id ID       id of the source entity the claim cites
    --confidence LEVEL   high | medium | low
    --qualifier K=V      qualifier pair, repeatable (dialect=cy-GB-north, ...)
    --note TEXT          curator-readable note
    --evidence-uri URI   pointer to raw evidence
    --submitter ID       who is submitting (default: the --actor value)
    --actor NAME         curator/client identity (default: "craidd-propose")
    --data-dir PATH      proposals written to PATH/proposals/
                         (default: /srv/town-dataset)
    --dry-run            assemble and validate; write nothing
    --json               machine-readable output

EXIT CODES
----------
    0  success (proposal written), or a clean dry-run
    1  the proposal failed schema validation — nothing written
    2  error — input could not be assembled (file missing/unparseable,
       bad arguments, or the proposals directory is not writable)
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Put the src/ root on the import path so `craidd.*` resolves when this
# script is run directly: python3 src/cli/craidd_propose.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from craidd import SCHEMA_VERSION
from craidd.schema import PREDICATE_REGISTRY, validate_proposal
from craidd.storage import DEFAULT_DATA_DIR


# --- proposal assembly -------------------------------------------------------

def _new_proposal_id(now: datetime) -> str:
    """Proposal id in the client/craidd_client.py format:
    P-<YYYYMMDD-HHMMSS>-<uuid8>."""
    return f"P-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _parse_kv_pairs(items: list[str], *, coerce: bool) -> dict[str, Any]:
    """Parse ['k=v', ...] into a dict. With coerce=True, values that look
    like ints or floats are converted (used for subject hints, where
    uprn/segment_id are numeric); with coerce=False, values stay strings
    (used for qualifiers, whose vocabulary is all text)."""
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected KEY=VALUE, got {item!r}")
        key, _, raw = item.partition("=")
        key = key.strip()
        raw = raw.strip()
        if not key:
            raise ValueError(f"empty key in {item!r}")
        if coerce:
            out[key] = _coerce_loose(raw)
        else:
            out[key] = raw
    return out


def _coerce_loose(raw: str) -> Any:
    """Best-effort scalar coercion for subject-hint values: int, then
    float, else the original string."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _coerce_value(raw: str, value_type: str) -> Any:
    """Coerce a flag-supplied string value to the predicate's value_type.
    Bilingual values are not handled here — they come from --value-cy /
    --value-en. An unknown value_type leaves the value as a string (the
    predicate is unknown; validate_proposal will report that)."""
    if value_type == "int":
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"value {raw!r} is not an integer")
    if value_type == "real":
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"value {raw!r} is not a number")
    # text, date, geom, entity_ref — and the unknown-predicate fallback
    return raw


def _load_proposal_file(path: Path) -> dict[str, Any]:
    """Load a proposal from a JSON or YAML file. YAML needs PyYAML; if it
    is not installed the error names requirements.txt."""
    if not path.exists():
        raise FileNotFoundError(f"proposal file not found: {path}")
    text = path.read_text()
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # noqa: PLC0415 — optional dependency, imported lazily
        except ImportError:
            raise ValueError(
                f"{path} is YAML, but PyYAML is not installed. "
                f"Install it (pip install pyyaml — it is in requirements.txt) "
                f"or supply the proposal as JSON."
            )
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: a proposal file must contain a single mapping/object"
        )
    return data


def _build_from_flags(args: argparse.Namespace) -> dict[str, Any]:
    """Assemble a proposal dict from command-line flags."""
    predicate = args.predicate
    pred = PREDICATE_REGISTRY.get(predicate) if predicate else None

    # value: bilingual from --value-cy/--value-en, otherwise coerced --value
    value: Any
    if args.value_cy is not None or args.value_en is not None:
        value = {}
        if args.value_cy is not None:
            value["cy"] = args.value_cy
        if args.value_en is not None:
            value["en"] = args.value_en
    elif args.value is not None:
        value_type = pred.value_type if pred is not None else None
        value = _coerce_value(args.value, value_type or "text")
    else:
        value = None

    subject_hint = (
        _parse_kv_pairs(args.subject_hint, coerce=True)
        if args.subject_hint
        else None
    )
    qualifiers = (
        _parse_kv_pairs(args.qualifier, coerce=False) if args.qualifier else {}
    )

    return {
        "subject": args.subject,
        "subject_hint": subject_hint,
        "predicate": predicate,
        "value": value,
        "source": {"id": args.source_id} if args.source_id else None,
        "confidence": args.confidence,
        "qualifiers": qualifiers,
        "evidence_uri": args.evidence_uri,
        "note": args.note,
    }


def _prompt(label: str, *, default: str | None = None,
            allow_blank: bool = False) -> str:
    """Prompt for a single line. Re-asks on blank input unless a default
    is offered or blank is explicitly allowed."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            answer = input(f"{label}{suffix}: ").strip()
        except EOFError:
            answer = ""
        if answer:
            return answer
        if default is not None:
            return default
        if allow_blank:
            return ""
        print("  (a value is required)")


def _build_interactive() -> dict[str, Any]:
    """Assemble a proposal dict by prompting the curator field by field."""
    print("craidd-propose — interactive. Ctrl-C to abort.\n")

    # predicate first: it tells us what shape the value and qualifiers take
    while True:
        predicate = _prompt("predicate")
        pred = PREDICATE_REGISTRY.get(predicate)
        if pred is not None:
            break
        print(f"  '{predicate}' is not a known predicate. "
              f"{len(PREDICATE_REGISTRY)} are registered — see "
              f"design/v0.1-schema.md §3.5.")
    print(f"  -> {pred.value_type} / {pred.cardinality} / applies to "
          f"{', '.join(pred.applies_to_types)}")
    print(f"  -> {pred.description_en}")
    if pred.required_qualifiers:
        print(f"  -> requires qualifier(s): "
              f"{', '.join(pred.required_qualifiers)}")

    # subject: an entity_id, or a hint
    subject = _prompt(
        "subject entity_id (blank to give a hint instead)", allow_blank=True
    ) or None
    subject_hint: dict[str, Any] | None = None
    if subject is None:
        print("  give one or more subject-hint pairs (e.g. uprn=10070355430)")
        hint_pairs: list[str] = []
        while True:
            pair = _prompt("  hint K=V (blank to finish)", allow_blank=True)
            if not pair:
                break
            hint_pairs.append(pair)
        subject_hint = (
            _parse_kv_pairs(hint_pairs, coerce=True) if hint_pairs else None
        )

    # value, shaped by the predicate's value_type
    value: Any
    if pred.value_type == "bilingual":
        cy = _prompt("  value (cy)", allow_blank=True)
        en = _prompt("  value (en)", allow_blank=True)
        value = {}
        if cy:
            value["cy"] = cy
        if en:
            value["en"] = en
    else:
        raw = _prompt(f"value ({pred.value_type})")
        try:
            value = _coerce_value(raw, pred.value_type)
        except ValueError as exc:
            print(f"  {exc} — keeping it as text; validation will flag it.")
            value = raw

    # qualifiers — required ones first, then any extras
    qualifiers: dict[str, Any] = {}
    for required in pred.required_qualifiers:
        qualifiers[required] = _prompt(f"  qualifier '{required}'")
    print("  any other qualifiers? (e.g. dialect=cy-GB-north)")
    while True:
        pair = _prompt("  qualifier K=V (blank to finish)", allow_blank=True)
        if not pair:
            break
        extra = _parse_kv_pairs([pair], coerce=False)
        qualifiers.update(extra)

    source_id = _prompt("source entity id")
    confidence = _prompt("confidence (high/medium/low)", default="medium")
    note = _prompt("note (optional)", allow_blank=True) or None
    evidence_uri = _prompt("evidence URI (optional)", allow_blank=True) or None

    return {
        "subject": subject,
        "subject_hint": subject_hint,
        "predicate": predicate,
        "value": value,
        "source": {"id": source_id},
        "confidence": confidence,
        "qualifiers": qualifiers,
        "evidence_uri": evidence_uri,
        "note": note,
    }


def _finalise(proposal: dict[str, Any], *, submitter: str,
              now: datetime) -> dict[str, Any]:
    """Stamp the assembled proposal with id, schema version, submitter,
    timestamp, and pending status — and normalise the key order to match
    client/craidd_client.py output so craidd-review reads one format."""
    return {
        "proposal_id": _new_proposal_id(now),
        "schema_version": SCHEMA_VERSION,
        "submitter": submitter,
        "submitted_at": now.isoformat(timespec="seconds"),
        "subject": proposal.get("subject"),
        "subject_hint": proposal.get("subject_hint"),
        "predicate": proposal.get("predicate"),
        "value": proposal.get("value"),
        "source": proposal.get("source"),
        "confidence": proposal.get("confidence"),
        "qualifiers": proposal.get("qualifiers") or {},
        "evidence_uri": proposal.get("evidence_uri"),
        "note": proposal.get("note"),
        "status": "pending",
    }


# --- reporting ---------------------------------------------------------------

def _report_failure(as_json: bool, *, code: int, reason: str,
                    detail: list[str]) -> None:
    if as_json:
        print(json.dumps(
            {"ok": False, "exit_code": code, "reason": reason,
             "detail": detail},
            indent=2,
        ))
    else:
        print(f"craidd-propose: FAILED — {reason}", file=sys.stderr)
        for line in detail:
            print(f"  - {line}", file=sys.stderr)


def _report_dry_run(as_json: bool, proposal: dict[str, Any]) -> None:
    if as_json:
        print(json.dumps(
            {"ok": True, "dry_run": True, "proposal": proposal}, indent=2,
        ))
    else:
        print("craidd-propose: DRY RUN — validated, nothing written")
        print(json.dumps(proposal, indent=2))


def _report_success(as_json: bool, proposal: dict[str, Any],
                    path: Path) -> None:
    if as_json:
        print(json.dumps(
            {"ok": True, "dry_run": False, "proposal_id":
             proposal["proposal_id"], "path": str(path)},
            indent=2,
        ))
    else:
        print("craidd-propose: OK — proposal written to the queue")
        print(f"  proposal_id : {proposal['proposal_id']}")
        print(f"  predicate   : {proposal['predicate']}")
        subject = proposal.get("subject") or proposal.get("subject_hint")
        print(f"  subject     : {subject}")
        print(f"  confidence  : {proposal['confidence']}")
        print(f"  file        : {path}")


# --- main --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="craidd-propose",
        description="Submit a proposal claim into the queue "
                    "(cli-design.md §4.2).",
    )
    parser.add_argument("--from-file", default=None,
                        help="a JSON or YAML proposal file")
    parser.add_argument("--subject", default=None,
                        help="subject entity_id (use this OR --subject-hint)")
    parser.add_argument("--subject-hint", action="append", default=[],
                        metavar="K=V",
                        help="subject hint pair, repeatable")
    parser.add_argument("--predicate", default=None,
                        help="a v0.1 predicate name")
    parser.add_argument("--value", default=None,
                        help="the claim value (coerced to the predicate type)")
    parser.add_argument("--value-cy", default=None,
                        help="Welsh value, for bilingual predicates")
    parser.add_argument("--value-en", default=None,
                        help="English value, for bilingual predicates")
    parser.add_argument("--source-id", default=None,
                        help="id of the source entity the claim cites")
    parser.add_argument("--confidence", default=None,
                        choices=("high", "medium", "low"),
                        help="high | medium | low")
    parser.add_argument("--qualifier", action="append", default=[],
                        metavar="K=V", help="qualifier pair, repeatable")
    parser.add_argument("--note", default=None,
                        help="curator-readable note")
    parser.add_argument("--evidence-uri", default=None,
                        help="pointer to raw evidence")
    parser.add_argument("--submitter", default=None,
                        help="who is submitting (default: the --actor value)")
    parser.add_argument("--actor", default="craidd-propose",
                        help="curator/client identity")
    parser.add_argument("--data-dir", default=None,
                        help="proposals written to PATH/proposals/ "
                             "(default: /srv/town-dataset)")
    parser.add_argument("--dry-run", action="store_true",
                        help="assemble and validate; write nothing")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="machine-readable output")
    args = parser.parse_args(argv)

    # --- 1. assemble the proposal from whichever input mode -------------
    try:
        if args.from_file:
            raw = _load_proposal_file(Path(args.from_file))
        elif args.predicate is not None:
            raw = _build_from_flags(args)
        else:
            raw = _build_interactive()
    except KeyboardInterrupt:
        print("\ncraidd-propose: aborted.", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        _report_failure(args.as_json, code=2,
                        reason="could not assemble the proposal",
                        detail=[str(exc)])
        return 2

    # A file may already carry submitter / submitted_at / proposal_id;
    # _finalise restamps them so every queued proposal is consistent.
    submitter = args.submitter or raw.get("submitter") or args.actor
    proposal = _finalise(raw, submitter=submitter,
                         now=datetime.now(timezone.utc))

    # --- 2. validate against the schema layer ---------------------------
    errors = validate_proposal(proposal)
    if errors:
        _report_failure(args.as_json, code=1,
                        reason="proposal failed schema validation",
                        detail=errors)
        return 1

    # --- 3. dry run: report and stop ------------------------------------
    if args.dry_run:
        _report_dry_run(args.as_json, proposal)
        return 0

    # --- 4. write the proposal file -------------------------------------
    data_dir = Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR
    proposals_dir = data_dir / "proposals"
    try:
        proposals_dir.mkdir(parents=True, exist_ok=True)
        path = proposals_dir / f"{proposal['proposal_id']}.json"
        path.write_text(json.dumps(proposal, indent=2))
    except OSError as exc:
        _report_failure(args.as_json, code=2,
                        reason="could not write to the proposals directory",
                        detail=[f"{proposals_dir}: {exc}"])
        return 2

    _report_success(args.as_json, proposal, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
