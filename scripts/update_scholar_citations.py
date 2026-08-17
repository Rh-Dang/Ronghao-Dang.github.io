"""Update the citation count cached by the static personal website."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


SCHOLAR_ID = "3MGeRMUAAAAJ"
PROFILE_URL = (
    "https://scholar.google.com/citations?"
    f"user={SCHOLAR_ID}&hl=en"
)
OUTPUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "scholar.json"
FETCH_URLS = (
    ("Google Scholar", PROFILE_URL),
    (
        "Google Scholar UK",
        f"https://scholar.google.co.uk/citations?user={SCHOLAR_ID}&hl=en",
    ),
    (
        "Google Scholar Canada",
        f"https://scholar.google.ca/citations?user={SCHOLAR_ID}&hl=en",
    ),
    # Scholar often rejects GitHub-hosted runners. AllOrigins performs the
    # same public, read-only request from a different network and needs no key.
    (
        "Google Scholar via AllOrigins",
        "https://api.allorigins.win/raw?url="
        + urllib.parse.quote(PROFILE_URL, safe=""),
    ),
)


def download(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_citations(html: str) -> int:
    # The first value in the Scholar statistics table is the all-time
    # citation count. Require the table marker as a guard against consent,
    # CAPTCHA, or other unexpected pages.
    if not re.search(r'id=["\']gsc_rsb_st["\']', html):
        raise ValueError("Scholar statistics table was not found")

    values = re.findall(
        r'<td\b[^>]*class=["\'][^"\']*\bgsc_rsb_std\b[^"\']*["\'][^>]*>'
        r"\s*([0-9][0-9,]*)\s*</td>",
        html,
        flags=re.IGNORECASE,
    )
    if not values:
        raise ValueError("Citation count was not found")
    return int(values[0].replace(",", ""))


def fetch_citations() -> tuple[int, str]:
    errors: list[str] = []
    for index, (source, url) in enumerate(FETCH_URLS):
        try:
            return extract_citations(download(url)), source
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            errors.append(f"{source}: {error}")
            if index < len(FETCH_URLS) - 1:
                time.sleep(2)
    raise RuntimeError("; ".join(errors))


def read_cache() -> dict[str, object]:
    try:
        cached = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return cached if isinstance(cached, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    cached = read_cache()
    try:
        citations, fetch_method = fetch_citations()
    except Exception as error:  # Preserve the previous valid cache on failure.
        cached_citations = cached.get("citations")
        if isinstance(cached_citations, int) and cached_citations >= 0:
            print(
                f"Scholar update skipped; keeping cached value "
                f"{cached_citations}: {error}",
                file=sys.stderr,
            )
            return 0
        print(f"Scholar update failed and no valid cache exists: {error}", file=sys.stderr)
        return 1

    if cached.get("citations") == citations:
        print(f"Scholar citations unchanged: {citations} ({fetch_method})")
        return 0

    payload = {
        "scholar_id": SCHOLAR_ID,
        "citations": citations,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "Google Scholar",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Updated Scholar citations: {citations} ({fetch_method})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
