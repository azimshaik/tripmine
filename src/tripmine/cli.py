"""tripmine CLI — scaffold stage.

Real logic lands as the Iceland dataset feeds through (v0.1):
  extract: Takeout zip -> normalized photos + JSON metadata
  track:   EXIF -> places -> stops -> timeline.json + map.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tripmine import __version__


def _not_built_yet(name: str) -> None:
    print(
        f"⛏️  `tripmine {name}` is scaffolded but not built yet — "
        "the real implementation lands with the v0.1 Iceland build.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def cmd_extract(args: argparse.Namespace) -> None:
    source = Path(args.source)
    if not source.exists():
        print(f"✗ source not found: {source}", file=sys.stderr)
        raise SystemExit(1)
    print(f"✓ input found: {source} ({source.stat().st_size / 1e9:.2f} GB)")
    _not_built_yet("extract")


def cmd_track(args: argparse.Namespace) -> None:
    source = Path(args.source)
    if not source.exists():
        print(f"✗ source not found: {source}", file=sys.stderr)
        raise SystemExit(1)
    print(f"✓ input found: {source}")
    _not_built_yet("track")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tripmine",
        description="Mine trips from your photo archives: exports → map + timeline.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser(
        "extract", help="Unpack a Google Takeout export into photos + metadata"
    )
    p_extract.add_argument("source", help="path to takeout zip or extracted dir")
    p_extract.add_argument("-o", "--output", default="photos", help="output dir")
    p_extract.set_defaults(func=cmd_extract)

    p_track = sub.add_parser(
        "track", help="Build the trip tracker: places, stops, timeline, map"
    )
    p_track.add_argument("source", help="photo/metadata directory")
    p_track.add_argument("-o", "--output", default="tracker", help="output dir")
    p_track.set_defaults(func=cmd_track)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
