"""geocode — reverse-geocode stop coordinates to place names (OSM Nominatim, free)."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "tripmine/0.1 (photo trip miner; https://github.com/azimshaik/tripmine)"
REQUEST_DELAY = 1.0  # Nominatim polite usage: max 1 req/sec

# address keys worth keeping, in priority order
PLACE_KEYS = [
    "tourism", "waterfall", "natural", "peak", "glacier", "volcano",
    "town", "village", "city", "hamlet", "suburb", "borough",
    "municipality", "county", "region", "state", "island", "country",
]


def _shorten_display(name: str, max_parts: int = 3) -> str:
    """'Skógafoss, Skógar, Suðurland, Iceland' -> 'Skógafoss, Skógar'."""
    parts = [p.strip() for p in name.split(",") if p.strip()]
    if parts and parts[-1].lower() in ("iceland", "united states", "usa", "india", "canada", "united kingdom"):
        parts = parts[:-1]
    return ", ".join(parts[:max_parts])


def reverse_geocode(lat: float, lon: float, cache: dict, zoom: int = 14) -> str | None:
    """Return a short place name for a coordinate. Uses and updates cache dict."""
    key = f"{lat:.5f},{lon:.5f}"
    if key in cache:
        return cache[key]
    params = urllib.parse.urlencode(
        {"format": "jsonv2", "lat": lat, "lon": lon, "zoom": zoom}
    )
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        cache[key] = None
        return None
    name = None
    if data and data.get("display_name"):
        # prefer the most specific place-ish address component
        addr = data.get("address") or {}
        for k in PLACE_KEYS:
            if addr.get(k):
                name = addr[k]
                break
        if not name:
            name = _shorten_display(data["display_name"])
    cache[key] = name
    time.sleep(REQUEST_DELAY)
    return name


def geocode_stops(stops: list[dict], cache_path: Path | None = None) -> None:
    """Fill stop['name'] in place using the cache dict persisted at cache_path."""
    cache: dict = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())
    try:
        for stop in stops:
            if stop["lat"] is None or stop["lon"] is None:
                stop["name"] = "Unknown location (no GPS)"
                continue
            stop["name"] = reverse_geocode(stop["lat"], stop["lon"], cache)
            if not stop["name"]:
                stop["name"] = f"{stop['lat']:.3f}, {stop['lon']:.3f}"
    finally:
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=1))
