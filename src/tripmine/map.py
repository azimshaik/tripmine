"""map — render the trip as timeline.json + a self-contained Leaflet map.html."""

from __future__ import annotations

import json
from pathlib import Path

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

MAP_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tripmine — {title}</title>
<link rel="stylesheet" href="{css}">
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 0; background: #f6f5f2; color: #222; }}
  header {{ padding: 18px 22px 10px; }}
  h1 {{ margin: 0; font-size: 22px; }}
  .meta {{ color: #666; font-size: 13px; margin-top: 4px; }}
  #map {{ height: 55vh; margin: 0 14px; border-radius: 10px; box-shadow: 0 1px 6px rgba(0,0,0,.15); }}
  .timeline {{ max-width: 760px; margin: 18px auto 40px; padding: 0 14px; }}
  .stop {{ background: #fff; border-radius: 10px; padding: 12px 16px; margin: 10px 0; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .stop h3 {{ margin: 0 0 4px; font-size: 16px; }}
  .stop .when {{ color: #777; font-size: 12.5px; }}
  .stop .stats {{ color: #555; font-size: 13px; margin-top: 4px; }}
  .day-divider {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: #999; margin: 22px 0 6px; }}
</style>
</head>
<body>
<header>
  <h1>⛏️ {title}</h1>
  <div class="meta">{summary}</div>
</header>
<div id="map"></div>
<div class="timeline" id="timeline"></div>
<script src="{js}"></script>
<script>
const stops = {stops_json};
const map = L.map('map').setView({center}, {zoom});
L.tileLayer('{tiles}', {{ attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }}).addTo(map);
const markers = [];
const polyline = [];
stops.forEach((s, i) => {{
  if (s.lat == null || s.lon == null) return;
  const m = L.marker([s.lat, s.lon]).addTo(map)
    .bindPopup(`<b>${{s.name}}</b><br>${{s.start}} → ${{s.end}}<br>📷 ${{s.photo_count}} · 🎬 ${{s.video_count}}`);
  markers.push(m); polyline.push([s.lat, s.lon]);
}});
if (polyline.length > 1) L.polyline(polyline, {{ color: '#e07a2f', weight: 3 }}).addTo(map);
if (polyline.length) map.fitBounds(L.latLngBounds(polyline), {{ padding: [24, 24] }});

// timeline
const tl = document.getElementById('timeline');
let lastDay = '';
stops.forEach(s => {{
  const day = s.start.slice(0, 10);
  if (day !== lastDay) {{
    const d = document.createElement('div');
    d.className = 'day-divider'; d.textContent = day;
    tl.appendChild(d); lastDay = day;
  }}
  const el = document.createElement('div');
  el.className = 'stop';
  const when = s.end === s.start ? s.start.slice(11) : s.start.slice(11) + ' – ' + s.end.slice(11);
  el.innerHTML = `<h3>${{s.name}}</h3><div class="when">${{when}}</div><div class="stats">📷 ${{s.photo_count}} · 🎬 ${{s.video_count}} · ${{s.duration_min}} min</div>`;
  tl.appendChild(el);
}});
</script>
</body>
</html>
"""


def write_outputs(stops: list[dict], summary: dict, out_dir: Path) -> dict:
    """Write timeline.json and map.html into out_dir. Returns paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": summary,
        "stops": stops,
    }
    json_path = out_dir / "timeline.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    named = [s for s in stops if s["lat"] is not None]
    if named:
        center = [
            round(sum(s["lat"] for s in named) / len(named), 5),
            round(sum(s["lon"] for s in named) / len(named), 5),
        ]
        zoom = 7
    else:
        center, zoom = [64.5, -19.5], 6

    summary_line = (
        f"{summary['total']} files · {len(stops)} stops · "
        f"{summary.get('first_date', '?')[:10]} → {summary.get('last_date', '?')[:10]}"
    )
    html = MAP_TEMPLATE.format(
        title="Iceland trip tracker",
        summary=summary_line,
        css=LEAFLET_CSS,
        js=LEAFLET_JS,
        tiles=TILE_URL,
        stops_json=json.dumps(stops, ensure_ascii=False),
        center=center,
        zoom=zoom,
    )
    map_path = out_dir / "map.html"
    map_path.write_text(html)

    return {"timeline": str(json_path), "map": str(map_path)}
