#!/usr/bin/env python3
"""
constitution_drift.py — fail loud if the awen-weave in-code model drifts
from the awen-constitution SCH-* it declares compatibility with.

The compatibility contract (awen-constitution/compatibility.md): for 0.1.x
the live code led and the constitution was reconciled to it; **from
constitution 0.2.0 onward the spec LEADS and this package validates against
it.** This check is that enforcement (brief §6 ride-along). It runs against
the constitution at the PINNED tag (craidd.CONSTITUTION_TAG), so a rules
change and a code change never silently diverge.

Two layers, both fail-loud:

  A. MODEL DIFF (exhaustive, precise) — every schema-decidable dimension of
     the code model (entity types, confidence/status/visibility enums, the
     14 qualifier keys, the 6 closed qualifier domains, the two cross-rules,
     the required claim fields) is compared to the corresponding SCH-*
     construct. Any symmetric difference is drift, reported by name.

  B. ROUND-TRIP (behavioural) — a corpus of representative documents is run
     through BOTH this package's validators AND the constitution schema; if
     the code accepts what the schema rejects (or vice-versa) that is drift.
     This catches divergence the enum diff cannot (e.g. a cross-rule whose
     wiring changed but whose vocabulary did not).

Usage:
  # CI: the constitution is checked out at the pinned tag into ./_constitution
  python scripts/constitution_drift.py --constitution ./_constitution

  # local: point at any clone / the awen-porth vendored tree
  python scripts/constitution_drift.py --constitution ~/Developer/awen-porth/constitution

Exit 0 = in sync. Exit 1 = drift (details on stderr). Exit 2 = setup error
(constitution tree missing, wrong tag, unreadable schema).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

from craidd import (  # noqa: E402
    CONSTITUTION_TAG,
    CONSTITUTION_VERSION,
    SCHEMA_VERSION,
    __name__ as _craidd_name,  # noqa: F401
)
from craidd.schema.entity_types import VALID_ENTITY_TYPES  # noqa: E402
from craidd.schema.qualifiers import (  # noqa: E402
    CLOSED_QUALIFIER_DOMAINS,
    QUALIFIER_KEYS,
)
from craidd.schema.validation import (  # noqa: E402
    VALID_CLAIM_STATUSES,
    VALID_CONFIDENCES,
    VALID_VISIBILITIES,
    validate_claim,
    validate_entity,
)


# --------------------------------------------------------------------------
# Loading the constitution (at the pinned tag)
# --------------------------------------------------------------------------
class Setup(Exception):
    pass


def load_constitution(root: Path) -> dict[str, Any]:
    if not root.exists():
        raise Setup(f"constitution tree not found at {root}")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if version != CONSTITUTION_VERSION:
        raise Setup(
            f"constitution VERSION is {version!r} but this package declares "
            f"CONSTITUTION_VERSION={CONSTITUTION_VERSION!r} (tag "
            f"{CONSTITUTION_TAG}). Check out the pinned tag, or bump the "
            f"declaration deliberately."
        )
    schema_dir = root / "schema"
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        stem = path.name[: -len(".schema.json")]
        schemas[stem] = json.loads(path.read_text(encoding="utf-8"))
    for required in ("claim", "entity"):
        if required not in schemas:
            raise Setup(f"missing schema/{required}.schema.json in {root}")
    return {"version": version, "schemas": schemas, "root": root}


# --------------------------------------------------------------------------
# Layer A — model diff
# --------------------------------------------------------------------------
def _enum(schema: dict, *path: str) -> set[str]:
    node = schema
    for key in path:
        node = node[key]
    return {v for v in node.get("enum", []) if v is not None}


def model_diff(schemas: dict[str, dict]) -> list[str]:
    claim = schemas["claim"]
    entity = schemas["entity"]
    qdefs = claim["$defs"]["qualifiers"]
    qprops = qdefs["properties"]
    drift: list[str] = []

    def cmp(name: str, code: set[str], spec: set[str]) -> None:
        if code != spec:
            only_code = sorted(code - spec)
            only_spec = sorted(spec - code)
            drift.append(
                f"{name}: code={sorted(code)} vs SCH={sorted(spec)}"
                + (f" | only-in-code={only_code}" if only_code else "")
                + (f" | only-in-SCH={only_spec}" if only_spec else "")
            )

    # 1. entity types
    cmp("entity_type", set(VALID_ENTITY_TYPES),
        _enum(entity, "properties", "entity_type"))
    # 2-4. claim enums
    cmp("confidence", set(VALID_CONFIDENCES), _enum(claim, "properties", "confidence"))
    cmp("status", set(VALID_CLAIM_STATUSES), _enum(claim, "properties", "status"))
    # 5. visibility (schema enum includes null; strip it)
    cmp("visibility", set(VALID_VISIBILITIES), _enum(entity, "properties", "visibility"))
    # 6. qualifier key set
    cmp("qualifier_keys", set(QUALIFIER_KEYS), set(qprops.keys()))
    # 7. each closed qualifier domain
    for key, domain in CLOSED_QUALIFIER_DOMAINS.items():
        spec_enum = {v for v in qprops.get(key, {}).get("enum", []) if v is not None}
        cmp(f"closed_domain.{key}", set(domain), spec_enum)

    # 8. cross-rule 1: co_signed_by ⇒ field_session_id
    dep = qdefs.get("dependentRequired", {}).get("co_signed_by")
    if dep != ["field_session_id"]:
        drift.append(
            f"cross-rule co_signed_by⇒field_session_id: SCH dependentRequired="
            f"{dep!r}, expected ['field_session_id']"
        )
    # 8. cross-rule 2: binding=federated ⇒ federated_from + source_ran_at
    fed_ok = False
    for clause in qdefs.get("allOf", []):
        cond = clause.get("if", {}).get("properties", {}).get("binding", {})
        if cond.get("const") == "federated":
            need = set(clause.get("then", {}).get("required", []))
            fed_ok = {"federated_from", "source_ran_at"} <= need
    if not fed_ok:
        drift.append(
            "cross-rule binding=federated⇒federated_from+source_ran_at: not "
            "found as an allOf if/then in SCH-CLAIM-001 $defs.qualifiers"
        )

    # 9. required claim fields present in the schema
    code_required = {"subject_id", "predicate", "source_id", "recorded_by", "confidence"}
    spec_required = set(claim.get("required", []))
    missing = code_required - spec_required
    if missing:
        drift.append(
            f"required claim fields: code enforces {sorted(code_required)} but "
            f"SCH-CLAIM-001 required is missing {sorted(missing)}"
        )
    return drift


def pairing_diff(root: Path, awen_weave_version: str) -> list[str]:
    """Confirm compatibility.md pairs this constitution version with this
    package's version + SCHEMA_VERSION."""
    text = (root / "compatibility.md").read_text(encoding="utf-8")
    drift: list[str] = []
    row = None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] == CONSTITUTION_VERSION:
                row = cells
                break
    if row is None:
        return [
            f"compatibility.md has no row for constitution {CONSTITUTION_VERSION}"
        ]
    pairs_with, schema_version = row[1], row[2]
    wv_line = ".".join(awen_weave_version.split(".")[:2])  # 0.2
    if not pairs_with.startswith(wv_line):
        drift.append(
            f"pairing: compatibility.md pairs constitution {CONSTITUTION_VERSION} "
            f"with awen-weave {pairs_with!r}, but this package is "
            f"{awen_weave_version!r} (line {wv_line})"
        )
    if schema_version != SCHEMA_VERSION:
        drift.append(
            f"pairing: compatibility.md SCHEMA_VERSION {schema_version!r} != "
            f"package SCHEMA_VERSION {SCHEMA_VERSION!r}"
        )
    return drift


# --------------------------------------------------------------------------
# Layer B — behavioural round-trip
# --------------------------------------------------------------------------
def _registry(schemas: dict[str, dict]):
    from referencing import Registry, Resource

    resources = [(s["$id"], Resource.from_contents(s)) for s in schemas.values()]
    return Registry().with_resources(resources)


def _schema_accepts(schemas, registry, kind: str, document: Any) -> bool:
    from jsonschema import Draft202012Validator

    schema = schemas[kind]
    return not list(Draft202012Validator(schema, registry=registry).iter_errors(document))


def _code_accepts(kind: str, fx: dict) -> bool:
    doc = fx["document"]
    if kind == "claim":
        return validate_claim(
            doc, subject_entity_type=fx.get("subject_entity_type", "building")
        ) == []
    if kind == "entity":
        return validate_entity(
            doc.get("entity_id", ""), doc.get("entity_type", ""), doc.get("visibility")
        ) == []
    raise Setup(f"round-trip corpus has an unroundtrippable kind {kind!r}")


def roundtrip_diff(schemas: dict[str, dict], fixtures: list[dict]) -> list[str]:
    registry = _registry(schemas)
    drift: list[str] = []
    for fx in fixtures:
        kind = fx["kind"]
        code = _code_accepts(kind, fx)
        spec = _schema_accepts(schemas, registry, kind, fx["document"])
        if code != spec:
            drift.append(
                f"round-trip[{fx['id']}]: code accepts={code} but SCH accepts="
                f"{spec} — {fx.get('note', '')}"
            )
    return drift


def load_fixtures(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["fixtures"] if isinstance(data, dict) else data


# --------------------------------------------------------------------------
def run(constitution_dir: Path, fixtures_path: Path | None) -> int:
    try:
        const = load_constitution(constitution_dir)
    except Setup as exc:
        print(f"SETUP ERROR: {exc}", file=sys.stderr)
        return 2

    import importlib.metadata as _md

    try:
        awen_weave_version = _md.version("awen-weave")
    except _md.PackageNotFoundError:
        # editable/uninstalled: read pyproject
        import re

        pt = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', pt, re.MULTILINE)
        awen_weave_version = m.group(1) if m else "0.0.0"

    schemas = const["schemas"]
    findings: list[str] = []
    findings += model_diff(schemas)
    findings += pairing_diff(const["root"], awen_weave_version)

    if fixtures_path is None:
        default = _REPO / "tests" / "schema" / "fixtures" / "constitution_roundtrip.json"
        fixtures_path = default if default.exists() else None
    if fixtures_path and fixtures_path.exists():
        try:
            findings += roundtrip_diff(schemas, load_fixtures(fixtures_path))
        except Setup as exc:
            print(f"SETUP ERROR: {exc}", file=sys.stderr)
            return 2
    else:
        print("note: no round-trip fixtures found; ran model-diff only",
              file=sys.stderr)

    print(
        f"constitution drift check — awen-weave {awen_weave_version} vs "
        f"awen-constitution {const['version']} ({CONSTITUTION_TAG})",
        file=sys.stderr,
    )
    if findings:
        print(f"\nDRIFT DETECTED ({len(findings)}):", file=sys.stderr)
        for f in findings:
            print(f"  ✗ {f}", file=sys.stderr)
        print(
            "\nThe spec leads from constitution 0.2.0: reconcile the code model "
            "to the SCH-* (or bump CONSTITUTION_TAG deliberately with a "
            "compatibility.md row).",
            file=sys.stderr,
        )
        return 1
    print("  ✓ no drift — code model matches the pinned SCH-*", file=sys.stderr)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--constitution",
        type=Path,
        default=Path("_constitution"),
        help="path to an awen-constitution tree checked out at the pinned tag",
    )
    ap.add_argument("--fixtures", type=Path, default=None)
    args = ap.parse_args()
    sys.exit(run(args.constitution, args.fixtures))


if __name__ == "__main__":
    main()
