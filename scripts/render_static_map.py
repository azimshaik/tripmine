"""Render timeline.json as a static PNG map (Pillow-only, no browser needed).

Usage: uv run --with pillow python scripts/render_static_map.py \
         tracker/timeline.json -o tracker/map.png

Stitches OSM raster tiles, draws the route polyline + numbered stop markers,
and appends a legend with names/dates/counts.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE = 256
USER_AGENT = "tripmine/0.1 (static map renderer; https://github.com/azimshaik/tripmine)"
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
MAX_TILES = 8  # cap width/height in tiles to keep requests polite

COLORS = {
    "route": (224, 122, 47, 255),
    "marker": (200, 40, 40, 255),
    "text": (30, 30, 30, 255),
    "bg": (255, 255, 255, 255),
}


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def tile_to_lonlat(x: int, y: int, z: int) -> tuple[float, float]:
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def pick_zoom(lon_span: float) -> int:
    """Highest zoom whose tile width fits within MAX_TILES."""
    for z in range(14, 3, -1):
        tiles_w = 360 / 2 ** z  # degrees of longitude per tile
        needed = math.ceil((lon_span + 0.5) / tiles_w)
        if needed <= MAX_TILES:
            return z
    return 3


def fetch_tile(z: int, x: int, y: int) -> Image.Image:
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return Image.open(io.BytesIO(resp.read())).convert("RGB")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def render(timeline: dict, out_path: Path, max_km: float = 600.0) -> Path:
    stops = [s for s in timeline["stops"] if s["lat"] is not None]
    if not stops:
        raise ValueError("no stops with GPS coordinates")

    if max_km > 0:
        # drop outliers (e.g. airport-city stops 4000km from the trip) so the
        # map focuses on the actual trip region
        center = (sum(s["lat"] for s in stops) / len(stops),
                  sum(s["lon"] for s in stops) / len(stops))
        kept = [s for s in stops if _haversine_km(center[0], center[1], s["lat"], s["lon"]) <= max_km]
        if kept:
            stops = kept

    lats = [s["lat"] for s in stops]
    lons = [s["lon"] for s in stops]
    lat_span = max(lats) - min(lats)
    lon_span = max(lons) - min(lons)

    # center the view with padding (add 10% of span each side)
    pad_lat, pad_lon = max(lat_span * 0.15, 0.05), max(lon_span * 0.15, 0.05)
    north, south = max(lats) + pad_lat, min(lats) - pad_lat
    east, west = max(lons) + pad_lon, min(lons) - pad_lon

    z = pick_zoom(east - west)
    x_min_f, y_min_f = lonlat_to_tile(west, north, z)
    x_max_f, y_max_f = lonlat_to_tile(east, south, z)
    x0, y0 = math.floor(x_min_f), math.floor(y_min_f)
    x1, y1 = math.ceil(x_max_f), math.ceil(y_max_f)
    # cap tile count (politeness + memory)
    if x1 - x0 > MAX_TILES:
        mid = (x0 + x1) // 2
        x0, x1 = mid - MAX_TILES // 2, mid + MAX_TILES // 2
    if y1 - y0 > MAX_TILES:
        mid = (y0 + y1) // 2
        y0, y1 = mid - MAX_TILES // 2, mid + MAX_TILES // 2

    img = Image.new("RGB", ((x1 - x0) * TILE, (y1 - y0) * TILE), COLORS["bg"])
    for xt in range(x0, x1):
        for yt in range(y0, y1):
            try:
                tile = fetch_tile(z, xt, yt)
            except Exception:
                tile = Image.new("RGB", (TILE, TILE), (220, 220, 220))
            img.paste(tile, ((xt - x0) * TILE, (yt - y0) * TILE))

    def to_px(lon: float, lat: float) -> tuple[float, float]:
        xf, yf = lonlat_to_tile(lon, lat, z)
        return (xf - x0) * TILE, (yf - y0) * TILE

    draw = ImageDraw.Draw(img)

    # route polyline (chronological)
    pts = [to_px(s["lon"], s["lat"]) for s in stops]
    draw.line(pts, fill=COLORS["route"], width=5, joint="curve")

    # numbered markers
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except OSError:
        font = small = ImageFont.load_default()

    for i, (s, (px, py)) in enumerate(zip(stops, pts), 1):
        r = 16
        draw.ellipse([px - r, py - r, px + r, py + r], fill=COLORS["marker"], outline=(255, 255, 255), width=3)
        label = str(i)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((px - tw / 2 - bbox[0], py - th / 2 - bbox[1]), label, fill=(255, 255, 255), font=font)

    # legend panel below the map
    line_h = 24
    legend = Image.new("RGB", (img.width, line_h * (len(stops) + 2) + 20), COLORS["bg"])
    ld = ImageDraw.Draw(legend)
    ld.text((14, 8), "Trip stops (chronological):", fill=COLORS["text"], font=small)
    for i, s in enumerate(stops, 1):
        y = 10 + line_h * (i + 1)
        date_part = f"{s['start'][5:16]}"
        name = s["name"] or "?"
        text = f"{i}. {date_part}  {name}  —  📷{s['photo_count']} 🎬{s['video_count']} ({s['duration_min']} min)"
        ld.text((14, y), text, fill=COLORS["text"], font=small)

    canvas = Image.new("RGB", (img.width, img.height + legend.height), COLORS["bg"])
    canvas.paste(img, (0, 0))
    canvas.paste(legend, (0, img.height))
    canvas.save(out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("timeline", help="path to timeline.json")
    ap.add_argument("-o", "--output", default="map.png", help="output png path")
    ap.add_argument("--max-km", type=float, default=600.0,
                    help="drop stops farther than N km from the trip center (0 = keep all)")
    args = ap.parse_args()
    timeline = json.loads(Path(args.timeline).read_text())
    out = render(timeline, Path(args.output), max_km=args.max_km)
    print(f"✓ map → {out}")


if __name__ == "__main__":
    main()
