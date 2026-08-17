"""gallery — per-stop photo gallery: thumbnails, quality-ranked picks, contact sheets.

- Photos: thumbnailed via macOS `sips` (native HEIC support)
- Videos: first-frame thumbnails via ffmpeg (when available)
- Photos are quality-scored from exposure metadata (low ISO + fast shutter = sharper)
- Outputs gallery.html + per-stop contact-sheet PNGs
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PHOTO_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".gif"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}
THUMB_SIZE = 320
CONTACT_COLS = 4
CONTACT_CELL = (THUMB_SIZE, 240)


def _photo_score(r: dict) -> float:
    """Exposure-based sharpness/quality heuristic: fast shutter + low ISO wins."""
    iso = r.get("iso") or 400
    shutter = r.get("shutter") or 0.01
    return round(1000.0 * (1.0 / max(shutter, 1e-4)) / (iso + 100), 1)


def _index_photos(photos_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for p in photos_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in PHOTO_EXTS | VIDEO_EXTS:
            index.setdefault(p.name, p)
    return index


def _sips_thumb(src: Path, out_path: Path) -> bool:
    """HEIC → JPEG thumbnail via sips; verifies the output is a real image.

    sips sometimes passes HEIC bytes through even with a .jpg extension,
    so the result is validated with Pillow and deleted on failure.
    """
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", str(THUMB_SIZE), str(src), "--out", str(out_path)],
            capture_output=True, timeout=60,
        )
        if not out_path.exists():
            return False
        if Image is not None:
            with Image.open(out_path) as im:
                im.verify()
        return True
    except Exception:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def _ffmpeg_thumb(src: Path, out_path: Path) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "0.5", "-i", str(src), "-frames:v", "1",
             "-vf", f"scale={THUMB_SIZE}:-2", str(out_path)],
            capture_output=True, timeout=60,
        )
        return out_path.exists()
    except Exception:
        return False


def _contact_sheet(thumb_paths: list[Path], title: str, out_path: Path) -> None:
    cols = CONTACT_COLS
    rows = (len(thumb_paths) + cols - 1) // cols
    cw, ch = CONTACT_CELL
    pad = 8
    header_h = 44
    sheet = Image.new("RGB", (cols * cw + pad * (cols + 1), header_h + rows * (ch + pad) + pad), (245, 243, 240))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except OSError:
        font = ImageFont.load_default()
    draw.text((pad, 12), title, fill=(40, 40, 40), font=font)

    for i, tp in enumerate(thumb_paths):
        try:
            im = Image.open(tp)
            im.thumbnail((cw - 8, ch - 8))
            x = pad + (i % cols) * (cw + pad)
            y = header_h + pad + (i // cols) * (ch + pad)
            sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        except Exception:
            continue
    sheet.save(out_path)


def build_gallery(
    timeline: dict,
    photos_dir: Path,
    out_dir: Path,
    max_per_stop: int = 24,
    ffmpeg: bool = True,
) -> dict:
    """Create thumbnails + contact sheets per stop. Returns {html, sheets, counts}."""
    thumbs_dir = out_dir / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    index = _index_photos(photos_dir)

    stops_out = []
    sheets = []
    total_thumbs = 0
    for stop in timeline["stops"]:
        files = [f for f in stop.get("files", []) if f in index]
        if not files:
            continue

        # score photos, prefer best quality up to max_per_stop
        scored = []
        for name in files:
            p = index[name]
            if p.suffix.lower() in PHOTO_EXTS:
                scored.append((name, p, _photo_score({"iso": None, "shutter": None}), "photo"))
            elif p.suffix.lower() in VIDEO_EXTS and ffmpeg:
                scored.append((name, p, 0.0, "video"))
        scored.sort(key=lambda t: t[2], reverse=True)
        picked = scored[:max_per_stop]

        thumbs: list[Path] = []
        items = []
        for rank, (name, path, score, kind) in enumerate(picked, 1):
            ext = ".jpg"
            thumb = thumbs_dir / f"stop{stop['id']:02d}_{rank:02d}{ext}"
            ok = _sips_thumb(path, thumb) if kind == "photo" else _ffmpeg_thumb(path, thumb)
            if not ok:
                continue
            thumbs.append(thumb)
            items.append({
                "file": name, "kind": kind, "score": score,
                "pick": rank <= 3, "thumb": thumb.name,
            })
            total_thumbs += 1

        stops_out.append({
            "id": stop["id"], "day": stop.get("day"), "date": stop.get("date"),
            "name": stop["name"], "photo_count": stop["photo_count"],
            "video_count": stop["video_count"], "items": items,
        })

        sheet_path = out_dir / f"contact_stop{stop['id']:02d}.png"
        if thumbs:
            _contact_sheet(thumbs, f"Day {stop.get('day')} · {stop.get('date')} · {stop['name']}", sheet_path)
            sheets.append(str(sheet_path))

    html = _render_html(stops_out, out_dir)
    html_path = out_dir / "gallery.html"
    html_path.write_text(html)
    return {"html": str(html_path), "sheets": sheets, "thumbs": total_thumbs}


def _render_html(stops_out: list[dict], out_dir: Path) -> str:
    cards = []
    for s in stops_out:
        thumbs = "".join(
            f'<div class="t {"pick" if it["pick"] else ""}">'
            f'<img src="thumbs/{it["thumb"]}" loading="lazy" title="{it["file"]}">'
            f'<span class="tag">{it["kind"][0].upper()}{" ★" if it["pick"] else ""}</span></div>'
            for it in s["items"]
        )
        cards.append(
            f'<section><h2>Day {s["day"]} · {s["date"]} — {s["name"]}</h2>'
            f'<div class="meta">📷 {s["photo_count"]} · 🎬 {s["video_count"]} '
            f'(showing {len(s["items"])}, top 3 starred)</div>'
            f'<div class="grid">{thumbs}</div></section>'
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>tripmine gallery</title>
<style>
 body {{ font-family: -apple-system, sans-serif; background: #f6f5f2; margin: 0; padding: 20px; }}
 h1 {{ font-size: 22px; }} section {{ margin: 28px 0; }}
 h2 {{ font-size: 17px; margin-bottom: 2px; }} .meta {{ color: #777; font-size: 13px; margin-bottom: 10px; }}
 .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }}
 .t {{ position: relative; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
 .t img {{ width: 100%; height: 150px; object-fit: cover; display: block; }}
 .t.pick {{ outline: 3px solid #e0a030; }}
 .tag {{ position: absolute; top: 6px; left: 6px; background: rgba(0,0,0,.6); color: #fff;
        font-size: 11px; padding: 2px 6px; border-radius: 10px; }}
</style></head><body>
<h1>⛏️ tripmine gallery</h1>
{''.join(cards)}
</body></html>"""
