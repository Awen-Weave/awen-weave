"""
src/craidd/validation_gate.py — the build-time constitution.validate gate.

The federation spine (S1) validates EVERY record it materialises before it is
written into a snapshot (CHI lesson 1: validate at build, fail loud, hard-stop
on schema drift). This module is the single seam through which a snapshot
builder reaches the constitution's Tier-1 schemas (SCH-PLACEANCHOR-001,
SCH-CLAIM-001, SCH-FEDERATION-001, SCH-ENTITY-001).

Two backends, one `Validator` protocol:

  - `PorthValidator` — the canonical live gate. Calls the `constitution.validate`
    / `constitution.version` MCP tools on awen-porth (craidd :8081). This is the
    gate the real build runs on craidd, where porth is a sibling service.
  - `SchemaValidator` — the offline gate. Validates against the constitution
    schemas vendored at their pinned machine-layer tag (constitution_vendor/,
    see PINNED.json). CI and off-tailnet runs use this so the check never needs
    the network — exactly the split awen-source-catalogue already runs.

`default_gate()` prefers porth when it is reachable and falls back to the
vendored schemas, so the same builder code is faithful on craidd and testable
on a dev Mac. Both backends answer the same question — is this document clean
against the constitution it pins? — and return the same `ValidationResult`.

The pinned machine layer moves only when the constitution's SCH-*/VOC-*/POL-*
change (PINNED.json), so the vendored offline schemas agree with the live porth
gate on every Tier-1 fixture; where they could ever drift, the live gate wins
(that is why the manifest pin is read live — see snapshot.py / brief §8).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# Where the machine-layer schemas are vendored inside this package.
_VENDOR_DIR = Path(__file__).resolve().parent / "constitution_vendor"
_SCHEMA_DIR = _VENDOR_DIR / "schema"

# Canonical kind -> vendored schema filename. Mirrors the porth `kind`
# vocabulary and awen-source-catalogue's map so the offline and live gates
# accept the same names.
KIND_TO_FILE = {
    "claim": "claim.schema.json",
    "entity": "entity.schema.json",
    "proposal-envelope": "proposal-envelope.schema.json",
    "place-anchor": "place-anchor.schema.json",
    "use-case-declaration": "use-case-declaration.schema.json",
    "federation-stamp": "federation-stamp.schema.json",
}

# Rule-id / Welsh aliases -> canonical kind (accepted by both gates).
_ALIASES = {
    "sch-claim-001": "claim", "honiad": "claim",
    "sch-entity-001": "entity", "endid": "entity",
    "sch-envelope-001": "proposal-envelope",
    "sch-placeanchor-001": "place-anchor",
    "sch-usecase-001": "use-case-declaration",
    "sch-federation-001": "federation-stamp",
}


class UnknownKindError(ValueError):
    """Raised for a kind that maps to no known Tier-1 schema (fail-loud)."""


class ValidationGateError(RuntimeError):
    """A gate could not reach or complete validation (transport / protocol)."""


@dataclass(frozen=True)
class ValidationResult:
    """The uniform answer both gates return. `valid` is the whole verdict;
    `violations` are human-readable strings (empty iff valid)."""

    kind: str
    valid: bool
    violations: list
    constitution_version: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "valid": self.valid,
            "violations": list(self.violations),
            "constitution_version": self.constitution_version,
        }


@dataclass(frozen=True)
class ConstitutionPin:
    """The constitution version a snapshot was minted under. Read LIVE from
    porth at build time (brief §8) so a consumer can refuse a snapshot minted
    under a version it doesn't accept; the vendored pin is only the offline
    fallback, marked `source='vendored'`."""

    constitution_version: str
    constitution_tag: str
    constitution_commit: Optional[str]
    source: str  # "porth" (live) | "vendored" (offline fallback)

    def to_manifest_pins(self, awen_weave_version: str) -> dict:
        return {
            "constitution_version": self.constitution_version,
            "constitution_tag": self.constitution_tag,
            "awen_weave": awen_weave_version,
        }


def resolve_kind(kind: str) -> str:
    """Map a kind / rule-id / Welsh alias to a canonical kind. Fail-loud."""
    key = kind.strip().lower()
    if key in KIND_TO_FILE:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    raise UnknownKindError(
        f"unknown kind {kind!r}; known kinds: {', '.join(sorted(KIND_TO_FILE))}"
    )


def vendored_pin() -> ConstitutionPin:
    """The machine-layer pin vendored in this package (PINNED.json). The
    offline fallback for the manifest when porth is unreachable."""
    data = json.loads((_VENDOR_DIR / "PINNED.json").read_text(encoding="utf-8"))
    tag = data.get("tag", "")
    # tag is like "v0.1.0"; the constitution_version is the tag without the v.
    version = tag[1:] if tag.startswith("v") else tag
    return ConstitutionPin(
        constitution_version=version,
        constitution_tag=tag,
        constitution_commit=data.get("commit"),
        source="vendored",
    )


# --- offline gate ------------------------------------------------------------

@lru_cache(maxsize=1)
def _registry():
    from jsonschema import Draft202012Validator  # noqa: F401 — ensure dep present
    from referencing import Registry, Resource
    resources = []
    for path in sorted(_SCHEMA_DIR.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def _offline_validator(kind: str):
    from jsonschema import Draft202012Validator
    schema = json.loads(
        (_SCHEMA_DIR / KIND_TO_FILE[kind]).read_text(encoding="utf-8")
    )
    return Draft202012Validator(schema, registry=_registry())


class SchemaValidator:
    """Offline gate: validate against the vendored machine-layer schemas.

    Same schemas, same pinned tag as the live porth gate; needs no network.
    Used by CI, unit tests, and any off-tailnet build.
    """

    backend = "vendored"

    def __init__(self):
        self._pin = vendored_pin()

    def pin(self) -> ConstitutionPin:
        return self._pin

    def validate(self, kind: str, document: Any) -> ValidationResult:
        canonical = resolve_kind(kind)
        if not isinstance(document, dict):
            return ValidationResult(
                canonical, False, ["document must be a JSON object"],
                self._pin.constitution_version,
            )
        errors = sorted(
            _offline_validator(canonical).iter_errors(document),
            key=lambda e: (list(e.absolute_path), e.message),
        )
        violations = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        ]
        return ValidationResult(
            canonical, not violations, violations,
            self._pin.constitution_version,
        )


# --- live gate (awen-porth MCP) ---------------------------------------------

# The awen-porth streamable-HTTP MCP endpoint on craidd's tailnet. Overridable
# for a different node / port.
DEFAULT_PORTH_URL = "http://100.68.238.84:8081/mcp"


class PorthValidator:
    """Live gate: the `constitution.validate` MCP tool on awen-porth.

    The canonical build-time gate the real snapshot build runs on craidd, where
    porth is a sibling on :8081. Speaks the streamable-HTTP MCP transport
    (initialize -> session id -> tools/call); responses arrive as SSE frames.
    """

    backend = "porth"

    def __init__(self, url: str = DEFAULT_PORTH_URL, timeout: float = 15.0):
        self.url = url
        self.timeout = timeout
        self._session = None  # requests.Session, lazily opened
        self._sid = None

    # -- MCP plumbing --------------------------------------------------------
    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._sid:
            h["Mcp-Session-Id"] = self._sid
        return h

    @staticmethod
    def _parse(text: str) -> list:
        """Parse a streamable-HTTP reply: either SSE `data:` frames or a plain
        JSON body."""
        frames = [
            json.loads(line[5:].strip())
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        if frames:
            return frames
        text = text.strip()
        return [json.loads(text)] if text.startswith("{") else []

    def _ensure_session(self):
        if self._session is not None:
            return
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise ValidationGateError(
                "PorthValidator needs `requests`; install it or use SchemaValidator"
            ) from exc
        s = requests.Session()
        init = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "awen-weave-snapshot", "version": "0.2.0"},
            },
        }
        try:
            r = s.post(self.url, headers=self._headers(), json=init,
                       timeout=self.timeout)
            r.raise_for_status()
        except Exception as exc:
            raise ValidationGateError(f"porth initialize failed: {exc}") from exc
        self._sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
        self._session = s
        # Complete the handshake.
        s.post(self.url, headers=self._headers(),
               json={"jsonrpc": "2.0", "method": "notifications/initialized"},
               timeout=self.timeout)

    def _call_tool(self, name: str, arguments: dict) -> dict:
        self._ensure_session()
        payload = {
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        try:
            r = self._session.post(self.url, headers=self._headers(),
                                   json=payload, timeout=self.timeout)
            r.raise_for_status()
        except Exception as exc:
            raise ValidationGateError(f"porth {name} call failed: {exc}") from exc
        frames = self._parse(r.text)
        if not frames:
            raise ValidationGateError(f"porth {name}: empty reply")
        result = frames[-1].get("result")
        if result is None:
            raise ValidationGateError(
                f"porth {name} error: {frames[-1].get('error')}"
            )
        # Prefer structuredContent; fall back to parsing the text content.
        if "structuredContent" in result:
            return result["structuredContent"]
        for item in result.get("content", []):
            if item.get("type") == "text":
                return json.loads(item["text"])
        raise ValidationGateError(f"porth {name}: no parseable content")

    # -- gate API ------------------------------------------------------------
    def validate(self, kind: str, document: Any) -> ValidationResult:
        canonical = resolve_kind(kind)
        out = self._call_tool(
            "constitution.validate", {"kind": canonical, "document": document}
        )
        raw = out.get("violations", [])
        violations = [
            v if isinstance(v, str)
            else f"{v.get('path', '<root>')}: {v.get('message', v)}"
            for v in raw
        ]
        return ValidationResult(
            out.get("kind", canonical),
            bool(out.get("valid", False)),
            violations,
            out.get("constitution_version"),
        )

    def pin(self) -> ConstitutionPin:
        out = self._call_tool("constitution.version", {})
        pinned = out.get("pinned", {})
        return ConstitutionPin(
            constitution_version=out.get("constitution_version", ""),
            constitution_tag=pinned.get("tag", ""),
            constitution_commit=pinned.get("commit"),
            source="porth",
        )

    def reachable(self) -> bool:
        try:
            self._ensure_session()
            return True
        except ValidationGateError:
            return False


# --- selector ----------------------------------------------------------------

def default_gate(porth_url: str = DEFAULT_PORTH_URL, prefer_porth: bool = True):
    """Return the gate the build should use: the live porth gate when it is
    reachable, else the offline vendored gate. The real craidd build gets porth;
    a dev Mac / CI run off-tailnet gets the vendored schemas. Both validate the
    same records against the same pinned constitution machine layer."""
    if prefer_porth:
        candidate = PorthValidator(porth_url)
        if candidate.reachable():
            return candidate
    return SchemaValidator()
