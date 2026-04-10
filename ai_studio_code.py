import json
import ssl
import time
import urllib.request


context = ssl._create_unverified_context()


def fetch_anilist_year(year):
    print(f"\n{'=' * 60}")
    print(f" Fetching AniList Top 30 for {year}")
    print(f"{'=' * 60}")

    url = "https://graphql.anilist.co"
    query = """
    query ($year: Int) {
      Page(page: 1, perPage: 30) {
        media(seasonYear: $year, type: ANIME, sort: POPULARITY_DESC) {
          id
          title {
            native
            romaji
          }
          coverImage {
            large
          }
        }
      }
    }
    """

    variables = {"year": year}
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, context=context, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            media_list = res_data["data"]["Page"]["media"]

        year_results = []
        for index, item in enumerate(media_list, 1):
            title = item["title"]["native"] or item["title"]["romaji"]
            anime_id = item["id"]
            cover_url = item["coverImage"]["large"]
            print(f"[{index:02d}] ID: {anime_id:<7} | {title}")
            year_results.append({
                "id": anime_id,
                "title": title,
                "cover": cover_url,
            })

        if not year_results:
            print(f"No items returned for {year}.")

        return year_results
    except Exception as exc:
        print(f"Failed to fetch {year}: {exc}")
        return []


def main():
    all_data = []
    start_year = 1998
    end_year = 2026

    for year in range(start_year, end_year + 1):
        year_animes = fetch_anilist_year(year)
        all_data.append({
            "year": year,
            "animes": year_animes,
        })
        time.sleep(1.2)

    output_file = "anime_data.json"
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(all_data, file, ensure_ascii=False, indent=4)

    print(f"\n{'*' * 60}")
    print(f"Saved anime data to: {output_file}")
    print(f"{'*' * 60}")


if __name__ == "__main__":
    main()
