import argparse
import io
import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


BG_COLOR = "#0f172a"
CARD_BG = "#1e293b"
TEXT_COLOR = "#f8fafc"
MUTED_TEXT = "#94a3b8"
ACCENT = "#ec4899"
BORDER = "#334155"
PLACEHOLDER = "#475569"

CARD_WIDTH = 150
CARD_HEIGHT = 210
TITLE_HEIGHT = 54
CARD_GAP = 14
PAGE_PADDING = 32
SECTION_GAP = 28
HEADER_HEIGHT = 116
YEAR_HEIGHT = 38
FOOTER_HEIGHT = 28
DEFAULT_COLUMNS = 6


@dataclass
class Anime:
    anime_id: int
    title: str
    cover: str
    year: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a long image from anime_data.json and watched IDs.")
    parser.add_argument("--data-file", default="anime_data.json", help="Path to anime data JSON.")
    parser.add_argument("--ids-file", default="watched_ids.json", help="Path to watched IDs JSON.")
    parser.add_argument("--output", default="anime-long.png", help="Output PNG path.")
    parser.add_argument("--mode", choices=("watched", "full"), default="watched", help="Render watched items or the full dataset.")
    parser.add_argument("--columns", type=int, default=DEFAULT_COLUMNS, help="Cards per row.")
    parser.add_argument("--cache-dir", default=".cache/covers", help="Directory used to cache downloaded covers.")
    return parser.parse_args()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_watched_ids(path: Path) -> list[int]:
    payload = load_json(path)
    if isinstance(payload, list):
        ids = payload
    elif isinstance(payload, dict):
        ids = payload.get("watchedIds", [])
    else:
        raise ValueError("Unsupported watched IDs JSON structure.")
    return sorted({int(item) for item in ids})


def load_anime_groups(path: Path) -> list[tuple[int, list[Anime]]]:
    payload = load_json(path)
    groups: list[tuple[int, list[Anime]]] = []
    for year_group in payload:
        year = int(year_group["year"])
        animes = [
            Anime(
                anime_id=int(item["id"]),
                title=str(item["title"]),
                cover=str(item.get("cover", "")),
                year=year,
            )
            for item in year_group.get("animes", [])
        ]
        groups.append((year, animes))
    return groups


def pick_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf" if bold else "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def measure_text(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_title(draw: ImageDraw.ImageDraw, title: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    if not title:
        return [""]

    lines: list[str] = []
    current = ""
    for char in title:
        candidate = current + char
        width, _ = measure_text(draw, candidate, font)
        if current and width > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate

    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return lines

    trimmed = lines[:max_lines]
    last = trimmed[-1]
    while last:
        width, _ = measure_text(draw, f"{last}...", font)
        if width <= max_width:
            trimmed[-1] = f"{last}..."
            return trimmed
        last = last[:-1]
    trimmed[-1] = "..."
    return trimmed


def safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


def download_cover(url: str, cache_path: Path) -> bytes:
    if cache_path.exists():
        return cache_path.read_bytes()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(data)
    return data


def build_cover_image(anime: Anime, cache_dir: Path) -> Image.Image:
    if not anime.cover:
        return Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), PLACEHOLDER)

    try:
        if anime.cover.startswith(("http://", "https://")):
            suffix = Path(urllib.parse.urlparse(anime.cover).path).suffix or ".img"
            cache_name = f"{anime.anime_id}_{safe_filename(str(anime.year))}{suffix}"
            cache_path = cache_dir / cache_name
            raw = download_cover(anime.cover, cache_path)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        else:
            local_path = Path(anime.cover)
            image = Image.open(local_path).convert("RGB")
        return ImageOps.fit(image, (CARD_WIDTH, CARD_HEIGHT), method=Image.Resampling.LANCZOS)
    except Exception:
        return Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), PLACEHOLDER)


def build_sections(anime_groups: list[tuple[int, list[Anime]]], watched_ids: set[int], mode: str) -> list[tuple[int, list[Anime]]]:
    sections: list[tuple[int, list[Anime]]] = []
    for year, animes in anime_groups:
        items = [anime for anime in animes if mode == "full" or anime.anime_id in watched_ids]
        if items:
            sections.append((year, items))
    return sections


def calculate_height(item_counts: Iterable[int], columns: int) -> int:
    height = PAGE_PADDING + HEADER_HEIGHT
    for count in item_counts:
        rows = max(1, math.ceil(count / columns))
        height += YEAR_HEIGHT
        height += rows * (CARD_HEIGHT + TITLE_HEIGHT)
        height += max(0, rows - 1) * CARD_GAP
        height += SECTION_GAP
    height += FOOTER_HEIGHT
    return height


def draw_card(canvas: Image.Image, draw: ImageDraw.ImageDraw, anime: Anime, x: int, y: int, title_font, cover_cache_dir: Path) -> None:
    cover = build_cover_image(anime, cover_cache_dir)
    canvas.paste(cover, (x, y))

    title_y = y + CARD_HEIGHT
    draw.rounded_rectangle(
        (x, title_y, x + CARD_WIDTH, title_y + TITLE_HEIGHT),
        radius=10,
        fill=CARD_BG,
        outline=BORDER,
        width=1,
    )

    lines = wrap_title(draw, anime.title, title_font, CARD_WIDTH - 16, max_lines=2)
    line_y = title_y + 10
    for line in lines:
        line_width, _ = measure_text(draw, line, title_font)
        draw.text((x + (CARD_WIDTH - line_width) / 2, line_y), line, fill=TEXT_COLOR, font=title_font)
        line_y += 16


def generate_image(args: argparse.Namespace) -> Path:
    data_file = Path(args.data_file)
    ids_file = Path(args.ids_file)
    output_file = Path(args.output)
    cache_dir = Path(args.cache_dir)

    anime_groups = load_anime_groups(data_file)
    watched_ids = set(load_watched_ids(ids_file)) if args.mode == "watched" else set()
    sections = build_sections(anime_groups, watched_ids, args.mode)
    if not sections:
        raise ValueError("No anime found for the selected mode.")

    columns = max(1, args.columns)
    width = PAGE_PADDING * 2 + columns * CARD_WIDTH + (columns - 1) * CARD_GAP
    height = calculate_height((len(items) for _, items in sections), columns)

    canvas = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(canvas)
    title_font = pick_font(28, bold=True)
    meta_font = pick_font(18)
    year_font = pick_font(24, bold=True)
    card_font = pick_font(14, bold=True)
    footer_font = pick_font(13)

    total_count = sum(len(items) for _, items in sections)
    header_title = "动画番剧阅历清单" if args.mode == "watched" else "动画番剧总览长图"
    draw.text((PAGE_PADDING, PAGE_PADDING), header_title, fill=ACCENT, font=title_font)
    draw.text((PAGE_PADDING, PAGE_PADDING + 42), f"Count: {total_count}", fill=TEXT_COLOR, font=meta_font)
    draw.text(
        (PAGE_PADDING, PAGE_PADDING + 70),
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        fill=MUTED_TEXT,
        font=footer_font,
    )
    draw.line(
        (PAGE_PADDING, PAGE_PADDING + HEADER_HEIGHT - 14, width - PAGE_PADDING, PAGE_PADDING + HEADER_HEIGHT - 14),
        fill=BORDER,
        width=1,
    )

    cursor_y = PAGE_PADDING + HEADER_HEIGHT
    for year, items in sections:
        draw.text((PAGE_PADDING, cursor_y), f"# {year}", fill=TEXT_COLOR, font=year_font)
        cursor_y += YEAR_HEIGHT

        for index, anime in enumerate(items):
            row = index // columns
            col = index % columns
            x = PAGE_PADDING + col * (CARD_WIDTH + CARD_GAP)
            y = cursor_y + row * (CARD_HEIGHT + TITLE_HEIGHT + CARD_GAP)
            draw_card(canvas, draw, anime, x, y, card_font, cache_dir)

        rows = math.ceil(len(items) / columns)
        cursor_y += rows * (CARD_HEIGHT + TITLE_HEIGHT) + max(0, rows - 1) * CARD_GAP + SECTION_GAP

    draw.text((PAGE_PADDING, height - FOOTER_HEIGHT), f"Output: {output_file.name}", fill=MUTED_TEXT, font=footer_font)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_file, format="PNG")
    return output_file


def main() -> None:
    args = parse_args()
    output = generate_image(args)
    print(f"Image written to: {output}")


if __name__ == "__main__":
    main()
