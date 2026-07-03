"""
src/craidd/federation.py — the core federation binding + provenance contract.

Phase 2.1 (2026-07-03). Promoted from Wnion's hand-rolled
`wnion_catchment/federation.py` into the framework so every Awen instance
federates another instance's data the SAME way — reference it, never copy
it — with one uniform, Prawf-loggable provenance stamp.

This module is the generic *frame*. Instances keep their own readers (which
source files/layers, the AOI polygon, the geolocation method, the per-layer
Craidd targets) but return a core `FederatedResult` and call the core
`provenance_stamp`, instead of re-implementing the schema. See
design/v0.1-schema.md §10 item 8 and the federation spec.

It operationalises SOV-001 (federated sovereignty) and the family-data
architecture (Awen Weave brokers, never centralises): Wnion's WNI-SOV and
Dolgellau Energy's EGNI-001 ("federate the Town Dataset; don't copy") both
assume exactly this contract.

The binding invariants (fail-loud):
  1. Reference, don't copy. A federated read points at the source's output
     read-only; it never writes back to the source and never re-homes the
     source's data inside the consumer.
  2. Provenance required. Every federated read emits the §4 stamp; missing
     source identity, source run-UTC, or paths is a hard `FederationError`.
  3. Verify-not-recall. The consumer records the source's OWN run-UTC (from
     the source's stats/manifest); it does not re-fetch or re-derive upstream.
  4. Grade-and-link. Each federated layer resolves to a graded Craidd node on
     the consumer, carrying the `binding: federated` qualifier.

The two claim-level qualifiers the validation cross-rule requires
(`federated_from`, `source_ran_at`; schema/qualifiers.py, schema/validation.py)
are the minimal fail-loud gate on the claim itself; the FULL stamp below is
what Prawf logs and a Craffter audits. `federation_qualifiers()` builds those
two keys from a result so the two layers can never drift.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


class FederationError(RuntimeError):
    """Fail-loud error for a malformed or provenance-less federated read."""


@dataclass
class SourceOfRecord:
    """Identity of the instance a datum is federated FROM.

    `ran_at_utc` is the source's OWN run-UTC (invariant 3, verify-not-recall):
    it is read from the source's stats/manifest, never re-derived by the
    consumer. `paths` maps logical names to paths relative to `root` — the
    read-only outputs the consumer references (invariant 1).
    """

    instance: str                       # source instance id (e.g. "dolgellau-town-dataset")
    repo: str                           # source repo (e.g. "arloesidolgellau/town-dataset")
    framework: str                      # "awen-weave" | "maes" | "tref" | …
    root: str                           # resolved source root on disk
    paths: dict[str, str]               # logical name -> path relative to root
    ran_at_utc: str | None              # source's OWN run UTC (from its stats)
    release: str | None                 # source release/tag (e.g. "complete", "2026-05")


@dataclass
class FederatedResult:
    """One federated read — never written back to the source (invariant 1).

    A generic container an instance's reader populates and hands to
    `provenance_stamp`. Instance-specific detail (per-row records, AOI clip
    geometry, geolocation method) stays in the instance's own result type;
    what lands here is only what the shared provenance contract needs.
    """

    binding: str = "federated"
    source: SourceOfRecord | None = None
    consumer_instance: str = ""
    craidd_node: str | None = None      # target node on the consumer's Craidd
    craidd_source: str | None = None    # source id in the consumer's Craidd
    grade: str | None = None            # A|B|C — the graded link (invariant 4)
    federated_utc: str = ""             # consumer's read UTC
    licence: str = ""                   # e.g. "OGL"
    crs: str = "n/a"                    # e.g. "EPSG:27700" | "n/a"
    aoi: str = "n/a"                    # clip region | "n/a"
    clipped: bool = False
    counts: dict[str, int] = field(default_factory=dict)
    notes: str = ""


def now_utc() -> str:
    """The current UTC instant as an ISO-8601 string (seconds precision).

    The consumer's read UTC (`FederatedResult.federated_utc`). NOT the source's
    run-UTC — that is `SourceOfRecord.ran_at_utc`, read from the source and
    never manufactured here (invariant 3).
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def provenance_stamp(r: FederatedResult) -> dict:
    """Build the reusable provenance stamp for a federated read.

    The canonical shape Prawf logs for a federated datum and a Craffter audits
    (federation spec §4). Fail-loud (invariants 2 & 3): a federated read with
    no source identity, or no source run-UTC, or no source paths, raises
    `FederationError` rather than emitting a hollow stamp.
    """
    if r.binding != "federated":
        raise FederationError(
            f"provenance_stamp is for federated reads; got binding={r.binding!r}"
        )
    if r.source is None or not r.source.instance:
        raise FederationError(
            "federated read missing source identity (invariant 2): "
            "source_of_record.instance is required"
        )
    if r.source.ran_at_utc is None or not str(r.source.ran_at_utc).strip():
        raise FederationError(
            "federated read missing source run-UTC (invariant 3, "
            "verify-not-recall): source_of_record.ran_at_utc is required"
        )
    if not r.source.paths:
        raise FederationError(
            "federated read missing source paths (invariant 2): "
            "source_of_record.paths must reference the read-only source outputs"
        )
    return {
        "binding": r.binding,
        "source_of_record": {
            "instance": r.source.instance,
            "repo": r.source.repo,
            "framework": r.source.framework,
            "root": r.source.root,
            "paths": dict(r.source.paths),
            "ran_at_utc": r.source.ran_at_utc,
            "release": r.source.release,
        },
        "consumer": {
            "instance": r.consumer_instance,
            "craidd_node": r.craidd_node,
            "craidd_source": r.craidd_source,
            "grade": r.grade,
        },
        "read": {
            "federated_utc": r.federated_utc,
            "licence": r.licence,
            "crs": r.crs,
            "aoi": r.aoi,
            "clipped": r.clipped,
            "counts": dict(r.counts),
        },
        "notes": r.notes,
    }


def federation_qualifiers(r: FederatedResult) -> dict[str, str]:
    """The claim-level qualifiers a federated datum must carry.

    Bridges this module to the schema cross-rule (schema/validation.py): the
    two keys returned here are exactly what a `binding=federated` claim needs
    to validate. Building them from the same `FederatedResult` that produced
    the full stamp guarantees the fail-loud gate on the claim and the
    Prawf-logged stamp can never drift apart. Fail-loud on the same missing
    source identity / run-UTC as `provenance_stamp`.
    """
    if r.source is None or not r.source.instance or not (
        r.source.ran_at_utc and str(r.source.ran_at_utc).strip()
    ):
        raise FederationError(
            "cannot derive federation qualifiers: source identity + run-UTC "
            "required (invariants 2 & 3)"
        )
    return {
        "binding": "federated",
        "federated_from": r.source.instance,
        "source_ran_at": r.source.ran_at_utc,
    }
