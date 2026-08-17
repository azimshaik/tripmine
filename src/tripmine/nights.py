"""nights — detect overnight gaps from media timestamps: the 'where did we sleep' view.

A "night" is a gap of >= GAP_HOURS between consecutive media timestamps.
The evening anchor (last photo before the gap) and morning anchor (first
photo after) pin down where the night was spent. `confirmed` fields are
carried over from an existing nights.json so users can annotate real stays.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

GAP_HOURS = 5.0


def _as_dt(ts):
    if isinstance(ts, str):
        return datetime.fromisoformat(ts)
    return ts


def _nearest_gps(recs: list[dict], idx: int, direction: int) -> dict:
    """Nearest record with GPS starting at idx, scanning direction (+1/-1)."""
    i = idx
    while 0 <= i < len(recs):
        if recs[i].get("lat") and recs[i].get("lon"):
            return recs[i]
        i += direction
    return recs[idx]


def detect_nights(records: list[dict], gap_hours: float = GAP_HOURS) -> list[dict]:
    """Find overnight gaps in chronological media records."""
    recs = sorted((r for r in records if r["ts"]), key=lambda r: _as_dt(r["ts"]))
    nights: list[dict] = []
    for i in range(1, len(recs)):
        gap = (_as_dt(recs[i]["ts"]) - _as_dt(recs[i - 1]["ts"])).total_seconds() / 3600
        if gap >= gap_hours:
            eve = _nearest_gps(recs, i - 1, -1)   # last GPS photo before the gap
            morn = _nearest_gps(recs, i, 1)       # first GPS photo after the gap
            nights.append({
                "night": len(nights) + 1,
                "date": _as_dt(recs[i - 1]["ts"]).date().isoformat(),
                "gap_hours": round(gap, 1),
                "evening": {
                    "ts": _as_dt(eve["ts"]).isoformat(), "lat": eve["lat"], "lon": eve["lon"],
                    "file": eve["source"],
                },
                "morning": {
                    "ts": _as_dt(morn["ts"]).isoformat(), "lat": morn["lat"], "lon": morn["lon"],
                    "file": morn["source"],
                },
                "area": None,       # reverse-geocoded from the evening anchor
                "confirmed": None,  # user-annotated: {"name": "...", "address": "..."}
            })
    return nights


def geocode_nights(nights: list[dict], geocode_fn, cache: dict) -> None:
    """Fill night['area'] from the evening anchor (street-level zoom 16)."""
    for n in nights:
        e = n["evening"]
        if e.get("lat") is None or e.get("lon") is None:
            n["area"] = "Unknown (no GPS)"
            continue
        name = geocode_fn(e["lat"], e["lon"], cache, zoom=16)
        n["area"] = name or f"{e['lat']:.3f}, {e['lon']:.3f}"


def merge_confirmed(nights: list[dict], nights_path: Path) -> None:
    """Carry over user-annotated `confirmed` stays from an existing nights.json."""
    if not nights_path.exists():
        return
    try:
        old = json.loads(nights_path.read_text())
    except json.JSONDecodeError:
        return
    by_date = {o["date"]: o for o in old if o.get("date")}
    for n in nights:
        prev = by_date.get(n["date"])
        if prev and prev.get("confirmed"):
            n["confirmed"] = prev["confirmed"]


def write_nights(nights: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(nights, indent=2, ensure_ascii=False))
