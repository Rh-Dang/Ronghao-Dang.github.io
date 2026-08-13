"""Update the citation count cached by the static personal website."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request


SCHOLAR_ID = "3MGeRMUAAAAJ"
PROFILE_URL = (
    "https://scholar.google.com/citations?"
    f"user={SCHOLAR_ID}&hl=en&view_op=list_works&sortby=pubdate"
)
OUTPUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "scholar.json"


def download_profile() -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            request = urllib.request.Request(PROFILE_URL, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(2**attempt)

    raise RuntimeError(f"Unable to download Scholar profile: {last_error}")


def extract_citations(html: str) -> int:
    # The first value in the Scholar statistics table is the all-time
    # citation count. Require the table marker as a guard against consent,
    # CAPTCHA, or other unexpected pages.
    if "gsc_rsb_st" not in html:
        raise ValueError("Scholar statistics table was not found")

    values = re.findall(r'<td class="gsc_rsb_std">\s*([0-9][0-9,]*)\s*</td>', html)
    if not values:
        raise ValueError("Citation count was not found")
    return int(values[0].replace(",", ""))


def main() -> int:
    try:
        citations = extract_citations(download_profile())
    except Exception as error:  # Preserve the previous valid cache on failure.
        print(f"Scholar update skipped: {error}", file=sys.stderr)
        return 1

    payload = {
        "scholar_id": SCHOLAR_ID,
        "citations": citations,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "Google Scholar",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Updated Scholar citations: {citations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
