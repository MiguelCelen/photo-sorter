# Photo Sorter

A small Python tool that sorts and renames my drone photos by the date they were taken.

After a flight, my photos come off the drone with names like `DJI_0042.JPG`, all in one folder. This tool reads the capture date from each photo's EXIF data and files it as:

```
sorted/
└── 2026/
    └── 2026-11-03/
        ├── 2026-11-03_07-24-17.jpg
        ├── 2026-11-03_07-24-29.jpg
        └── 2026-11-03_13-05-46.jpg
```

It started as a pet project from my Python course, and it is part of my portfolio at [miguelcelen.be](https://miguelcelen.be).

## Features

- **Date from EXIF:** uses `DateTimeOriginal`. Falls back to the file date when a photo has none, and says so in the log.
- **Safe by default:** copies the photos and keeps the originals. Use `--move` only when you are sure.
- **Dry run:** `--dry-run` shows what would happen without touching a file.
- **No duplicates:** two photos taken in the same second get `_2`, `_3` ... An identical photo that is already sorted is skipped.
- **Drone filter:** `--drone-only` keeps only photos made by a drone (DJI, Autel, Parrot, Skydio, Yuneec), so phone photos from the same day stay out.
- **Log:** every run writes a CSV with the old name, new name, date, camera and action.

## Install

Requires Python 3.10 or newer.

```bash
git clone https://github.com/<your-username>/photo-sorter.git
cd photo-sorter
pip install -r requirements.txt
```

## Use

```bash
# See what would happen
python photo_sorter.py ~/Pictures/drone-import ~/Pictures/sorted --dry-run

# Copy and rename
python photo_sorter.py ~/Pictures/drone-import ~/Pictures/sorted

# Only the drone photos
python photo_sorter.py ~/Pictures/drone-import ~/Pictures/sorted --drone-only
```

Supported files: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.dng`.

## Tests

```bash
pip install pytest
python -m pytest
```

The tests create small fake photos with EXIF data, so no personal photos are needed.

## Next steps

- HEIC support for iPhone photos (with `pillow-heif`)
- Sort by location from the GPS data, for example per municipality
- A simple interface to pick the folders

## License

MIT
