"""track — cluster photos into trip stops and geocode them.

Core idea: sort every media file by timestamp, then split into "stops"
wherever the gap between consecutive items exceeds a threshold (default 90
minutes) or a large GPS jump indicates travel without photos.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

GAP_MINUTES = 90          # new stop when photo gap exceeds this
MAX_JUMP_KM = 30.0        # new stop when GPS jump exceeds this (no photos in between)
VIDEO_TYPES = {"MOV", "MP4", "M4V", "AVI"}

STOP_DEFAULTS = {
    "id": 0,
    "name": None,
    "lat": None,
    "lon": None,
    "start": None,
    "end": None,
    "photo_count": 0,
    "video_count": 0,
    "duration_min": 0,
    "files": [],
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    mid = len(xs) // 2
    if len(xs) % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2


def _stop_aggregates(current: list[dict]) -> dict:
    """Rich per-stop stats from the raw records (missing data → None/0)."""
    alts = [r["altitude"] for r in current if r.get("altitude") is not None]
    speeds = [r["speed"] for r in current if r.get("speed") is not None]
    videos = [r for r in current if r["filetype"] in VIDEO_TYPES]
    selfies = [r for r in current if "front" in (r.get("lens") or "").lower()]
    return {
        "altitude_median_m": round(_median(alts), 1) if alts else None,
        "altitude_max_m": round(max(alts), 1) if alts else None,
        "speed_median_kmh": round(_median(speeds), 2) if speeds else None,
        "video_seconds": round(sum(r.get("duration") or 0 for r in videos)),
        "selfies": len(selfies),
    }


def build_stops(records: list[dict]) -> list[dict]:
    """Group chronological media records into stops."""
    dated = [r for r in records if r["ts"] is not None]
    dated.sort(key=lambda r: r["ts"])
    trip_start = dated[0]["ts"].date()

    stops: list[dict] = []
    current: list[dict] = []

    def close_stop() -> None:
        if not current:
            return
        photos = [r for r in current if r["filetype"] not in VIDEO_TYPES]
        videos = [r for r in current if r["filetype"] in VIDEO_TYPES]
        first, last = current[0]["ts"], current[-1]["ts"]
        # first GPS point in the stop is a good anchor (arrival location)
        anchor = next((r for r in current if r["lat"] and r["lon"]), None)
        stop = {
            "id": len(stops),
            "name": None,
            "lat": anchor["lat"] if anchor else None,
            "lon": anchor["lon"] if anchor else None,
            "start": first.isoformat(timespec="minutes"),
            "end": last.isoformat(timespec="minutes"),
            "day": (first.date() - trip_start).days + 1,
            "date": first.date().isoformat(),
            "photo_count": len(photos),
            "video_count": len(videos),
            "duration_min": round((last - first).total_seconds() / 60),
            "files": [r["source"] for r in current],
        }
        stop.update(_stop_aggregates(current))
        stops.append(stop)
        current.clear()

    for record in dated:
        if current:
            gap_min = (record["ts"] - current[-1]["ts"]).total_seconds() / 60
            jump = 0.0
            prev = current[-1]
            if prev["lat"] and prev["lon"] and record["lat"] and record["lon"]:
                jump = _haversine_km(prev["lat"], prev["lon"], record["lat"], record["lon"])
            if gap_min > GAP_MINUTES or (jump > MAX_JUMP_KM and gap_min > 10):
                close_stop()
        current.append(record)

    close_stop()
    return stops


def merge_stays(stops: list[dict], nights_path: Path) -> int:
    """Attach confirmed stays from nights.json onto the stop covering the night.

    The evening anchor timestamp of a confirmed night falls inside the stop
    where the travelers actually were when the night began.
    """
    if not nights_path.exists():
        return 0
    try:
        nights = json.loads(nights_path.read_text())
    except json.JSONDecodeError:
        return 0
    count = 0
    for n in nights:
        conf = n.get("confirmed")
        if not conf:
            continue
        eve_ts = n["evening"]["ts"]
        stop = next((s for s in stops if s["start"] <= eve_ts <= s["end"]), None)
        if stop is None:
            stop = min(
                stops,
                key=lambda s: abs(
                    (datetime.fromisoformat(s["start"]) - datetime.fromisoformat(eve_ts)).total_seconds()
                ),
            )
        stop["stay"] = {
            "name": conf.get("name"),
            "address": conf.get("address"),
            "night": n.get("night"),
        }
        count += 1
    return count


def summarize(records: list[dict]) -> dict:
    """High-level stats about the whole archive."""
    with_ts = sum(1 for r in records if r["ts"])
    with_gps = sum(1 for r in records if r["lat"] and r["lon"])
    photos = sum(1 for r in records if r["filetype"] not in VIDEO_TYPES)
    videos = len(records) - photos
    dated = [r["ts"] for r in records if r["ts"]]
    return {
        "total": len(records),
        "photos": photos,
        "videos": videos,
        "with_timestamp": with_ts,
        "with_gps": with_gps,
        "first_date": min(dated).isoformat() if dated else None,
        "last_date": max(dated).isoformat() if dated else None,
    }
