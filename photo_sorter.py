#!/usr/bin/env python3
"""Sort and rename photos by the date they were taken.

Reads the capture date from each photo's EXIF data (DateTimeOriginal),
then copies (or moves) the photo to DEST/YYYY/YYYY-MM-DD/ and renames it
to YYYY-MM-DD_HH-MM-SS.ext. Built for drone photos, but it works for any
camera. Originals are copied by default, so nothing is lost.

Usage:
    python photo_sorter.py SOURCE DEST [--move] [--dry-run] [--drone-only]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng"}
EXIF_IFD = 0x8769
TAG_DATETIME_ORIGINAL = 36867   # DateTimeOriginal
TAG_DATETIME = 306              # DateTime (fallback inside EXIF)
TAG_MAKE = 271
TAG_MODEL = 272
DRONE_MAKERS = ("dji", "autel", "parrot", "skydio", "yuneec")


@dataclass
class PhotoInfo:
    path: Path
    taken: datetime
    date_source: str   # "exif" or "file"
    camera: str

    @property
    def is_drone(self) -> bool:
        return self.camera.lower().startswith(DRONE_MAKERS)


def read_photo_info(path: Path) -> PhotoInfo:
    """Return the capture date and camera of a photo.

    Falls back to the file's modification time when the photo has no
    usable EXIF date (for example screenshots or edited exports).
    """
    taken, camera = None, "unknown"
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            sub = exif.get_ifd(EXIF_IFD)
            raw = sub.get(TAG_DATETIME_ORIGINAL) or exif.get(TAG_DATETIME)
            if raw:
                taken = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
            make = str(exif.get(TAG_MAKE, "")).strip()
            model = str(exif.get(TAG_MODEL, "")).strip()
            camera = " ".join(p for p in (make, model) if p) or "unknown"
    except (OSError, ValueError):
        pass  # unreadable image or malformed date: use the file date below

    if taken is None:
        return PhotoInfo(path, datetime.fromtimestamp(path.stat().st_mtime), "file", camera)
    return PhotoInfo(path, taken, "exif", camera)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def target_path(info: PhotoInfo, dest: Path) -> Path:
    """DEST/YYYY/YYYY-MM-DD/YYYY-MM-DD_HH-MM-SS.ext"""
    folder = dest / f"{info.taken:%Y}" / f"{info.taken:%Y-%m-%d}"
    return folder / f"{info.taken:%Y-%m-%d_%H-%M-%S}{info.path.suffix.lower()}"


def unique_path(candidate: Path, source: Path, planned: set[Path]) -> Path | None:
    """Add _2, _3 ... when the name is taken.

    Returns None when an identical file already sits at one of those names,
    so the same photo is never stored twice.
    """
    stem, suffix, n = candidate.stem, candidate.suffix, 1
    path = candidate
    while path in planned or path.exists():
        if path.exists() and path not in planned and file_hash(path) == file_hash(source):
            return None
        n += 1
        path = candidate.with_name(f"{stem}_{n}{suffix}")
    return path


def find_photos(source: Path) -> list[Path]:
    return sorted(p for p in source.rglob("*")
                  if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS)


def sort_photos(source: Path, dest: Path, move: bool = False, dry_run: bool = False,
                drone_only: bool = False) -> list[dict]:
    rows, planned = [], set()
    infos = sorted((read_photo_info(p) for p in find_photos(source)), key=lambda i: i.taken)
    for info in infos:
        row = {"original": str(info.path.relative_to(source)),
               "taken": info.taken.isoformat(sep=" "),
               "date_source": info.date_source, "camera": info.camera}
        if drone_only and not info.is_drone:
            rows.append({**row, "new": "", "action": "skipped (not a drone photo)"})
            continue
        new = unique_path(target_path(info, dest), info.path, planned)
        if new is None:
            rows.append({**row, "new": "", "action": "skipped (duplicate)"})
            continue
        planned.add(new)
        action = "move" if move else "copy"
        if not dry_run:
            new.parent.mkdir(parents=True, exist_ok=True)
            (shutil.move if move else shutil.copy2)(str(info.path), str(new))
        rows.append({**row, "new": str(new.relative_to(dest)),
                     "action": f"{action} (dry run)" if dry_run else action})
    return rows


def write_log(rows: list[dict], dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    log = dest / f"photo_sorter_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with log.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["original", "new", "taken", "date_source", "camera", "action"])
        w.writeheader()
        w.writerows(rows)
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sort and rename photos by the date they were taken.")
    ap.add_argument("source", type=Path, help="folder with photos (subfolders included)")
    ap.add_argument("dest", type=Path, help="folder for the sorted photos")
    ap.add_argument("--move", action="store_true", help="move instead of copy (originals are removed)")
    ap.add_argument("--dry-run", action="store_true", help="only show what would happen")
    ap.add_argument("--drone-only", action="store_true", help="only photos made by a drone (DJI, Autel ...)")
    args = ap.parse_args(argv)

    if not args.source.is_dir():
        print(f"Source folder not found: {args.source}", file=sys.stderr)
        return 1
    if args.dest.resolve().is_relative_to(args.source.resolve()):
        print("Destination may not be inside the source folder.", file=sys.stderr)
        return 1

    rows = sort_photos(args.source, args.dest, args.move, args.dry_run, args.drone_only)
    for r in rows:
        print(f"{r['action']:<28} {r['original']}  ->  {r['new'] or '-'}   [{r['camera']}, date from {r['date_source']}]")
    done = sum(1 for r in rows if r["new"])
    print(f"\n{done} of {len(rows)} photos {'would be ' if args.dry_run else ''}sorted.")
    if not args.dry_run and rows:
        print(f"Log: {write_log(rows, args.dest)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
