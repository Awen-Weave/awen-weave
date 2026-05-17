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

EXIT CODES
----------
    0  success / clean dry-run
    1  validation or operational failure (download error, etc.)
    2  bad arguments / paths
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
from lleolydd.cache.sources import boundary_line as _bl


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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
