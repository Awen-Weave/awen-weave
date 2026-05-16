"""
Smoke tests for src/cli/craidd_propose.py.

The CLI assembles a proposal from flags or a file, validates it against
the schema layer (validate_proposal), and writes a JSON file into
<data-dir>/proposals/. Tests run main() in-process against a temp dir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def craidd_propose():
    from cli import craidd_propose as mod  # type: ignore[import-not-found]
    return mod.main


def test_propose_from_flags_writes_proposal_file(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "floor_area_m2",
        "--value", "142.6",
        "--source-id", "TDS-DOL-SRC-DOL-ENERGY-2026",
        "--confidence", "medium",
        "--note", "smoke test",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("*.json"))
    assert len(proposals) == 1
    payload = json.loads(proposals[0].read_text())
    assert payload["subject"] == "TDS-DOL-B-00001"
    assert payload["predicate"] == "floor_area_m2"
    assert payload["value"] == 142.6
    assert payload["submitter"] == "test"


def test_propose_dry_run_writes_nothing(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "floor_area_m2",
        "--value", "142.6",
        "--source-id", "TDS-DOL-SRC-DOL-ENERGY-2026",
        "--confidence", "medium",
        "--dry-run",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    assert not (tmp_path / "proposals").exists() or not list(
        (tmp_path / "proposals").glob("*.json")
    )


def test_propose_invalid_predicate_exits_nonzero(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "not_a_real_predicate",
        "--value", "anything",
        "--source-id", "TDS-DOL-SRC-LOCAL",
        "--confidence", "medium",
        "--actor", "test",
    ])
    assert code == 1
    assert not (tmp_path / "proposals").exists() or not list(
        (tmp_path / "proposals").glob("*.json")
    )


def test_propose_from_file_round_trip(
    tmp_path: Path, craidd_propose, capsys,
):
    """A JSON file proposal should be loaded, restamped, validated, and
    written. The CLI overrides submitter and timestamp from the file with
    the --actor / current time."""
    src = tmp_path / "input.json"
    src.write_text(json.dumps({
        "subject": "TDS-DOL-B-00001",
        "predicate": "build_year",
        "value": 1890,
        "source": {"id": "TDS-DOL-SRC-LOCAL"},
        "confidence": "high",
    }))
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--from-file", str(src),
        "--actor", "test-curator",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("*.json"))
    assert len(proposals) == 1
    payload = json.loads(proposals[0].read_text())
    assert payload["predicate"] == "build_year"
    assert payload["value"] == 1890
    assert payload["submitter"] == "test-curator"


def test_propose_bilingual_value_via_flags(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "address",
        "--value-cy", "Stryd y Bont",
        "--value-en", "Bridge Street",
        "--source-id", "TDS-DOL-SRC-LOCAL",
        "--confidence", "high",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("*.json"))
    assert len(proposals) == 1
    payload = json.loads(proposals[0].read_text())
    assert payload["value"] == {"cy": "Stryd y Bont", "en": "Bridge Street"}


# --- entity-mode tests (--entity flag, added 2026-05-16) ---------------------

import re  # noqa: E402

EP_ID_RE = re.compile(r"^EP-\d{8}-\d{4}-[0-9a-fA-F]{8}$")
BUNDLE_ID_RE = re.compile(r"^B-\d{8}-\d{4}-[0-9a-fA-F]{8}$")


def test_entity_flag_driven_writes_ep_file(
    tmp_path: Path, craidd_propose, capsys,
):
    """Flag-driven entity mode: minimal building entity with one cy name."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-LLEOLYDD-TEST",
        "--confidence", "high",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    proposals = list((tmp_path / "proposals").glob("EP-*.json"))
    assert len(proposals) == 1
    assert EP_ID_RE.match(proposals[0].stem) is not None
    payload = json.loads(proposals[0].read_text())
    assert payload["proposal_type"] == "entity"
    assert payload["entity"]["entity_type"] == "building"
    assert payload["entity"]["names"] == [
        {"value": "Tŷ Newyddion", "language": "cy",
         "name_type": "current_local"},
    ]
    assert payload["source"] == {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"}


def test_entity_flag_driven_multiple_names(
    tmp_path: Path, craidd_propose, capsys,
):
    """Two cy names + one en name, paired correctly with their name_types."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--name-cy", "Adeilad Glyndwr",
        "--name-cy-type", "historic",
        "--name-en", "Glyndwr Buildings",
        "--name-en-type", "historic",
        "--source-id", "TDS-DOL-SRC-LLEOLYDD-TEST",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    ep = json.loads(
        next((tmp_path / "proposals").glob("EP-*.json")).read_text()
    )
    assert len(ep["entity"]["names"]) == 3
    assert {n["value"] for n in ep["entity"]["names"]} == {
        "Tŷ Newyddion", "Adeilad Glyndwr", "Glyndwr Buildings",
    }


def test_entity_flag_external_refs(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-LLEOLYDD-TEST",
        "--external-ref", "uprn:200003184697",
        "--external-ref", "cadw:4938",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    ep = json.loads(
        next((tmp_path / "proposals").glob("EP-*.json")).read_text()
    )
    refs = ep["entity"]["external_refs"]
    assert refs == [
        {"scheme": "uprn", "value": "200003184697"},
        {"scheme": "cadw", "value": "4938"},
    ]


def test_entity_flag_address_text_and_note(
    tmp_path: Path, craidd_propose, capsys,
):
    """The --address-text and --note (shared with claim mode) flags both
    propagate into the entity proposal."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-LLEOLYDD-TEST",
        "--address-text", "Bridge Street, Dolgellau",
        "--note", "building newly identified",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    ep = json.loads(
        next((tmp_path / "proposals").glob("EP-*.json")).read_text()
    )
    assert ep["entity"]["address_text"] == "Bridge Street, Dolgellau"
    # propose_entity normalises a string note into {"en": <str>}
    assert ep["note"] == {"en": "building newly identified"}


def test_entity_from_file_flat_shape(
    tmp_path: Path, craidd_propose, capsys,
):
    """--from-file with flat kwargs shape (entity_type at top level)."""
    src = tmp_path / "ep.json"
    src.write_text(json.dumps({
        "entity_type": "building",
        "names": [
            {"value": "Tŷ Newyddion", "language": "cy",
             "name_type": "current_local"},
        ],
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
        "confidence": "high",
    }))
    code = craidd_propose([
        "--entity",
        "--from-file", str(src),
        "--data-dir", str(tmp_path),
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    eps = list((tmp_path / "proposals").glob("EP-*.json"))
    assert len(eps) == 1


def test_entity_from_file_nested_shape(
    tmp_path: Path, craidd_propose, capsys,
):
    """--from-file with the nested shape that propose_entity itself writes
    (`entity` block + top-level source/confidence). Curators can edit a
    queued proposal and re-submit through this path."""
    src = tmp_path / "ep.json"
    src.write_text(json.dumps({
        "entity": {
            "entity_type": "building",
            "names": [
                {"value": "Tŷ Newyddion", "language": "cy",
                 "name_type": "current_local"},
            ],
            "address_text": "Bridge Street",
        },
        "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
        "confidence": "medium",
    }))
    code = craidd_propose([
        "--entity",
        "--from-file", str(src),
        "--data-dir", str(tmp_path),
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    ep = json.loads(
        next((tmp_path / "proposals").glob("EP-*.json")).read_text()
    )
    assert ep["entity"]["address_text"] == "Bridge Street"
    assert ep["confidence"] == "medium"


def test_entity_from_file_bundle_shape_routes_to_propose_bundle(
    tmp_path: Path, craidd_propose, capsys,
):
    """A --from-file file with both entity_proposal and claim_proposals
    keys routes to propose_bundle. All output files share a bundle_id."""
    src = tmp_path / "bundle.json"
    src.write_text(json.dumps({
        "entity_proposal": {
            "entity_type": "building",
            "names": [
                {"value": "Tŷ Newyddion", "language": "cy",
                 "name_type": "current_local"},
            ],
            "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
            "address_text": "Bridge Street, Dolgellau",
        },
        "claim_proposals": [
            {"predicate": "floor_area_m2", "value": 142.6,
             "source": {"id": "TDS-DOL-SRC-LLEOLYDD-TEST"},
             "confidence": "medium"},
            {"predicate": "build_year", "value": 1885,
             "source": {"id": "TDS-DOL-SRC-LOCAL"},
             "confidence": "high"},
        ],
    }))
    code = craidd_propose([
        "--entity",
        "--from-file", str(src),
        "--data-dir", str(tmp_path),
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    eps = list((tmp_path / "proposals").glob("EP-*.json"))
    claims = list((tmp_path / "proposals").glob("P-*.json"))
    assert len(eps) == 1
    assert len(claims) == 2

    ep_payload = json.loads(eps[0].read_text())
    bundle_id = ep_payload["bundle_id"]
    assert BUNDLE_ID_RE.match(bundle_id) is not None
    for claim_file in claims:
        claim_payload = json.loads(claim_file.read_text())
        assert claim_payload["bundle_id"] == bundle_id
        assert claim_payload["subject_hint"] == "<bundle>"


def test_entity_dry_run_writes_nothing(
    tmp_path: Path, craidd_propose, capsys,
):
    """--dry-run validates and reports but writes no files to the live
    queue. Used by curators to sanity-check a proposal before submitting."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-LLEOLYDD-TEST",
        "--dry-run",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    assert not (tmp_path / "proposals").exists() or not list(
        (tmp_path / "proposals").glob("EP-*.json")
    )


def test_entity_invalid_entity_type_exits_with_validation_failure(
    tmp_path: Path, craidd_propose, capsys,
):
    """`monument` is a v0.3 entity type, not yet enabled — validate_entity_proposal
    rejects it. CLI exit 1 (validation failure) per the documented exit codes."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "monument",
        "--name-cy", "Cromlech",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-TEST",
        "--actor", "test",
    ])
    assert code == 1
    assert not list((tmp_path / "proposals").glob("EP-*.json"))


def test_entity_mismatched_name_pairs_exits_with_input_error(
    tmp_path: Path, craidd_propose, capsys,
):
    """Two --name-cy with only one --name-cy-type: counts mismatch → exit 2."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy", "Adeilad Glyndwr",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-TEST",
        "--actor", "test",
    ])
    assert code == 2
    err = capsys.readouterr().err
    assert "counts must match" in err


def test_entity_invalid_name_type_exits_with_input_error(
    tmp_path: Path, craidd_propose, capsys,
):
    """name_type outside the closed set is caught in the pairing helper
    before propose_entity is called — exit 2 (input error) rather than
    propose_entity's exit 1 (schema validation)."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "made-up-type",
        "--source-id", "TDS-DOL-SRC-TEST",
        "--actor", "test",
    ])
    assert code == 2


def test_entity_malformed_external_ref_exits_with_input_error(
    tmp_path: Path, craidd_propose, capsys,
):
    """External ref without a colon — clear shape error, exit 2."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-TEST",
        "--external-ref", "no-colon-here",
        "--actor", "test",
    ])
    assert code == 2


def test_entity_from_file_missing_entity_type_exits_with_input_error(
    tmp_path: Path, craidd_propose, capsys,
):
    """A --from-file that omits entity_type fails with exit 2 — input
    error caught by _entity_kwargs_from_file before propose_entity is
    called. (Flag-mode 'missing --entity-type' falls through to interactive
    prompts, which is exercised by curators with a real terminal, not
    in unit tests where stdin capture means input() raises OSError.)"""
    src = tmp_path / "ep.json"
    src.write_text(json.dumps({
        "names": [
            {"value": "Tŷ Newyddion", "language": "cy",
             "name_type": "current_local"},
        ],
        "source": {"id": "TDS-DOL-SRC-TEST"},
    }))
    code = craidd_propose([
        "--entity",
        "--from-file", str(src),
        "--data-dir", str(tmp_path),
        "--actor", "test",
    ])
    assert code == 2
    err = capsys.readouterr().err
    assert "entity_type" in err


def test_entity_missing_source_id_exits_with_input_error(
    tmp_path: Path, craidd_propose, capsys,
):
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--actor", "test",
    ])
    assert code == 2


def test_entity_json_output(
    tmp_path: Path, craidd_propose, capsys,
):
    """--json mode produces a parseable success line carrying proposal_id."""
    code = craidd_propose([
        "--entity",
        "--data-dir", str(tmp_path),
        "--entity-type", "building",
        "--name-cy", "Tŷ Newyddion",
        "--name-cy-type", "current_local",
        "--source-id", "TDS-DOL-SRC-TEST",
        "--json",
        "--actor", "test",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert EP_ID_RE.match(payload["proposal_id"]) is not None


def test_claim_mode_unchanged_when_entity_flag_absent(
    tmp_path: Path, craidd_propose, capsys,
):
    """The existing claim-mode path is untouched — adding --entity flag
    doesn't change the default behaviour of the CLI."""
    code = craidd_propose([
        "--data-dir", str(tmp_path),
        "--subject", "TDS-DOL-B-00001",
        "--predicate", "floor_area_m2",
        "--value", "142.6",
        "--source-id", "TDS-DOL-SRC-DOL-ENERGY-2026",
        "--confidence", "medium",
        "--actor", "test",
    ])
    assert code == 0, capsys.readouterr().err
    # No EP files; one claim file.
    assert list((tmp_path / "proposals").glob("EP-*.json")) == []
    claims = list((tmp_path / "proposals").glob("P-*.json"))
    assert len(claims) == 1
