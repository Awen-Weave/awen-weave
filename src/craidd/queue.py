"""
src/craidd/queue.py — Deliverable C: the async federation request queue.

A plain-directory contract on the tailnet — deliberately just directories and
JSON files so the shape survives every transport hop (Mythic Beasts / TES) with
nothing to break:

    requests/
      inbox/     # consumers drop  <id>.json  (the §6 request schema)
      claimed/   # the builder moves a request here while assembling it
      done/      # moved here once its result has landed in a snapshot (audit)

For S1 the reader is a STUB: it lists and parses inbox items and validates their
shape. Live assembly (claim -> build -> done) is S6 — but the directory contract
and request schema are built NOW so nothing changes later (brief §5).

Request schema (§6):
    { place, nation, wanted_layers[], requested_by, reason, emitted_at }

`emitted_at` is the consumer's own emit time (verify-not-recall applies to
SOURCE run-UTCs, not to a consumer's request timestamp).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

INBOX = "inbox"
CLAIMED = "claimed"
DONE = "done"
_STAGES = (INBOX, CLAIMED, DONE)

# Required keys on a request (brief §6). wanted_layers must be a non-empty list.
_REQUIRED = ("place", "nation", "wanted_layers", "requested_by", "reason",
             "emitted_at")


class QueueError(RuntimeError):
    """Fail-loud for a malformed queue layout or request file."""


@dataclass(frozen=True)
class Request:
    """A parsed inbox request. `raw` keeps the full document; `errors` is empty
    iff the request is well formed against the §6 schema."""

    request_id: str
    path: Path
    raw: dict
    errors: list

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_request(doc) -> list:
    """Return a list of problems with a request document (empty == valid).

    Pure/offline — the §6 shape gate. Not a constitution SCH-* (a request is a
    transport envelope, not a governed record), so it is checked here."""
    problems: list = []
    if not isinstance(doc, dict):
        return ["request must be a JSON object"]
    for key in _REQUIRED:
        if key not in doc:
            problems.append(f"missing required key '{key}'")
    layers = doc.get("wanted_layers")
    if layers is not None:
        if not isinstance(layers, list) or not layers:
            problems.append("'wanted_layers' must be a non-empty list")
        elif not all(isinstance(x, str) and x.strip() for x in layers):
            problems.append("'wanted_layers' entries must be non-empty strings")
    for key in ("place", "nation", "requested_by", "reason", "emitted_at"):
        val = doc.get(key)
        if key in doc and (not isinstance(val, str) or not val.strip()):
            problems.append(f"'{key}' must be a non-empty string")
    return problems


class RequestQueue:
    """The directory contract + the S1 reader stub.

    `ensure()` creates the three stage directories (idempotent). `read_inbox()`
    lists and parses every `<id>.json` in inbox. `claim()` / `mark_done()` move
    a request between stages — wired now so S6 assembly is a drop-in."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def stage_dir(self, stage: str) -> Path:
        if stage not in _STAGES:
            raise QueueError(f"unknown stage {stage!r}; expected one of {_STAGES}")
        return self.root / stage

    def ensure(self) -> Path:
        """Create requests/{inbox,claimed,done}. Idempotent."""
        for stage in _STAGES:
            (self.root / stage).mkdir(parents=True, exist_ok=True)
        return self.root

    def read_inbox(self) -> list:
        """Parse every request in inbox (sorted by id for determinism). A
        malformed JSON file becomes a Request with a parse error rather than
        crashing the whole read — the caller decides what to do with it."""
        inbox = self.root / INBOX
        if not inbox.is_dir():
            return []
        out: list = []
        for path in sorted(inbox.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                out.append(Request(path.stem, path, {}, [f"unreadable: {exc}"]))
                continue
            out.append(Request(path.stem, path, doc if isinstance(doc, dict) else {},
                               validate_request(doc)))
        return out

    def _move(self, request_id: str, src: str, dst: str) -> Path:
        src_path = self.stage_dir(src) / f"{request_id}.json"
        if not src_path.is_file():
            raise QueueError(f"request {request_id!r} not in {src}")
        self.stage_dir(dst).mkdir(parents=True, exist_ok=True)
        dst_path = self.stage_dir(dst) / f"{request_id}.json"
        src_path.replace(dst_path)
        return dst_path

    def claim(self, request_id: str) -> Path:
        """Move a request inbox -> claimed (builder is assembling it)."""
        return self._move(request_id, INBOX, CLAIMED)

    def mark_done(self, request_id: str) -> Path:
        """Move a request claimed -> done (its result landed in a snapshot)."""
        return self._move(request_id, CLAIMED, DONE)


def write_request(root: Path, request_id: str, doc: dict) -> Path:
    """Helper for a consumer (or a test) to drop a request into inbox.

    Fail-loud: refuses to write a request that doesn't satisfy the §6 shape, so
    a malformed request never enters the queue."""
    problems = validate_request(doc)
    if problems:
        raise QueueError(
            f"refusing to enqueue malformed request {request_id!r}: "
            f"{'; '.join(problems)}"
        )
    queue = RequestQueue(root)
    queue.ensure()
    path = queue.stage_dir(INBOX) / f"{request_id}.json"
    path.write_text(
        json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
