"""track — cluster photos into trip stops and geocode them.

Core idea: sort every media file by timestamp, then split into "stops"
wherever the gap between consecutive items exceeds a threshold (default 90
minutes) or a large GPS jump indicates travel without photos.
"""

from __future__ import annotations

import math
from datetime import datetime

GAP_MINUTES = 90          # new stop when photo gap exceeds this
MAX_JUMP_KM = 30.0        # new stop when GPS jump exceeds this (no photos in between)

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


def build_stops(records: list[dict]) -> list[dict]:
    """Group chronological media records into stops."""
    dated = [r for r in records if r["ts"] is not None]
    dated.sort(key=lambda r: r["ts"])

    stops: list[dict] = []
    current: list[dict] = []

    def close_stop() -> None:
        if not current:
            return
        photos = [r for r in current if r["filetype"] not in ("MOV", "MP4", "M4V")]
        videos = [r for r in current if r["filetype"] in ("MOV", "MP4", "M4V")]
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
            "photo_count": len(photos),
            "video_count": len(videos),
            "duration_min": round((last - first).total_seconds() / 60),
            "files": [r["source"] for r in current],
        }
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


def summarize(records: list[dict]) -> dict:
    """High-level stats about the whole archive."""
    with_ts = sum(1 for r in records if r["ts"])
    with_gps = sum(1 for r in records if r["lat"] and r["lon"])
    photos = sum(1 for r in records if r["filetype"] not in ("MOV", "MP4", "M4V"))
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
