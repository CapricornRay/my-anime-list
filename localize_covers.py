import argparse
import json
import ssl
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


DEFAULT_DATA_FILE = "anime_data.json"
DEFAULT_ASSET_DIR = "assets/covers"
DEFAULT_TIMEOUT = 30
DEFAULT_WORKERS = 8


ssl_context = ssl._create_unverified_context()
print_lock = threading.Lock()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download remote anime covers into the repo and rewrite anime_data.json to local relative paths."
    )
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE, help="Input JSON file.")
    parser.add_argument("--output", default=None, help="Output JSON file. Defaults to overwrite --data-file.")
    parser.add_argument("--asset-dir", default=DEFAULT_ASSET_DIR, help="Where to store localized covers.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Concurrent download workers.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Download timeout in seconds.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N anime entries for testing.")
    parser.add_argument(
        "--keep-remote-on-failure",
        action="store_true",
        help="If a cover fails to download, keep the original remote URL instead of clearing it.",
    )
    return parser.parse_args()


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, payload):
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=4)


def normalize_asset_path(path):
    return path.as_posix()


def extension_from_url(url):
    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ext
    return ".jpg"


def is_remote_url(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def build_download_jobs(data, limit):
    jobs = []
    seen_ids = set()

    for year_group in data:
        for anime in year_group.get("animes", []):
            anime_id = anime.get("id")
            cover = anime.get("cover")
            if anime_id in seen_ids:
                continue
            seen_ids.add(anime_id)
            if not is_remote_url(cover):
                continue
            jobs.append({
                "id": anime_id,
                "cover": cover,
            })
            if limit and len(jobs) >= limit:
                return jobs

    return jobs


def download_cover(job, asset_dir, timeout):
    anime_id = job["id"]
    url = job["cover"]
    ext = extension_from_url(url)
    target = asset_dir / f"{anime_id}{ext}"
    relative_target = normalize_asset_path(target)

    if target.exists() and target.stat().st_size > 0:
        return anime_id, relative_target, None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://anilist.co/",
    }

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        payload = response.read()

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return anime_id, relative_target, None


def localize_covers(data, asset_dir, workers, timeout, limit, keep_remote_on_failure):
    jobs = build_download_jobs(data, limit)
    results = {}
    failures = {}

    if not jobs:
        return data, results, failures

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_map = {executor.submit(download_cover, job, asset_dir, timeout): job for job in jobs}
        completed = 0

        for future in as_completed(future_map):
            job = future_map[future]
            anime_id = job["id"]
            completed += 1
            try:
                _, relative_target, _ = future.result()
                results[anime_id] = relative_target
                with print_lock:
                    print(f"[{completed:>4}/{len(jobs)}] localized {anime_id} -> {relative_target}")
            except Exception as exc:
                failures[anime_id] = str(exc)
                with print_lock:
                    print(f"[{completed:>4}/{len(jobs)}] failed {anime_id}: {exc}")

    for year_group in data:
        for anime in year_group.get("animes", []):
            anime_id = anime.get("id")
            original_cover = anime.get("cover")
            if anime_id in results:
                anime["cover_remote"] = original_cover
                anime["cover"] = results[anime_id]
            elif anime_id in failures and not keep_remote_on_failure:
                anime["cover_remote"] = original_cover
                anime["cover"] = ""

    return data, results, failures


def main():
    args = parse_args()
    data_file = Path(args.data_file)
    output_file = Path(args.output) if args.output else data_file
    asset_dir = Path(args.asset_dir)

    data = read_json(data_file)
    updated_data, results, failures = localize_covers(
        data=data,
        asset_dir=asset_dir,
        workers=args.workers,
        timeout=args.timeout,
        limit=args.limit,
        keep_remote_on_failure=args.keep_remote_on_failure,
    )

    write_json(output_file, updated_data)
    print("")
    print(f"Localized covers: {len(results)}")
    print(f"Failed covers: {len(failures)}")
    print(f"Asset dir: {asset_dir.as_posix()}")
    print(f"Output JSON: {output_file.as_posix()}")


if __name__ == "__main__":
    main()
