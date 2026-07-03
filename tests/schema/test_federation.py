"""
Tests for src/craidd/federation.py — the core federation binding + provenance
contract (§10 item 8, Phase 2.1).

Covers the fail-loud invariants (provenance required, verify-not-recall), the
stamp schema shape, the reference-don't-copy discipline (no write-back), and
the bridge to the claim-level cross-rule qualifiers.
"""
from __future__ import annotations

import re

import pytest

from craidd.federation import (
    FederatedResult,
    FederationError,
    SourceOfRecord,
    federation_qualifiers,
    now_utc,
    provenance_stamp,
)
from craidd.schema.validation import validate_claim


def _source() -> SourceOfRecord:
    return SourceOfRecord(
        instance="dolgellau-town-dataset",
        repo="arloesidolgellau/town-dataset",
        framework="awen-weave",
        root="/home/pi/Awen/town-dataset",
        paths={"csv": "seed/output/dolgellau-pricepaid-complete.csv"},
        ran_at_utc="2026-06-30T09:15:00+00:00",
        release="complete",
    )


def _result() -> FederatedResult:
    return FederatedResult(
        source=_source(),
        consumer_instance="wnion-catchment",
        craidd_node="wnion.settlement.property_market",
        craidd_source="town-dataset-pricepaid",
        grade="A",
        federated_utc=now_utc(),
        licence="OGL",
        crs="EPSG:27700",
        aoi="aoi/wnion-catchment.geojson",
        clipped=True,
        counts={"in_source": 2195, "kept": 2100, "dropped_outside": 90, "unlocatable": 5},
        notes="HMLR Price Paid federated from the Town Dataset.",
    )


def test_now_utc_is_iso_with_offset():
    stamp = now_utc()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$", stamp)


def test_provenance_stamp_matches_contract_shape():
    stamp = provenance_stamp(_result())
    assert stamp["binding"] == "federated"
    # source_of_record — the §4 keys, exactly.
    sor = stamp["source_of_record"]
    assert set(sor) == {
        "instance", "repo", "framework", "root", "paths", "ran_at_utc", "release",
    }
    assert sor["instance"] == "dolgellau-town-dataset"
    assert sor["ran_at_utc"] == "2026-06-30T09:15:00+00:00"
    # consumer + read blocks present with their keys.
    assert set(stamp["consumer"]) == {
        "instance", "craidd_node", "craidd_source", "grade",
    }
    assert set(stamp["read"]) == {
        "federated_utc", "licence", "crs", "aoi", "clipped", "counts",
    }
    assert stamp["read"]["counts"]["kept"] == 2100


def test_provenance_stamp_fails_loud_without_source():
    r = _result()
    r.source = None
    with pytest.raises(FederationError, match="source identity"):
        provenance_stamp(r)


def test_provenance_stamp_fails_loud_without_run_utc():
    """Verify-not-recall (invariant 3): no source run-UTC → hard error."""
    r = _result()
    r.source.ran_at_utc = None
    with pytest.raises(FederationError, match="run-UTC"):
        provenance_stamp(r)


def test_provenance_stamp_fails_loud_without_paths():
    r = _result()
    r.source.paths = {}
    with pytest.raises(FederationError, match="paths"):
        provenance_stamp(r)


def test_provenance_stamp_rejects_non_federated_binding():
    r = _result()
    r.binding = "curated"
    with pytest.raises(FederationError, match="federated"):
        provenance_stamp(r)


def test_stamp_does_not_mutate_source_paths():
    """Reference, don't copy (invariant 1): the stamp is a read of the source,
    never a write-back. Mutating the stamp must not reach the source object."""
    r = _result()
    stamp = provenance_stamp(r)
    stamp["source_of_record"]["paths"]["csv"] = "TAMPERED"
    stamp["read"]["counts"]["kept"] = -1
    assert r.source.paths["csv"] == "seed/output/dolgellau-pricepaid-complete.csv"
    assert r.counts["kept"] == 2100


def test_federation_qualifiers_bridge_to_cross_rule():
    """The two keys derived from a result must satisfy the claim-level
    cross-rule — the fail-loud gate and the Prawf stamp cannot drift."""
    quals = federation_qualifiers(_result())
    assert quals == {
        "binding": "federated",
        "federated_from": "dolgellau-town-dataset",
        "source_ran_at": "2026-06-30T09:15:00+00:00",
    }
    claim = {
        "subject_id": "WNI-B-00001",
        "predicate": "address",
        "value_cy": "Tŷ", "value_en": "House",
        "source_id": "WNI-SRC-TOWN-DATASET",
        "recorded_by": "huw@arloesidolgellau.com",
        "confidence": "high",
        "qualifiers": quals,
    }
    assert validate_claim(claim, subject_entity_type="building") == []


def test_federation_qualifiers_fail_loud_without_run_utc():
    r = _result()
    r.source.ran_at_utc = ""
    with pytest.raises(FederationError):
        federation_qualifiers(r)
