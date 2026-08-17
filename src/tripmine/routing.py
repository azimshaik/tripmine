"""routing — real road paths between stops via OSRM (free, no API key).

Makes the trip map look like a real travel route instead of straight
crow-flies lines. Results are cached to disk (routes are deterministic).
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
USER_AGENT = "tripmine/0.2 (route geometry; https://github.com/azimshaik/tripmine)"

# one color per trip day (markers + route segments)
DAY_PALETTE = [
    "#e63946", "#f77f00", "#2a9d8f", "#3a86ff",
    "#7b2cbf", "#2d6a4f", "#c9184a", "#5f0f40",
]


def day_color(day: int | None) -> str:
    if not day:
        return "#888888"
    return DAY_PALETTE[(day - 1) % len(DAY_PALETTE)]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cache_key(points: list[tuple[float, float]]) -> str:
    blob = json.dumps([(round(lat, 5), round(lon, 5)) for lat, lon in points], sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()


def _load_cache(path: Path | None) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def get_route(
    points: list[tuple[float, float]],
    cache_path: Path | None = None,
    timeout: float = 30.0,
) -> dict | None:
    """Road geometry through points (lat, lon) in order.

    Returns {coordinates: [(lon, lat), ...], distance_km, duration_min}
    or None when routing fails (offline, <2 points, OSRM error).
    """
    if len(points) < 2:
        return None
    cache = _load_cache(cache_path)
    key = _cache_key(points)
    if key in cache:
        return cache[key]

    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    params = urllib.parse.urlencode({"overview": "full", "geometries": "geojson"})
    url = f"{OSRM_URL.format(coords=coords)}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    if not data.get("routes"):
        return None
    route = data["routes"][0]
    result = {
        "coordinates": route["geometry"]["coordinates"],  # [lon, lat]
        "distance_km": round(route["distance"] / 1000.0, 1),
        "duration_min": round(route["duration"] / 60.0),
    }
    if cache_path:
        cache[key] = result
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=1))
    return result


def trip_region(stops: list[dict], max_km: float = 600.0) -> list[dict]:
    """Stops within max_km of the trip center (drops airport-city outliers)."""
    gps = [s for s in stops if s.get("lat") is not None and s.get("lon") is not None]
    if not gps or max_km <= 0:
        return gps
    clat = sum(s["lat"] for s in gps) / len(gps)
    clon = sum(s["lon"] for s in gps) / len(gps)
    kept = [
        s for s in gps
        if haversine_km(clat, clon, s["lat"], s["lon"]) <= max_km
    ]
    return kept or gps


def split_route_by_day(route_coords: list[list[float]], stops: list[dict]) -> list[tuple[int, list]]:
    """Split an OSRM LineString at the stop waypoints, keyed by stop day.

    route_coords: [(lon, lat), ...]; stops: region stops in visit order.
    Returns [(day, [(lon, lat), ...]), ...] — consecutive stops on the same
    day produce adjacent segments of the same color.
    """
    if not route_coords or len(stops) < 2:
        return []
    idxs: list[int] = []
    for s in stops:
        tx, ty = s["lon"], s["lat"]
        best, best_d = 0, float("inf")
        start = idxs[-1] if idxs else 0
        for i in range(start, len(route_coords)):
            lon, lat = route_coords[i]
            d = (lon - tx) ** 2 + (lat - ty) ** 2
            if d < best_d:
                best_d, best = d, i
        idxs.append(best)
    segments: list[tuple[int, list]] = []
    for i in range(len(stops) - 1):
        a, b = idxs[i], idxs[i + 1]
        if b <= a:
            continue
        segments.append((stops[i]["day"], route_coords[a:b + 1]))
    return segments
