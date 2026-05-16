"""
Smoke + contract tests for client/craidd_client.py::propose_entity and
propose_bundle.

Covers the contract documented in design/entity-proposal-shape.md §6 and
implemented per cowork-to-code-implement-propose-entity-and-bundle.md:

  - propose_entity happy paths (minimal, full, note shorthand)
  - propose_entity error paths (invalid entity_type / names /
    external_refs / qualifiers / cross-qualifier rule)
  - propose_bundle happy paths (EP + 1 claim, EP + N claims,
    field_session_id propagation)
  - propose_bundle atomicity: validation-failure → no files;
    disk-error-mid-rename → partial state visible via shared bundle_id
  - ID format pinning for _new_ep_id / _new_bundle_id

Pure-function tests where possible; filesystem-touching tests use the
pytest tmp_path fixture and a fresh Craidd instance per test.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Both src/ and client/ on the path so the imports below resolve in tests
# the same way they do at runtime (pytest.ini adds src and client).
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "client"))

from craidd_client import (  # noqa: E402 — sys.path inserted above
    Craidd,
    _new_bundle_id,
    _new_ep_id,
)
from datetime import datetime, timezone  # noqa: E402


# Regexes the validator enforces — pinned here too so tests catch any
# drift between client-side ID generation and schema-side validation.
EP_ID_RE = re.compile(r"^EP-\d{8}-\d{4}-[0-9a-fA-F]{8}$")
BUNDLE_ID_RE = re.compile(r"^B-\d{8}-\d{4}-[0-9a-fA-F]{8}$")


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path) -> Craidd:
    """A Craidd client writing to tmp_path. Bypasses the default
    energy-study proposals-out location."""
    return Craidd(repo_root=tmp_path, proposals_out=tmp_path / "proposals")


def _ep_kwargs() -> dict:
    """Minimal-but-valid propose_entity kwargs."""
    return {
        "submitter": "huw@arloesidolgellau.com",
        "entity_type": "building",
        "names": [
            {
                "value": "Tŷ Newyddion",
                "language": "cy",
                "name_type": "current_local",
            },
        ],
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
    }


# --- ID format pinning ------------------------------------------------------

def test_new_ep_id_matches_regex():
    """100 generated EP ids all match the strict regex the validator enforces."""
    now = datetime.now(timezone.utc)
    for _ in range(100):
        assert EP_ID_RE.match(_new_ep_id(now)) is not None


def test_new_bundle_id_matches_regex():
    now = datetime.now(timezone.utc)
    for _ in range(100):
        assert BUNDLE_ID_RE.match(_new_bundle_id(now)) is not None


def test_two_ids_at_same_minute_have_different_hex_suffixes():
    """Uniqueness within a minute — the uuid4 suffix guarantees this."""
    fixed_now = datetime(2026, 5, 16, 14, 30, tzinfo=timezone.utc)
    ids = {_new_ep_id(fixed_now) for _ in range(10)}
    assert len(ids) == 10


# --- propose_entity happy paths ---------------------------------------------

def test_propose_entity_minimal(client: Craidd):
    ep_id = client.propose_entity(**_ep_kwargs())
    assert EP_ID_RE.match(ep_id) is not None
    file = client.proposals_out / f"{ep_id}.json"
    assert file.is_file()
    payload = json.loads(file.read_text())
    assert payload["proposal_type"] == "entity"
    assert payload["proposal_id"] == ep_id
    assert payload["entity"]["entity_type"] == "building"
    assert payload["entity"]["names"][0]["value"] == "Tŷ Newyddion"
    assert payload["confidence"] == "high"  # default


def test_propose_entity_full_options(client: Craidd):
    ep_id = client.propose_entity(
        submitter="huw@arloesidolgellau.com",
        entity_type="building",
        names=[
            {"value": "Tŷ Newyddion", "language": "cy",
             "name_type": "current_local"},
            {"value": "Ty Newyddion", "language": "en",
             "name_type": "current_local"},
        ],
        source={"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
        note={"cy": "nodyn Cymraeg", "en": "english note"},
        confidence="medium",
        address_text="Bridge Street, Dolgellau",
        external_refs=[
            {"scheme": "uprn", "value": "200003184697"},
            {"scheme": "cadw", "value": "4938"},
        ],
        qualifiers={"verification_method": "on-site"},
        field_session_id="FS-20260516-bridge-street-walk",
        bundle_id="B-20260516-1015-9c4d2b78",
    )
    file = client.proposals_out / f"{ep_id}.json"
    payload = json.loads(file.read_text())
    assert payload["entity"]["address_text"] == "Bridge Street, Dolgellau"
    assert len(payload["entity"]["external_refs"]) == 2
    assert payload["entity"]["names"][1]["language"] == "en"
    assert payload["note"] == {"cy": "nodyn Cymraeg", "en": "english note"}
    assert payload["field_session_id"] == "FS-20260516-bridge-street-walk"
    assert payload["bundle_id"] == "B-20260516-1015-9c4d2b78"
    assert payload["qualifiers"]["verification_method"] == "on-site"


def test_propose_entity_note_string_shorthand(client: Craidd):
    """Passing a string for `note` becomes {"en": <str>} in the file."""
    ep_id = client.propose_entity(
        **{**_ep_kwargs(), "note": "building newly identified"}
    )
    payload = json.loads((client.proposals_out / f"{ep_id}.json").read_text())
    assert payload["note"] == {"en": "building newly identified"}


def test_propose_entity_omits_optional_fields_when_absent(client: Craidd):
    """The file shape should match the schema doc's worked examples —
    no null clutter for unsupplied optionals."""
    ep_id = client.propose_entity(**_ep_kwargs())
    payload = json.loads((client.proposals_out / f"{ep_id}.json").read_text())
    assert "field_session_id" not in payload
    assert "bundle_id" not in payload
    assert "note" not in payload
    assert "address_text" not in payload["entity"]
    assert "external_refs" not in payload["entity"]


# --- propose_entity error paths ---------------------------------------------

def _assert_no_ep_files(client: Craidd) -> None:
    """No EP-*.json files in proposals_out — the propose_entity call
    must have raised before writing."""
    assert list(client.proposals_out.glob("EP-*.json")) == []


def test_propose_entity_invalid_entity_type_raises(client: Craidd):
    kwargs = _ep_kwargs()
    kwargs["entity_type"] = "monument"  # v0.3 type, not yet enabled
    with pytest.raises(ValueError, match="entity_type"):
        client.propose_entity(**kwargs)
    _assert_no_ep_files(client)


def test_propose_entity_empty_names_raises(client: Craidd):
    kwargs = _ep_kwargs()
    kwargs["names"] = []
    with pytest.raises(ValueError, match="names"):
        client.propose_entity(**kwargs)
    _assert_no_ep_files(client)


def test_propose_entity_invalid_external_ref_scheme_raises(client: Craidd):
    kwargs = _ep_kwargs()
    kwargs["external_refs"] = [{"scheme": "loqate", "value": "x"}]
    with pytest.raises(ValueError, match="scheme"):
        client.propose_entity(**kwargs)
    _assert_no_ep_files(client)


def test_propose_entity_malformed_uprn_raises(client: Craidd):
    kwargs = _ep_kwargs()
    kwargs["external_refs"] = [{"scheme": "uprn", "value": "12"}]
    with pytest.raises(ValueError):
        client.propose_entity(**kwargs)
    _assert_no_ep_files(client)


def test_propose_entity_closed_qualifier_outside_set_raises(client: Craidd):
    kwargs = _ep_kwargs()
    kwargs["qualifiers"] = {"verification_method": "ouija-board"}
    with pytest.raises(ValueError, match="verification_method"):
        client.propose_entity(**kwargs)
    _assert_no_ep_files(client)


def test_propose_entity_cosign_without_session_raises(client: Craidd):
    """The cross-qualifier rule from design/lleolydd.md §12.A —
    co_signed_by requires field_session_id."""
    kwargs = _ep_kwargs()
    kwargs["qualifiers"] = {"co_signed_by": "richard@arloesidolgellau.com"}
    with pytest.raises(ValueError, match="co_signed_by"):
        client.propose_entity(**kwargs)
    _assert_no_ep_files(client)


# --- propose_bundle happy paths ---------------------------------------------

def _bundle_args(claim_count: int = 1) -> dict:
    """Minimal-but-valid propose_bundle kwargs producing 1+claim_count
    proposals total."""
    claim_specs = [
        {
            "predicate": "floor_area_m2",
            "value": 142.6 + i,
            "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
            "confidence": "medium",
        }
        for i in range(claim_count)
    ]
    return {
        "submitter": "huw@arloesidolgellau.com",
        "entity_proposal": {
            "entity_type": "building",
            "names": [
                {"value": "Test Building", "language": "en",
                 "name_type": "current_local"},
            ],
            "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
        },
        "claim_proposals": claim_specs,
    }


def test_propose_bundle_ep_plus_one_claim(client: Craidd):
    bundle_id = client.propose_bundle(**_bundle_args(claim_count=1))
    assert BUNDLE_ID_RE.match(bundle_id) is not None

    ep_files = sorted(client.proposals_out.glob("EP-*.json"))
    claim_files = sorted(client.proposals_out.glob("P-*.json"))
    assert len(ep_files) == 1
    assert len(claim_files) == 1

    ep = json.loads(ep_files[0].read_text())
    claim = json.loads(claim_files[0].read_text())
    assert ep["bundle_id"] == bundle_id
    assert claim["bundle_id"] == bundle_id
    # Claim's subject_hint sentinel + None subject per
    # entity-proposal-shape.md §5
    assert claim["subject_hint"] == "<bundle>"
    assert claim["subject"] is None


def test_propose_bundle_ep_plus_three_claims(client: Craidd):
    args = _bundle_args(claim_count=3)
    bundle_id = client.propose_bundle(**args)
    files = sorted(client.proposals_out.glob("*.json"))
    assert len(files) == 4
    for f in files:
        payload = json.loads(f.read_text())
        assert payload["bundle_id"] == bundle_id


def test_propose_bundle_field_session_id_propagates(client: Craidd):
    args = _bundle_args(claim_count=2)
    args["field_session_id"] = "FS-20260516-bridge-street-walk"
    bundle_id = client.propose_bundle(**args)

    ep = json.loads(next(client.proposals_out.glob("EP-*.json")).read_text())
    assert ep["field_session_id"] == "FS-20260516-bridge-street-walk"
    # Claims pick up the session id in their qualifiers
    for claim_file in client.proposals_out.glob("P-*.json"):
        claim = json.loads(claim_file.read_text())
        assert claim["bundle_id"] == bundle_id
        assert (
            claim["qualifiers"]["field_session_id"]
            == "FS-20260516-bridge-street-walk"
        )


# --- propose_bundle atomicity -----------------------------------------------

def test_propose_bundle_validation_failure_in_ep_writes_nothing(
    client: Craidd,
):
    """Bundle EP fails validation → no files at all."""
    args = _bundle_args(claim_count=1)
    args["entity_proposal"]["entity_type"] = "monument"  # not v0.1
    with pytest.raises(ValueError):
        client.propose_bundle(**args)
    assert list(client.proposals_out.glob("EP-*.json")) == []
    assert list(client.proposals_out.glob("P-*.json")) == []


def test_propose_bundle_validation_failure_in_claim_writes_nothing(
    client: Craidd,
):
    """Bundle claim fails validation → no files at all, even though the
    EP would have validated standalone."""
    args = _bundle_args(claim_count=1)
    args["claim_proposals"][0]["predicate"] = "not_a_real_predicate"
    with pytest.raises(ValueError):
        client.propose_bundle(**args)
    assert list(client.proposals_out.glob("EP-*.json")) == []
    assert list(client.proposals_out.glob("P-*.json")) == []


def test_propose_bundle_validation_failure_reports_per_proposal(
    client: Craidd,
):
    """Errors carry the offending proposal's id + role for diagnostics."""
    args = _bundle_args(claim_count=2)
    args["claim_proposals"][1]["predicate"] = "not_a_real_predicate"
    with pytest.raises(ValueError) as excinfo:
        client.propose_bundle(**args)
    msg = str(excinfo.value)
    assert "claim[1]" in msg
    assert "not_a_real_predicate" in msg


def test_propose_bundle_disk_error_mid_rename_pins_partial_state(
    client: Craidd, monkeypatch: pytest.MonkeyPatch,
):
    """All-pass-validation, simulate a disk error on the second os.rename.
    The contract: bundle is atomic against *validation* errors, NOT against
    disk errors — the first proposal (the EP) has already landed when the
    second rename fails. craidd-review detects partial state via the
    shared bundle_id.

    This is the load-bearing test for the brief's §5.4 contract pin."""
    import os as _os
    rename_calls: list[tuple[str, str]] = []
    real_rename = _os.rename

    def flaky_rename(src, dst):  # noqa: ANN001 — match os.rename signature
        rename_calls.append((str(src), str(dst)))
        if len(rename_calls) >= 2:
            raise OSError("simulated disk failure on second rename")
        real_rename(src, dst)

    monkeypatch.setattr("craidd_client.os.rename", flaky_rename)

    args = _bundle_args(claim_count=1)
    with pytest.raises(OSError, match="simulated disk failure"):
        client.propose_bundle(**args)

    # The EP (first in the rename order) landed; the claim did not.
    ep_files = list(client.proposals_out.glob("EP-*.json"))
    claim_files = list(client.proposals_out.glob("P-*.json"))
    assert len(ep_files) == 1, "EP should have renamed before failure"
    assert len(claim_files) == 0, "claim's rename failed"

    # Bundle id is consistent on what did land — craidd-review can
    # identify the partial state by querying for this bundle_id.
    ep = json.loads(ep_files[0].read_text())
    assert "bundle_id" in ep and BUNDLE_ID_RE.match(ep["bundle_id"])


def test_propose_bundle_temp_files_cleaned_when_no_rename_succeeds(
    client: Craidd, monkeypatch: pytest.MonkeyPatch,
):
    """If the first rename fails outright, the remaining temp files
    should be unlinked. No .tmp leftovers in the proposals dir."""
    import os as _os

    def always_failing_rename(src, dst):  # noqa: ANN001
        raise OSError("rename always fails")

    monkeypatch.setattr("craidd_client.os.rename", always_failing_rename)

    args = _bundle_args(claim_count=2)
    with pytest.raises(OSError):
        client.propose_bundle(**args)

    tmp_files = list(client.proposals_out.glob("*.tmp"))
    assert tmp_files == [], (
        f"temp files should have been cleaned up; found {tmp_files}"
    )
    json_files = list(client.proposals_out.glob("*.json"))
    assert json_files == []


# --- atomic write check for propose_entity ----------------------------------

def test_propose_entity_leaves_no_temp_files_on_success(client: Craidd):
    """The atomic-write helper renames temp → final; no .tmp leftovers."""
    client.propose_entity(**_ep_kwargs())
    assert list(client.proposals_out.glob("*.tmp")) == []


def test_propose_entity_leaves_no_temp_files_on_validation_failure(
    client: Craidd,
):
    """Validation rejects before any temp is written, so no .tmp residue."""
    kwargs = _ep_kwargs()
    kwargs["entity_type"] = "monument"
    with pytest.raises(ValueError):
        client.propose_entity(**kwargs)
    assert list(client.proposals_out.glob("*.tmp")) == []
    assert list(client.proposals_out.glob("EP-*.json")) == []


# --- list_pending_entity_proposals ------------------------------------------

def test_list_pending_entity_proposals_returns_only_ep_files(client: Craidd):
    """The new convenience accessor must not muddle EP-*.json with
    P-*.json (list_pending_proposals already covers the latter)."""
    # Mix some entity proposals and one claim
    client.propose_entity(**_ep_kwargs())
    client.propose_entity(**_ep_kwargs())
    client.propose_bundle(**_bundle_args(claim_count=1))

    eps = client.list_pending_entity_proposals()
    claims = client.list_pending_proposals()
    assert all(f.name.startswith("EP-") for f in eps)
    assert all(f.name.startswith("P-") for f in claims)
    assert len(eps) == 3   # 2 standalone + 1 from the bundle
    assert len(claims) == 1
