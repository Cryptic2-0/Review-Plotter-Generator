import os
import time
from pathlib import Path

import requests

# ---------- CONFIG ----------

# Template URL – the {} will be replaced with page numbers 1..30
BASE_URL_TEMPLATE = (
    "https://www.shiksha.com/university/"
    "iit-bombay-indian-institute-of-technology-mumbai-54212/reviews-{}"
)

START_PAGE = 4          # first page number
END_PAGE = 30           # last page number (inclusive)

OUTPUT_DIR = r"C:\Users\ASUS\Desktop\Sample Project\Webpages"

# A browser-like User-Agent so the site doesn't think this is a bot script
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


SLEEP_SECONDS = 1       # pause between requests to be polite

# ----------------------------


def download_page(page_number: int) -> None:
    url = BASE_URL_TEMPLATE.format(page_number)
    print(f"\nFetching page {page_number}: {url}")

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"  Attempt {attempt}/{MAX_RETRIES}...")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=40)
        except requests.RequestException as e:
            print(f"    [ERROR] Request failed: {e}")
            # If not last attempt, wait a bit and retry
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            else:
                print(f"    [GIVE UP] Skipping page {page_number}")
                return

        if resp.status_code != 200:
            print(f"    [WARN] Status {resp.status_code} for page {page_number}")
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            else:
                print(f"    [GIVE UP] Skipping page {page_number}")
                return

        # If we reach here, we got a valid response
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        filename = f"page_{page_number}.html"
        out_path = os.path.join(OUTPUT_DIR, filename)

        with open(out_path, "w", encoding=resp.encoding or "utf-8") as f:
            f.write(resp.text)

        print(f"    [OK] Saved to {out_path}")
        return


def main():
    for page in range(START_PAGE, END_PAGE + 1):
        download_page(page)
        time.sleep(3)  # was 1; be extra polite


if __name__ == "__main__":
    main()
