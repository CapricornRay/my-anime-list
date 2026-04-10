import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps


DEFAULT_DATA_FILE = "anime_data.json"
DEFAULT_COVER_DIR = "assets/covers"
DEFAULT_MAX_WIDTH = 320
DEFAULT_MAX_HEIGHT = 448
DEFAULT_QUALITY = 82


def parse_args():
    parser = argparse.ArgumentParser(
        description="Resize localized covers to lightweight WebP files and rewrite anime_data.json cover paths."
    )
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE, help="Anime data JSON path.")
    parser.add_argument("--cover-dir", default=DEFAULT_COVER_DIR, help="Localized cover directory.")
    parser.add_argument("--max-width", type=int, default=DEFAULT_MAX_WIDTH, help="Max cover width.")
    parser.add_argument("--max-height", type=int, default=DEFAULT_MAX_HEIGHT, help="Max cover height.")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help="WebP quality.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N covers for testing.")
    parser.add_argument(
        "--keep-originals",
        action="store_true",
        help="Keep original jpg/png files after creating WebP versions.",
    )
    return parser.parse_args()


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, payload):
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=4)


def normalize(path):
    return path.as_posix()


def iter_cover_records(data):
    seen = set()
    for year_group in data:
        for anime in year_group.get("animes", []):
            cover = anime.get("cover", "")
            anime_id = anime.get("id")
            if not cover or anime_id in seen:
                continue
            seen.add(anime_id)
            yield anime


def convert_cover(source_path, target_path, max_width, max_height, quality):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        image.save(target_path, format="WEBP", quality=quality, method=6)


def optimize_covers(data, cover_dir, max_width, max_height, quality, limit, keep_originals):
    processed = 0
    total_before = 0
    total_after = 0

    for anime in iter_cover_records(data):
        cover = anime.get("cover", "")
        if cover.startswith(("http://", "https://")):
            continue

        source_path = Path(cover)
        if not source_path.is_absolute():
            source_path = Path(".") / source_path
        if not source_path.exists():
            continue

        total_before += source_path.stat().st_size
        target_path = cover_dir / f"{anime['id']}.webp"
        convert_cover(source_path, target_path, max_width, max_height, quality)
        total_after += target_path.stat().st_size

        if not keep_originals and source_path.resolve() != target_path.resolve() and source_path.exists():
            source_path.unlink()

        anime["cover"] = normalize(target_path)
        processed += 1
        print(f"[{processed}] optimized {anime['id']} -> {normalize(target_path)}")

        if limit and processed >= limit:
            break

    return processed, total_before, total_after


def main():
    args = parse_args()
    data_file = Path(args.data_file)
    cover_dir = Path(args.cover_dir)

    data = load_json(data_file)
    processed, total_before, total_after = optimize_covers(
        data=data,
        cover_dir=cover_dir,
        max_width=args.max_width,
        max_height=args.max_height,
        quality=args.quality,
        limit=args.limit,
        keep_originals=args.keep_originals,
    )
    save_json(data_file, data)

    print("")
    print(f"Processed covers: {processed}")
    print(f"Size before: {round(total_before / 1024 / 1024, 2)} MB")
    print(f"Size after: {round(total_after / 1024 / 1024, 2)} MB")


if __name__ == "__main__":
    main()
