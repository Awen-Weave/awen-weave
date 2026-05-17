"""
lleolydd-cache — operator CLI for the Lleolydd OGL cache.

Per design/cli-design.md §5 ("Lleolydd"), this CLI is two things:
  build               First-Lleolydd-CLI-to-ship; downloads + indexes +
                      runs band classification. Reads area-bounds from
                      seed/lleolydd/area-bounds.geojson by default.
  snapshot list       Enumerate available snapshot manifests.
  snapshot show       Print one manifest's details.
  snapshot diff       Compare two manifests for changes between releases.
  derive-bounds       One-off — pull a LAD polygon from OS BoundaryLine
                      into area-bounds.geojson. Run once per project.
  schema-sniff        Compare each source's EXPECTED_COLUMNS against
                      the live file on disk. Catch upstream OGL
                      data-format drift cheaply before a full build
                      hits it.

USAGE
-----
    python3 src/cli/lleolydd_cache.py build [--area PATH] [--release YYYY-MM]
                                            [--sources LIST] [--data-dir PATH]
                                            [--force] [--skip-download]
                                            [--dry-run] [--json]
    python3 src/cli/lleolydd_cache.py snapshot list [--data-dir PATH]
    python3 src/cli/lleolydd_cache.py snapshot show <release> [--data-dir PATH]
    python3 src/cli/lleolydd_cache.py snapshot diff <rel-a> <rel-b>
                                                    [--data-dir PATH]
    python3 src/cli/lleolydd_cache.py derive-bounds --lad <name>
                                                    [--output PATH]
                                                    [--workdir PATH]
    python3 src/cli/lleolydd_cache.py schema-sniff [--source NAME]
                                                   [--download-if-missing]
                                                   [--data-dir PATH] [--json]

EXIT CODES
----------
    0  success / clean dry-run / no drift detected
    1  validation or operational failure (download error, etc.) — also
       used by `schema-sniff` when drift is detected
    2  bad arguments / paths — also used by `schema-sniff` when a live
       source file is missing or unreadable
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# src/ and client/ on the path so `lleolydd.cache` and friends resolve
# when this is run as `python3 src/cli/lleolydd_cache.py`.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))

from lleolydd.cache import build as _build
from lleolydd.cache import snapshot as _snapshot
from lleolydd.cache.sources import (
    _common as _src_common,
    boundary_line as _bl,
    inspire as _inspire,
    open_linked_ids as _olid,
    open_toid as _otoid,
    open_uprn as _ouprn,
    zoomstack as _zoomstack,
)


# Ordered registry of source modules — used by `schema-sniff` and any
# future per-source iteration. Keeping the order stable matters for
# the `schema-sniff` output (the operator reads it top-to-bottom).
SOURCE_MODULES = (
    ("open-uprn", _ouprn),
    ("open-toid", _otoid),
    ("open-linked-ids", _olid),
    ("inspire", _inspire),
    ("boundary-line", _bl),
    ("zoomstack", _zoomstack),
)


DEFAULT_DATA_DIR = Path("/srv/town-dataset")
DEFAULT_AREA_BOUNDS = Path("seed/lleolydd/area-bounds.geojson")


def _data_dir(args: argparse.Namespace) -> Path:
    return Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR


def _area_bounds(args: argparse.Namespace) -> Path:
    """The area-bounds geojson — explicit --area wins, else data-dir's
    seed/lleolydd/area-bounds.geojson, else the repo-relative default."""
    if args.area:
        return Path(args.area)
    candidate = _data_dir(args) / DEFAULT_AREA_BOUNDS
    if candidate.exists():
        return candidate
    return DEFAULT_AREA_BOUNDS


def _print_build_summary(summary: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, indent=2, default=str))
        return
    print(f"lleolydd-cache: OK — built {summary['snapshot_id']}")
    print(f"  cache_db     : {summary['cache_db']}")
    print(f"  snapshot_dir : {summary['snapshot_dir']}")
    if "manifest_path" in summary:
        print(f"  manifest     : {summary['manifest_path']}")
    band = summary.get("band_stats")
    if band:
        print()
        print("  band distribution:")
        total = band.get("total", 0)
        for label in ("auto-snapped", "unsnapped",
                      "contested-prox", "contested-lids", "non-postal"):
            n = band.get(label, 0)
            pct = (100 * n / total) if total else 0
            print(f"    {label:13s} : {n:>8,}  ({pct:5.1f}%)")
        print(f"    {'total':13s} : {total:>8,}")


def cmd_build(args: argparse.Namespace) -> int:
    area = _area_bounds(args)
    if not area.is_file():
        print(
            f"lleolydd-cache: area-bounds file not found: {area}. "
            f"Run `lleolydd-cache derive-bounds --lad Gwynedd` to "
            f"generate it, or pass --area PATH.",
            file=sys.stderr,
        )
        return 2
    sources = None
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    try:
        summary = _build.build(
            data_dir=_data_dir(args),
            area_bounds=area,
            release=args.release,
            sources=sources,
            force=args.force,
            skip_download=args.skip_download,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"lleolydd-cache: FAILED — {exc}", file=sys.stderr)
        return 1

    _print_build_summary(summary, args.as_json)
    return 0


def cmd_snapshot_list(args: argparse.Namespace) -> int:
    snapshots_root = _data_dir(args) / "seed" / "lleolydd" / "snapshots"
    items = _snapshot.list_snapshots(snapshots_root)
    if args.as_json:
        print(json.dumps({"snapshots": items}, indent=2))
    else:
        if not items:
            print(f"(no snapshots under {snapshots_root})")
        else:
            for s in items:
                print(s)
    return 0


def cmd_snapshot_show(args: argparse.Namespace) -> int:
    snapshots_root = _data_dir(args) / "seed" / "lleolydd" / "snapshots"
    snap_dir = snapshots_root / args.release
    if not (snap_dir / "manifest.json").is_file():
        print(
            f"lleolydd-cache: no manifest for {args.release} at {snap_dir}",
            file=sys.stderr,
        )
        return 2
    manifest = _snapshot.load_manifest(snap_dir)
    if args.as_json:
        print(json.dumps(manifest, indent=2, default=str))
        return 0
    print(f"snapshot: {manifest['snapshot_id']}")
    print(f"  release      : {manifest['release']}")
    print(f"  created_at   : {manifest['created_at']}")
    print(f"  area_bounds  : {manifest['area_bounds_path']}")
    print(f"  bounds sha256: {manifest['area_bounds_sha256'][:16]}…")
    print(f"  sources      : {len(manifest['sources'])}")
    for s in manifest["sources"]:
        load = s.get("load_stats", {})
        print(
            f"    {s['name']:32s} "
            f"in={load.get('rows_in','?')!s:>10s} "
            f"clipped={load.get('rows_in_area','?')!s:>10s}"
        )
    band = manifest.get("band_stats")
    if band:
        print("  band distribution:")
        total = band.get("total", 0)
        for label in ("auto-snapped", "unsnapped",
                      "contested-prox", "contested-lids", "non-postal"):
            n = band.get(label, 0)
            pct = (100 * n / total) if total else 0
            print(f"    {label:13s} : {n:>8,}  ({pct:5.1f}%)")
        print(f"    {'total':13s} : {total:>8,}")
    return 0


def cmd_snapshot_diff(args: argparse.Namespace) -> int:
    snapshots_root = _data_dir(args) / "seed" / "lleolydd" / "snapshots"
    a_dir = snapshots_root / args.release_a
    b_dir = snapshots_root / args.release_b
    if not (a_dir / "manifest.json").is_file():
        print(f"lleolydd-cache: no manifest for {args.release_a}",
              file=sys.stderr)
        return 2
    if not (b_dir / "manifest.json").is_file():
        print(f"lleolydd-cache: no manifest for {args.release_b}",
              file=sys.stderr)
        return 2
    a = _snapshot.load_manifest(a_dir)
    b = _snapshot.load_manifest(b_dir)

    def _band(m: dict) -> dict:
        return m.get("band_stats") or {}

    diff_payload = {
        "a": {"release": a["release"], "created_at": a["created_at"],
              "band_stats": _band(a)},
        "b": {"release": b["release"], "created_at": b["created_at"],
              "band_stats": _band(b)},
        "deltas": {
            band: _band(b).get(band, 0) - _band(a).get(band, 0)
            for band in ("auto-snapped", "unsnapped", "contested-prox",
                         "contested-lids", "non-postal", "total")
        },
    }
    if args.as_json:
        print(json.dumps(diff_payload, indent=2, default=str))
        return 0
    print(f"snapshot diff: {a['release']} → {b['release']}")
    for k, v in diff_payload["deltas"].items():
        sign = "+" if v >= 0 else ""
        print(f"  {k:13s} : {sign}{v:,}")
    return 0


def cmd_derive_bounds(args: argparse.Namespace) -> int:
    """One-off — pull a LAD polygon from OS BoundaryLine GML into a
    single-feature GeoJSON. The default workdir is a tmp dir we don't
    keep (the 168 MB BoundaryLine ZIP is recoverable any time)."""
    import tempfile  # noqa: PLC0415 — lazy
    out = Path(args.output) if args.output else DEFAULT_AREA_BOUNDS

    if args.workdir:
        workdir = Path(args.workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        files = _bl.download(workdir, force=args.force)
        result = _bl.extract_lad_polygon(files, args.lad, out)
    else:
        with tempfile.TemporaryDirectory(prefix="bdline-") as tmp:
            tmp_path = Path(tmp)
            files = _bl.download(tmp_path, force=args.force)
            result = _bl.extract_lad_polygon(files, args.lad, out)

    if args.as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"lleolydd-cache: OK — derived {args.lad} bounds")
        print(f"  output       : {result['geojson_path']}")
        print(f"  bbox (BNG)   : {result['bbox_bng']}")
        print(f"  area         : {result['area_m2'] / 1e6:.1f} km²")
        print(f"  source sha256: {result['source_file_sha256'][:16]}…")
    return 0


def _find_source_file(
    module,
    name: str,
    data_dir: Path,
) -> Path | None:
    """Locate the live file for a source under the data-dir's latest
    snapshot's downloads/ directory.

    Returns None if no matching file is on disk. Matching:
      - For sources with a SNIFF_FILENAME (currently only boundary_line,
        which targets INSPIRE_AdministrativeUnit.gml exactly), match
        that filename within any subdirectory of downloads/.
      - Otherwise, match the source's FILENAME_PATTERN substring
        case-insensitively against on-disk filenames; prefer .csv > .gml
        > .mbtiles > any other extension (mirrors what the loaders read).
    """
    snapshots_root = data_dir / "seed" / "lleolydd" / "snapshots"
    if not snapshots_root.is_dir():
        return None
    candidate_dirs = sorted(
        (d for d in snapshots_root.iterdir() if d.is_dir()),
        reverse=True,
    )
    sniff_filename = getattr(module, "SNIFF_FILENAME", None)
    pattern = getattr(module, "FILENAME_PATTERN", None)
    preferred_ext = {"csv": ".csv", "gml": ".gml", "mbtiles": ".mbtiles"}.get(
        getattr(module, "SOURCE_KIND", ""),
    )

    for snap_dir in candidate_dirs:
        downloads = snap_dir / "downloads"
        if not downloads.is_dir():
            continue
        files = [p for p in downloads.rglob("*") if p.is_file()]
        if sniff_filename:
            for p in files:
                if p.name == sniff_filename:
                    return p
            continue
        if not pattern:
            continue
        pat_lower = pattern.lower()
        matches = [p for p in files if pat_lower in p.name.lower()]
        if preferred_ext:
            ranked = sorted(
                matches,
                key=lambda p: (
                    0 if p.suffix.lower() == preferred_ext else 1,
                    p.name,
                ),
            )
            if ranked and ranked[0].suffix.lower() == preferred_ext:
                return ranked[0]
        if matches:
            return matches[0]
    return None


def _sniff_one_source(name: str, module, data_dir: Path) -> dict:
    """Run schema-sniff for one source module. Returns a dict the CLI
    renders either as text or JSON.

    Statuses:
      ok      — actual columns match expected.
      drift   — file present, expected columns present in actual,
                BUT actual has at least one extra (added) or is
                missing at least one (removed).
      skip    — SOURCE_KIND in {"mbtiles"} (not column-shaped) or
                the source declines a sniff for other documented reasons.
      missing — file not on disk; --download-if-missing wasn't passed
                or download attempt failed.
      error   — read failed (corrupt file, GDAL error, etc.).
    """
    kind = getattr(module, "SOURCE_KIND", None)
    expected = tuple(getattr(module, "EXPECTED_COLUMNS", ()))

    if kind == "mbtiles":
        return {
            "name": name, "status": "skip",
            "reason": "MBTiles binary — column-shape contract doesn't apply",
            "expected": list(expected),
            "actual": [],
        }

    file_path = _find_source_file(module, name, data_dir)
    if file_path is None:
        return {
            "name": name, "status": "missing",
            "reason": (
                "no live file under any "
                "seed/lleolydd/snapshots/*/downloads/ — run a build first "
                "or pass --download-if-missing"
            ),
            "expected": list(expected),
            "actual": [],
        }

    try:
        if kind == "csv":
            actual = _src_common.sniff_csv_columns(file_path)
        elif kind == "gml":
            actual = _src_common.sniff_gml_columns(file_path)
        else:
            return {
                "name": name, "status": "error",
                "reason": f"unknown SOURCE_KIND {kind!r}",
                "expected": list(expected),
                "actual": [],
                "file": str(file_path),
            }
    except (RuntimeError, OSError) as exc:
        return {
            "name": name, "status": "error",
            "reason": str(exc),
            "expected": list(expected),
            "actual": [],
            "file": str(file_path),
        }

    added, removed = _src_common.diff_columns(expected, actual)
    # Per-kind drift semantics:
    #   csv: strict — any addition or removal is drift. OS publishes a
    #        fixed CSV schema; an extra column is the kind of change a
    #        future loader update might want to consume (or a real
    #        rename in disguise) so we don't auto-tolerate it.
    #   gml: must-include — OGR's auto-generated attributes (OGC_FID,
    #        gml_id, etc.) appear in actual but aren't part of the
    #        loader's contract. We only fail when an EXPECTED column
    #        is missing; extras are reported informationally but don't
    #        trigger drift.
    if kind == "gml":
        drift = bool(removed)
    else:
        drift = bool(added) or bool(removed)
    result = {
        "name": name,
        "expected": list(expected),
        "actual": list(actual),
        "added": list(added),
        "removed": list(removed),
        "file": str(file_path),
        "drift_mode": "must_include" if kind == "gml" else "strict",
    }
    if not drift:
        # Clean if no removed cols (or no diff at all for CSV). Note
        # GML "ok" can still have informational `added` entries —
        # they're rendered but don't fail.
        result["status"] = "ok"
    else:
        result["status"] = "drift"
    return result


def _try_download_for_sniff(module, data_dir: Path) -> Path | None:
    """Best-effort full download (calls the source's download()) and
    returns the first on-disk file after the call. Used by schema-sniff
    --download-if-missing. Catches any exception so a single source's
    network failure doesn't abort the whole sniff."""
    snapshots_root = data_dir / "seed" / "lleolydd" / "snapshots"
    snapshots_root.mkdir(parents=True, exist_ok=True)
    # Place ad-hoc-downloaded files under a sentinel snapshot dir so
    # we don't accidentally populate a real release.
    target = snapshots_root / "schema-sniff" / "downloads"
    target.mkdir(parents=True, exist_ok=True)
    try:
        module.download(target)
    except Exception:  # noqa: BLE001 — best-effort; reported via status
        return None
    files = [p for p in target.rglob("*") if p.is_file()]
    if not files:
        return None
    return files[0]


def cmd_schema_sniff(args: argparse.Namespace) -> int:
    """Compare each source's expected columns against the live file
    on disk. Exit 0 clean / 1 drift / 2 file-missing (or read failure).

    See `seed/lleolydd/README.md` for operational guidance — recommended
    pre-flight check before kicking off a full cache build.
    """
    data_dir = _data_dir(args)

    scope: tuple[tuple[str, object], ...]
    if args.source:
        wanted = args.source
        match = [(n, m) for (n, m) in SOURCE_MODULES if n == wanted]
        if not match:
            print(
                f"lleolydd-cache: unknown source {wanted!r}. Known: "
                f"{', '.join(n for n, _ in SOURCE_MODULES)}.",
                file=sys.stderr,
            )
            return 2
        scope = tuple(match)
    else:
        scope = SOURCE_MODULES

    results: list[dict] = []
    for name, module in scope:
        result = _sniff_one_source(name, module, data_dir)
        if (
            result["status"] == "missing"
            and getattr(args, "download_if_missing", False)
            and getattr(module, "SOURCE_KIND", None) != "mbtiles"
        ):
            downloaded = _try_download_for_sniff(module, data_dir)
            if downloaded is not None:
                result = _sniff_one_source(name, module, data_dir)
            else:
                result["reason"] = (
                    "download attempted (--download-if-missing) but "
                    "failed; file still not present"
                )
        results.append(result)

    drift_count = sum(1 for r in results if r["status"] == "drift")
    error_count = sum(
        1 for r in results if r["status"] in ("error", "missing")
    )
    if drift_count > 0:
        exit_code = 1
    elif error_count > 0:
        exit_code = 2
    else:
        exit_code = 0

    if args.as_json:
        payload = {
            "sources": results,
            "drift_count": drift_count,
            "error_count": error_count,
            "exit_code": exit_code,
        }
        print(json.dumps(payload, indent=2, default=str))
        return exit_code

    print("lleolydd-cache schema-sniff")
    print("-" * 60)
    for r in results:
        tag = {
            "ok":      "[ok]    ",
            "drift":   "[drift] ",
            "skip":    "[skip]  ",
            "missing": "[miss]  ",
            "error":   "[err]   ",
        }.get(r["status"], "[?]     ")
        line = f"{tag}{r['name']:<18}"
        if r["status"] == "ok":
            mode = r.get("drift_mode", "strict")
            extra = r.get("added") or []
            if mode == "must_include" and extra:
                # GML: surfacing the auto-generated / upstream extras
                # without failing — informational, not drift.
                print(
                    f"{line} — all {len(r['expected'])} required columns "
                    f"present (must-include mode); "
                    f"extras present (informational): {tuple(extra)}"
                )
            else:
                print(
                    f"{line} — all {len(r['expected'])} expected columns "
                    f"present"
                )
        elif r["status"] == "drift":
            mode = r.get("drift_mode", "strict")
            print(f"{line} — schema drift (mode={mode})")
            print(f"           expected: {tuple(r['expected'])}")
            print(f"           actual:   {tuple(r['actual'])}")
            print(f"           added:    {tuple(r['added'])}")
            print(f"           removed:  {tuple(r['removed'])}")
        elif r["status"] == "skip":
            print(f"{line} — skip ({r.get('reason', '')})")
        elif r["status"] == "missing":
            print(f"{line} — missing: {r.get('reason', '')}")
        else:
            print(f"{line} — error: {r.get('reason', '')}")
    print("-" * 60)
    print(f"summary: drift={drift_count} error/missing={error_count}")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lleolydd-cache",
        description="Build + inspect the Lleolydd OGL cache.",
    )
    parser.add_argument("--data-dir", default=None,
                        help="cache lives under PATH/seed/lleolydd/ "
                             "(default: /srv/town-dataset)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser(
        "build", help="download, index, classify bands; full or partial build",
    )
    p_build.add_argument("--area", default=None,
                         help="area-bounds geojson (default: data-dir's "
                              "seed/lleolydd/area-bounds.geojson)")
    p_build.add_argument("--release", default=None,
                         help="release tag (default: current YYYY-MM)")
    p_build.add_argument("--sources", default=None,
                         help="comma-list subset of "
                              "{open-uprn,open-toid,open-linked-ids,"
                              "inspire,zoomstack}; default all")
    p_build.add_argument("--force", action="store_true",
                         help="overwrite an existing release directory")
    p_build.add_argument("--skip-download", action="store_true",
                         help="don't download; reuse existing snapshot "
                              "downloads/ dir")
    p_build.add_argument("--dry-run", action="store_true",
                         help="plan + validate inputs, write nothing")
    p_build.set_defaults(func=cmd_build)

    p_snap = sub.add_parser("snapshot", help="snapshot inspection")
    snap_sub = p_snap.add_subparsers(dest="snapshot_cmd", required=True)
    p_snap_list = snap_sub.add_parser("list")
    p_snap_list.set_defaults(func=cmd_snapshot_list)
    p_snap_show = snap_sub.add_parser("show")
    p_snap_show.add_argument("release", help="release tag, e.g. 2026-05")
    p_snap_show.set_defaults(func=cmd_snapshot_show)
    p_snap_diff = snap_sub.add_parser("diff")
    p_snap_diff.add_argument("release_a")
    p_snap_diff.add_argument("release_b")
    p_snap_diff.set_defaults(func=cmd_snapshot_diff)

    p_derive = sub.add_parser(
        "derive-bounds",
        help="one-off — pull a LAD polygon from OS BoundaryLine GML",
    )
    p_derive.add_argument("--lad", required=True,
                          help="LAD name as it appears in BoundaryLine "
                               "(e.g. 'Gwynedd')")
    p_derive.add_argument("--output", default=None,
                          help="target GeoJSON path (default: "
                               "seed/lleolydd/area-bounds.geojson)")
    p_derive.add_argument("--workdir", default=None,
                          help="keep the BoundaryLine download here "
                               "(default: tmp dir, auto-cleaned)")
    p_derive.add_argument("--force", action="store_true",
                          help="re-download even if zip is present")
    p_derive.set_defaults(func=cmd_derive_bounds)

    p_sniff = sub.add_parser(
        "schema-sniff",
        help=(
            "compare each source's EXPECTED_COLUMNS against the live "
            "file on disk; catch upstream OGL data-format drift before "
            "a full cache build hits it"
        ),
    )
    p_sniff.add_argument(
        "--source", default=None,
        help=(
            "scope to one source (e.g. open-uprn, open-toid, "
            "open-linked-ids, inspire, boundary-line, zoomstack). "
            "Default: all six."
        ),
    )
    p_sniff.add_argument(
        "--download-if-missing", action="store_true",
        dest="download_if_missing",
        help=(
            "if the live file isn't on disk, call the source's "
            "download() to fetch it (best-effort; per-source download "
            "failures are reported, not raised). Files land under "
            "seed/lleolydd/snapshots/schema-sniff/downloads/ to keep "
            "them out of real release directories."
        ),
    )
    p_sniff.set_defaults(func=cmd_schema_sniff)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
