"""Import personal cat photos into ``data/raw/personal/my_pets/`` for labelling.

Browsers can't display HEIC (iPhone) photos, so HEIC/HEIF files are converted to JPEG.
Other images are copied as-is. Videos and other files are skipped and reported.
The source folder is never modified. Re-running is safe: existing targets are skipped.

Usage::

    uv run python -m sunnynui.data.import_photos ~/Downloads/pets
"""

from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

HEIC_EXTS = {".heic", ".heif"}
COPY_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
DEFAULT_DEST = Path("data/raw/personal/my_pets")
JPEG_QUALITY = 92


def convert_heic(src: Path, dest: Path) -> None:
    with Image.open(src) as img:
        # bake EXIF rotation into the pixels so every viewer shows the photo upright
        ImageOps.exif_transpose(img).convert("RGB").save(dest, "JPEG", quality=JPEG_QUALITY)


def import_photos(src: Path, dest: Path) -> Counter:
    """Import every image below ``src`` (recursively) flat into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    stats: Counter = Counter()
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        ext = path.suffix.lower()
        if ext in HEIC_EXTS:
            target = dest / f"{path.stem}.jpg"
        elif ext in COPY_EXTS:
            target = dest / path.name
        else:
            stats[f"skipped {ext or '(no ext)'}"] += 1
            continue
        if target.exists():
            stats["already imported"] += 1
            continue
        try:
            if ext in HEIC_EXTS:
                convert_heic(path, target)
                stats["converted heic"] += 1
            else:
                shutil.copy2(path, target)
                stats["copied"] += 1
        except OSError as exc:
            target.unlink(missing_ok=True)
            stats["failed"] += 1
            print(f"failed: {path.name}: {exc}")
    return stats


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("src", type=Path, help="downloaded photos (recursive)")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args(argv)
    if not args.src.is_dir():
        parser.exit(1, f"Not a folder: {args.src}\n")
    stats = import_photos(args.src, args.dest)
    for key, n in sorted(stats.items()):
        print(f"{key:>20}: {n}")
    print(f"-> {args.dest.resolve()}")


if __name__ == "__main__":
    main()
