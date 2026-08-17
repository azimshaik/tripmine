"""tripmine CLI — extract photo exports, build trip trackers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tripmine import __version__
from tripmine import extract as extract_mod
from tripmine import gallery, geocode, map as map_mod, metadata, nights, track


def cmd_extract(args: argparse.Namespace) -> None:
    source = Path(args.source)
    if not source.exists():
        print(f"✗ source not found: {source}", file=sys.stderr)
        raise SystemExit(1)
    out_dir = Path(args.output)
    try:
        count = extract_mod.extract(source, out_dir, keep_sidecars=not args.no_sidecars)
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"✓ extracted {count} media files → {out_dir}")


def cmd_track(args: argparse.Namespace) -> None:
    source = Path(args.source)
    if not source.exists():
        print(f"✗ source not found: {source}", file=sys.stderr)
        raise SystemExit(1)

    print("⏳ reading metadata (exiftool)...")
    records = metadata.read_all(source)
    if not records:
        print("✗ no media files found", file=sys.stderr)
        raise SystemExit(1)

    summary = track.summarize(records)
    print(
        f"  {summary['total']} files · {summary['photos']} photos · {summary['videos']} videos · "
        f"{summary['with_gps']} with GPS"
    )

    print("⏳ clustering into stops...")
    stops = track.build_stops(records)
    print(f"  {len(stops)} stops")

    print("⏳ reverse-geocoding (OSM Nominatim)...")
    cache_path = Path(args.output) / "geocode_cache.json"
    geocode.geocode_stops(stops, cache_path)

    nights_path = Path(args.output) / "nights.json"
    merged = track.merge_stays(stops, nights_path)
    if merged:
        print(f"  ✓ {merged} confirmed stay(s) merged into stops")

    out_dir = Path(args.output)
    written = map_mod.write_outputs(stops, summary, out_dir)
    print(f"✓ timeline → {written['timeline']}")
    print(f"✓ map      → {written['map']}")


def cmd_inspect(args: argparse.Namespace) -> None:
    source = Path(args.source)
    if not source.exists():
        print(f"✗ source not found: {source}", file=sys.stderr)
        raise SystemExit(1)
    print("⏳ reading metadata (exiftool)...")
    records = metadata.read_all(source)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_safe = []
    for r in records:
        copy = dict(r)
        copy["ts"] = r["ts"].isoformat() if r["ts"] else None
        json_safe.append(copy)
    out_path.write_text(json.dumps(json_safe, indent=1, ensure_ascii=False))
    print(f"✓ {len(records)} records → {out_path}")
    print(f"  sample: {records[0]['source']} | {records[0]['model']} | "
          f"alt {records[0].get('altitude')}m | spd {records[0].get('speed')}km/h | "
          f"dir {records[0].get('direction')}° | acc {records[0].get('accuracy')}m")


def cmd_nights(args: argparse.Namespace) -> None:
    src = Path(args.source)
    if not src.exists():
        print(f"✗ source not found: {src}", file=sys.stderr)
        raise SystemExit(1)
    if src.is_dir():
        print("⏳ reading metadata (exiftool)...")
        records = metadata.read_all(src)
    else:
        try:
            records = json.loads(src.read_text())
        except json.JSONDecodeError:
            print(f"✗ not a valid metadata.json: {src}", file=sys.stderr)
            raise SystemExit(1)

    detected = nights.detect_nights(records)
    cache: dict = {}
    cache_path = Path(args.output).parent / "geocode_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
    nights.geocode_nights(detected, geocode.reverse_geocode, cache)
    nights.merge_confirmed(detected, Path(args.output))
    nights.write_nights(detected, Path(args.output))
    cache_path.write_text(json.dumps(cache, indent=1))

    for n in detected:
        stay = n["confirmed"]["name"] if n["confirmed"] else "—"
        print(f"  N{n['night']} {n['date']}  {str(n['area'])[:36]:36} gap {n['gap_hours']}h  stay: {stay}")
    print(f"✓ nights → {args.output}")


def cmd_gallery(args: argparse.Namespace) -> None:
    timeline_path = Path(args.timeline)
    if not timeline_path.exists():
        print(f"✗ timeline not found: {timeline_path}", file=sys.stderr)
        raise SystemExit(1)
    timeline = json.loads(timeline_path.read_text())
    out_dir = Path(args.output)
    result = gallery.build_gallery(
        timeline, Path(args.photos), out_dir,
        max_per_stop=args.max_per_stop,
        ffmpeg=not args.no_video_thumbs,
    )
    print(f"✓ gallery → {result['html']} ({result['thumbs']} thumbnails)")
    print(f"✓ contact sheets → {len(result['sheets'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tripmine",
        description="Mine trips from your photo archives: exports → map + timeline.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser(
        "extract", help="Unpack a Google Takeout / iCloud export into photos + metadata"
    )
    p_extract.add_argument("source", help="path to takeout zip or extracted dir")
    p_extract.add_argument("-o", "--output", default="photos", help="output dir")
    p_extract.add_argument(
        "--no-sidecars", action="store_true",
        help="skip .json sidecar files (Google Takeout metadata)",
    )
    p_extract.set_defaults(func=cmd_extract)

    p_track = sub.add_parser(
        "track", help="Build the trip tracker: places, stops, timeline, map"
    )
    p_track.add_argument("source", help="photo/metadata directory")
    p_track.add_argument("-o", "--output", default="tracker", help="output dir")
    p_track.set_defaults(func=cmd_track)

    p_inspect = sub.add_parser(
        "inspect", help="Dump full metadata (altitude, speed, direction, camera specs) for every file"
    )
    p_inspect.add_argument("source", help="photo/metadata directory")
    p_inspect.add_argument("-o", "--output", default="metadata.json", help="output json path")
    p_inspect.set_defaults(func=cmd_inspect)

    p_gallery = sub.add_parser(
        "gallery", help="Per-stop photo gallery: thumbnails, quality picks, contact sheets"
    )
    p_gallery.add_argument("timeline", help="path to timeline.json")
    p_gallery.add_argument("photos", help="photo directory (the extracted photos)")
    p_gallery.add_argument("-o", "--output", default="gallery", help="output dir")
    p_gallery.add_argument("--max-per-stop", type=int, default=24, help="max thumbnails per stop")
    p_gallery.add_argument("--no-video-thumbs", action="store_true", help="skip video first-frames")
    p_gallery.set_defaults(func=cmd_gallery)

    p_nights = sub.add_parser(
        "nights", help="Detect overnight gaps (where you slept) + annotate confirmed stays"
    )
    p_nights.add_argument("source", help="photos dir or metadata.json")
    p_nights.add_argument("-o", "--output", default="nights.json", help="output json path")
    p_nights.set_defaults(func=cmd_nights)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
