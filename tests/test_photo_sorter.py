from datetime import datetime
from pathlib import Path
import os
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import photo_sorter as ps  # noqa: E402


def make_photo(path: Path, taken: str | None, make: str = "DJI", model: str = "FC3582", color=(90, 140, 200)):
    img = Image.new("RGB", (64, 48), color)
    exif = Image.Exif()
    exif[ps.TAG_MAKE] = make
    exif[ps.TAG_MODEL] = model
    if taken:
        exif.get_ifd(ps.EXIF_IFD)[ps.TAG_DATETIME_ORIGINAL] = taken
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, exif=exif)
    return path


def test_reads_exif_date_and_camera(tmp_path):
    p = make_photo(tmp_path / "DJI_0001.JPG", "2026:11:03 07:24:29")
    info = ps.read_photo_info(p)
    assert info.taken == datetime(2026, 11, 3, 7, 24, 29)
    assert info.date_source == "exif"
    assert info.camera == "DJI FC3582" and info.is_drone


def test_falls_back_to_file_date(tmp_path):
    p = make_photo(tmp_path / "scan.jpg", None, make="", model="")
    os.utime(p, (1700000000, 1700000000))
    info = ps.read_photo_info(p)
    assert info.date_source == "file"
    assert info.taken == datetime.fromtimestamp(1700000000)


def test_copies_into_date_folders_and_keeps_originals(tmp_path):
    src, dest = tmp_path / "in", tmp_path / "out"
    make_photo(src / "a.JPG", "2026:11:03 13:05:46")
    make_photo(src / "sub" / "b.jpg", "2026:10:21 09:00:00", color=(10, 10, 10))
    rows = ps.sort_photos(src, dest)
    assert (dest / "2026/2026-11-03/2026-11-03_13-05-46.jpg").exists()
    assert (dest / "2026/2026-10-21/2026-10-21_09-00-00.jpg").exists()
    assert (src / "a.JPG").exists(), "copy mode must keep the original"
    assert [r["action"] for r in rows] == ["copy", "copy"]


def test_same_second_gets_suffix(tmp_path):
    src, dest = tmp_path / "in", tmp_path / "out"
    make_photo(src / "a.jpg", "2026:11:03 13:05:46", color=(1, 2, 3))
    make_photo(src / "b.jpg", "2026:11:03 13:05:46", color=(200, 2, 3))
    ps.sort_photos(src, dest)
    day = dest / "2026/2026-11-03"
    assert sorted(p.name for p in day.iterdir()) == ["2026-11-03_13-05-46.jpg", "2026-11-03_13-05-46_2.jpg"]


def test_skips_identical_file_already_sorted(tmp_path):
    src, dest = tmp_path / "in", tmp_path / "out"
    make_photo(src / "a.jpg", "2026:11:03 13:05:46")
    ps.sort_photos(src, dest)
    rows = ps.sort_photos(src, dest)
    assert rows[0]["action"] == "skipped (duplicate)"


def test_dry_run_changes_nothing(tmp_path):
    src, dest = tmp_path / "in", tmp_path / "out"
    make_photo(src / "a.jpg", "2026:11:03 13:05:46")
    rows = ps.sort_photos(src, dest, dry_run=True)
    assert not dest.exists() and rows[0]["action"] == "copy (dry run)"


def test_drone_only_skips_phone_photos(tmp_path):
    src, dest = tmp_path / "in", tmp_path / "out"
    make_photo(src / "drone.jpg", "2026:11:03 10:00:00")
    make_photo(src / "phone.jpg", "2026:11:03 11:00:00", make="Apple", model="iPhone 16 Pro")
    rows = {r["original"]: r["action"] for r in ps.sort_photos(src, dest, drone_only=True)}
    assert rows == {"drone.jpg": "copy", "phone.jpg": "skipped (not a drone photo)"}


def test_move_removes_original(tmp_path):
    src, dest = tmp_path / "in", tmp_path / "out"
    make_photo(src / "a.jpg", "2026:11:03 13:05:46")
    ps.sort_photos(src, dest, move=True)
    assert not (src / "a.jpg").exists()


def test_refuses_destination_inside_source(tmp_path):
    src = tmp_path / "in"
    make_photo(src / "a.jpg", "2026:11:03 13:05:46")
    assert ps.main([str(src), str(src / "sorted")]) == 1
