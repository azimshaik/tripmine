"""metadata — read dates + GPS from photos/videos via exiftool (batch, no deps)."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

EXIFTOOL_FIELDS = [
    "DateTimeOriginal",
    "CreateDate",
    "GPSLatitude",
    "GPSLongitude",
    "Model",
    "Make",
    "FileType",
    "MediaDuration",
]

DATE_FORMATS = (
    "%Y:%m:%d %H:%M:%S",
    "%Y:%m:%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None


def read_all(directory: Path) -> list[dict]:
    """Batch-read EXIF/metadata for every media file in directory (recursive).

    Returns records: {path, source, ts, lat, lon, model, filetype, duration}
    ts is a datetime, lat/lon floats or None.
    """
    cmd = [
        "exiftool",
        "-r", "-json", "-n", "-q",
        "-DateTimeOriginal", "-CreateDate", "-GPSLatitude", "-GPSLongitude",
        "-Model", "-Make", "-FileType", "-FileModifyDate", "-MediaDuration",
        str(directory),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise RuntimeError(f"exiftool batch read failed: {e}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"exiftool error: {proc.stderr[:500]}")

    records: list[dict] = []
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("exiftool produced invalid JSON")

    for item in raw:
        path = item.get("SourceFile", "")
        if not path:
            continue
        ts = _parse_ts(item.get("DateTimeOriginal")) or _parse_ts(item.get("CreateDate"))
        lat = _coord(item.get("GPSLatitude"))
        lon = _coord(item.get("GPSLongitude"))
        records.append(
            {
                "path": path,
                "source": Path(path).name,
                "ts": ts,
                "lat": lat,
                "lon": lon,
                "model": item.get("Model") or item.get("Make") or "",
                "filetype": item.get("FileType") or Path(path).suffix.lstrip(".").upper(),
                "duration": _duration(item.get("MediaDuration")) if "MediaDuration" in item else None,
            }
        )
    return records


def _coord(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _duration(value) -> float | None:
    if not value:
        return None
    try:
        # exiftool -n MediaDuration gives seconds as float
        return float(value)
    except (TypeError, ValueError):
        return None
