"""extract — turn a photo export into a normalized photo directory.

Supports Google Takeout zips and iCloud "Download All" zips (flat IMG_* dumps).
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

PHOTO_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}
SIDECAR_EXTS = {".json"}  # Google Takeout sidecars

ALL_EXTS = PHOTO_EXTS | VIDEO_EXTS | SIDECAR_EXTS


def is_media(path: Path) -> bool:
    return path.suffix.lower() in ALL_EXTS


def extract_zip(zip_path: Path, out_dir: Path, keep_sidecars: bool = True) -> int:
    """Unpack a photo zip into out_dir. Returns number of files extracted."""
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            suffix = Path(member.filename).suffix.lower()
            if suffix not in ALL_EXTS:
                continue
            if not keep_sidecars and suffix == ".json":
                continue
            # strip ../ and absolute paths (zip-slip guard)
            target = (out_dir / member.filename).resolve()
            if not str(target).startswith(str(out_dir.resolve())):
                continue
            zf.extract(member, out_dir)
            count += 1
    return count


def copy_dir(src: Path, out_dir: Path) -> int:
    """Copy media files from an already-extracted directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in src.rglob("*"):
        if f.is_file() and is_media(f):
            rel = f.relative_to(src)
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            count += 1
    return count


def extract(source: Path, out_dir: Path, keep_sidecars: bool = True) -> int:
    if source.is_file() and source.suffix.lower() == ".zip":
        return extract_zip(source, out_dir, keep_sidecars)
    if source.is_dir():
        return copy_dir(source, out_dir)
    raise FileNotFoundError(f"source is neither a zip nor a directory: {source}")
