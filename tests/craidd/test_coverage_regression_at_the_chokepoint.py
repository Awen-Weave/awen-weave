"""Rule 4 — a re-materialise must not silently shrink national coverage, checked at the CHOKEPOINT.

WHY THE GUARD MOVED. A nation-regression check was written on 16/08 into the catalogue's
`aoi_gate.py` and wired into `build_layer_snapshot.py`, the shared runner. It caught the
elderly-demand Wales drop the same morning. Hours later flood-coverage was re-materialised with
`--nations wales` and lost **296 English authorities** — 646 claims down to 48, a 93% coverage loss
on a national layer a paying consumer reads — and the guard did not fire, because
`build_flood_snapshot.py` is a *different runner*. It reached no served store only because an
unrelated layer aborted the claims build.

Counting afterwards: **seven** scripts in the catalogue write layer snapshots; **two** called the
guard. A guard covering one path and not its sibling is worse than no guard, because it produces
confidence. All seven — and every other repo on the spine — call `SnapshotBuilder.build`. So the
check belongs here, where it cannot be bypassed by writing a new runner.

WHAT THESE TESTS PIN. Not only that the guard fires, but that it is **self-limiting**: a check added
to the shared spine must not break builds it was never meant to police. Per-UPRN layers, layers that
emit no claims, and first builds must all pass untouched. That half matters as much as the catch —
an over-eager guard at a chokepoint takes the whole estate down, and the next person's fix is to
delete it.

All three claims shapes the estate actually writes are covered (verified against the live box,
16/08): `claims.json`, `claims.json.gz`, `claims.jsonl.gz`.
"""
from __future__ import annotations

import gzip
import json

import pytest

from craidd.federation import SourceOfRecord
from craidd.gazetteer import federated_name_claim
from craidd.snapshot import SnapshotBuilder, SnapshotError, SnapshotRecords
from craidd.validation_gate import SchemaValidator

BUILT_UTC = "2026-08-16T22:00:00+00:00"
PRIOR_ID = "snapshot-20260712T000000Z"


def _source() -> SourceOfRecord:
    return SourceOfRecord(
        instance="flood-coverage",
        repo="Awen-Weave/awen-source-catalogue",
        framework="awen-source-catalogue",
        root="awen_source_catalogue.modules.flood_coverage",
        paths={"claims": "claims.json"},
        ran_at_utc="2026-05-21T00:00:00+00:00",
        release="OS Boundary-Line 2026-05",
    )


def _claim(subject_id: str) -> dict:
    """A REAL SCH-CLAIM-001 record. It has to validate, because rule 1 runs before the coverage
    check — a hand-rolled shape would fail the build for the wrong reason and the test would look
    like it was passing on the thing under test."""
    return federated_name_claim(
        subject_id=subject_id,
        predicate="name_en",
        value=f"area {subject_id}",
        source_id="flood-coverage",
        recorded_by="flood-coverage",
        source=_source(),
        name_type="current_local",
    )


def _records(subject_ids) -> SnapshotRecords:
    return SnapshotRecords(
        place_anchors=[], claims=[_claim(s) for s in subject_ids], stamps=[],
        source_ran_at={"flood-coverage": "2026-05-21T00:00:00+00:00"},
    )


def _write_prior(out_dir, subject_ids, *, shape="claims.json"):
    snap = out_dir / PRIOR_ID
    snap.mkdir(parents=True)
    claims = [_claim(s) for s in subject_ids]
    if shape == "claims.json":
        (snap / shape).write_text(json.dumps(claims), encoding="utf-8")
    elif shape == "claims.json.gz":
        with gzip.open(snap / shape, "wt", encoding="utf-8") as fh:
            json.dump(claims, fh)
    elif shape == "claims.jsonl.gz":
        with gzip.open(snap / shape, "wt", encoding="utf-8") as fh:
            for c in claims:
                fh.write(json.dumps(c) + "\n")
    else:                                                    # pragma: no cover
        raise AssertionError(shape)
    (snap / "manifest.json").write_text(json.dumps({"counts": {"claims": len(claims)}}),
                                        encoding="utf-8")
    return snap


def _build(out_dir, subject_ids):
    return SnapshotBuilder(SchemaValidator()).build(
        _records(subject_ids), out_dir, built_utc=BUILT_UTC)


ENGLAND_AND_WALES = ["E06000001", "E06000002", "E08000001", "W06000001", "W06000002"]
WALES_ONLY = ["W06000001", "W06000002"]


# ── the catch ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("shape", ["claims.json", "claims.json.gz", "claims.jsonl.gz"])
def test_dropping_a_nation_is_refused_in_every_claims_shape(tmp_path, shape):
    """The exact 16/08 flood regression, against each shape a real layer writes. A guard that only
    understands the format the one broken layer happened to use is the same mistake again."""
    out = tmp_path / "flood-coverage"
    _write_prior(out, ENGLAND_AND_WALES, shape=shape)

    with pytest.raises(SnapshotError) as exc:
        _build(out, WALES_ONLY)

    msg = str(exc.value)
    assert "coverage REGRESSION" in msg
    assert "england" in msg, "the message must name the nation being dropped"


def test_a_refused_rebuild_writes_nothing(tmp_path):
    """Fail-loud means no partial snapshot on disk — the same contract rule 1 already holds to."""
    out = tmp_path / "flood-coverage"
    _write_prior(out, ENGLAND_AND_WALES)
    with pytest.raises(SnapshotError):
        _build(out, WALES_ONLY)
    assert sorted(p.name for p in out.iterdir()) == [PRIOR_ID]


def test_an_unreadable_prior_on_a_nation_coded_layer_is_refused(tmp_path):
    """The ambiguous state. The layer IS nation-coded, so the comparison matters and we could not
    make it — which must not read as a pass. "We did not look" is not "nothing is missing"."""
    out = tmp_path / "flood-coverage"
    snap = out / PRIOR_ID
    snap.mkdir(parents=True)
    (snap / "manifest.json").write_text("{}", encoding="utf-8")   # no claims file at all

    with pytest.raises(SnapshotError, match="could not read the prior snapshot"):
        _build(out, WALES_ONLY)


# ── the self-limiting half: what it must NOT break ──────────────────────────────────────────────
def test_a_first_build_is_never_a_regression(tmp_path):
    """No prior means nothing to shrink. A guard that makes the empty case impossible is its own
    failure mode — and this one sits in front of every build in the estate."""
    out = tmp_path / "flood-coverage"
    assert _build(out, WALES_ONLY).exists()


def test_widening_coverage_is_allowed(tmp_path):
    out = tmp_path / "flood-coverage"
    _write_prior(out, WALES_ONLY)
    assert _build(out, ENGLAND_AND_WALES).exists()


def test_same_coverage_is_allowed(tmp_path):
    out = tmp_path / "flood-coverage"
    _write_prior(out, ENGLAND_AND_WALES)
    assert _build(out, ENGLAND_AND_WALES).exists()


def test_a_per_uprn_layer_is_untouched_even_with_an_unreadable_prior(tmp_path):
    """UPRN subjects carry no nation code, so there is nothing to compare and never will be. This
    is the blast-radius test: adding the guard at the spine must not start failing every
    property-grain layer in every repo because their priors are in some shape we did not enumerate.
    """
    out = tmp_path / "epc-domestic"
    snap = out / PRIOR_ID
    snap.mkdir(parents=True)
    (snap / "manifest.json").write_text("{}", encoding="utf-8")   # deliberately unreadable claims
    assert _build(out, ["100023336956", "100023336957"]).exists()


def test_a_layer_emitting_no_claims_is_untouched(tmp_path):
    """planning-lifecycle writes a snapshot whose claims are a README, not a claims file. It must
    keep building — verified against the live box, where it is the one layer in that shape."""
    out = tmp_path / "planning-lifecycle"
    snap = out / PRIOR_ID
    snap.mkdir(parents=True)
    (snap / "claims.README.md").write_text("claims are not materialised for this layer",
                                           encoding="utf-8")
    (snap / "manifest.json").write_text("{}", encoding="utf-8")
    recs = SnapshotRecords(place_anchors=[], claims=[], stamps=[], source_ran_at={})
    assert SnapshotBuilder(SchemaValidator()).build(recs, out, built_utc=BUILT_UTC).exists()


def test_a_bare_uprn_is_never_read_as_a_nation_code(tmp_path):
    """A 12-digit UPRN must not accidentally match the nation-code pattern; if it did, every
    property layer would acquire a phantom nation set and the guard would fire at random."""
    from craidd.snapshot import _nations_of
    assert _nations_of([_claim("100023336956")]) == set()
    assert _nations_of([_claim("E06000001")]) == {"E"}
