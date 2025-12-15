# import_shiksha_reviews_v2.py
import csv, re, time
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs
import requests
from bs4 import BeautifulSoup

# -------- config --------
INPUT_URLS = "shiksha_urls.csv"
OUTPUT_CSV = "shiksha_reviews.csv"
YEARS_BACK = 5
RATE_DELAY = 0.8

# Use a very "normal" browser UA to avoid alternate markup
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

# -------- helpers --------
DATE_TXT = re.compile(r"Reviewed on\s+(\d{1,2}\s+\w{3,}\s+\d{4})", re.I)
BATCH_TXT = re.compile(r"\bBatch\s+of\s+(\d{4})\b", re.I)

def parse_date_str(s: str):
    s = s.strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try: return datetime.strptime(s, fmt)
        except ValueError: pass
    return None

def boundary_date():
    today_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return today_ist.replace(tzinfo=None) - timedelta(days=365*YEARS_BACK + 2)

def set_page(url: str, page: int) -> str:
    if page == 1: return url
    parts = urlsplit(url)
    q = parse_qs(parts.query)
    q["page"] = [str(page)]
    new_q = urlencode(q, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_q, parts.fragment))

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def split_degree_branch(title: str):
    """
    title examples:
      "B.Tech. in Computer Science and Engineering"
      "Master of Business Administration (MBA)"
      "Integrated B.Tech. in Electrical Engineering + M.Tech. in Communication and Signal Processing"
    We keep this simple & resilient:
      - degree = text up to ' in ' or first ' of ' (if present), else first 6 tokens
      - branch = remainder (may be empty)
    """
    t = clean(title)
    m = re.split(r"\s+(?:in|of)\s+", t, maxsplit=1, flags=re.I)
    if len(m) == 2:
        return m[0], m[1]
    # fallback: take first 6 tokens as "degree", rest as "branch"
    toks = t.split()
    deg = " ".join(toks[:6]) if len(toks) > 6 else t
    br  = " ".join(toks[6:]) if len(toks) > 6 else ""
    return deg, br

# -------- CSV input (tolerant to BOM, ; etc.) --------
def read_input_urls(path: str):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        r = csv.DictReader(f, dialect=dialect)
        if not r.fieldnames:
            raise ValueError("shiksha_urls.csv has no header row.")
        norm = { (h or "").strip().strip('"').strip("\ufeff").lower(): h for h in r.fieldnames }
        iit_key = norm.get("iit") or norm.get("college") or norm.get("name")
        url_key = norm.get("url") or norm.get("link") or norm.get("reviews_url")
        if not iit_key or not url_key:
            raise ValueError(f"Expected headers 'iit' and 'url'. Found: {r.fieldnames}")
        for row in r:
            iit = (row.get(iit_key) or "").strip()
            url = (row.get(url_key) or "").strip()
            if iit and url:
                yield iit, url

# -------- fetch & parse --------
def fetch(url: str) -> str:
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def extract_cards(soup: BeautifulSoup):
    """
    Strategy:
      1) Find all elements whose text contains 'Batch of YYYY' (very stable on Shiksha).
      2) For each, walk up to the smallest ancestor that ALSO contains a 'Reviewed on ...' line.
      3) That ancestor is the review 'card' – extract fields from within.
    """
    seen = set()
    for node in soup.find_all(string=BATCH_TXT):
        # avoid duplicate text nodes
        container = None
        for anc in getattr(node, "parents", []):
            if not hasattr(anc, "get_text"): continue
            block = anc.get_text(" ", strip=True)
            if DATE_TXT.search(block):
                container = anc
                break
        if not container:  # if we didn't find a date with this ancestor chain, skip
            continue
        key = id(container)
        if key in seen:  # don't yield same ancestor multiple times
            continue
        seen.add(key)
        yield container

def parse_card(card):
    txt = card.get_text(" ", strip=True)

    # reviewed date
    m = DATE_TXT.search(txt)
    if not m:
        return None
    dt = parse_date_str(m.group(1))
    if not dt:
        return None

    # course/batch line
    mb = BATCH_TXT.search(txt)
    batch_year = int(mb.group(1)) if mb else None

    # find the visible course title preceding "Batch of"
    course_title = ""
    if mb:
        pre = txt[:mb.start()]
        # take the last ' - ' or ' | ' separated chunk (closest to 'Batch of')
        parts = re.split(r"\s[-–—|]\s", pre)
        course_title = parts[-1] if parts else pre
        # often course title itself contains 'B.Tech. in ...', which we want
        course_title = re.sub(r"^\W+|\W+$", "", course_title)

    degree, branch = ("", "")
    if course_title:
        degree, branch = split_degree_branch(course_title)

    # full review body (optional, but handy later)
    # usually includes "Placements:", "Infrastructure:", etc.
    body = txt

    is_alumni = ""
    if batch_year:
        is_alumni = "true" if dt.year >= batch_year else "false"

    return {
        "reviewed_date": dt.strftime("%Y-%m-%d"),
        "degree": degree,
        "branch": branch,
        "batch_year": batch_year or "",
        "is_alumni": is_alumni,
        "text": body
    }

def iter_reviews(url: str, keep_after: datetime):
    total = 0
    for page in range(1, 40):
        page_url = set_page(url, page)
        html = fetch(page_url)
        time.sleep(RATE_DELAY)
        soup = BeautifulSoup(html, "lxml")

        cards = list(extract_cards(soup))
        if not cards:
            if page == 1:
                print(f"[warn] no review cards detected on {url}")
            break

        any_recent = False
        for c in cards:
            rec = parse_card(c)
            if not rec:
                continue
            dt = datetime.strptime(rec["reviewed_date"], "%Y-%m-%d")
            if dt >= keep_after:
                any_recent = True
                total += 1
                yield rec, page_url
        if not any_recent:
            break
    print(f"[info] parsed {total} recent reviews from {url}")

def main():
    keep_after = boundary_date()
    out_rows = []
    for iit, url in read_input_urls(INPUT_URLS):
        for rec, src in iter_reviews(url, keep_after):
            out_rows.append({
                "iit": iit,
                "reviewed_date": rec["reviewed_date"],
                "degree": rec["degree"],
                "branch": rec["branch"],
                "batch_year": rec["batch_year"],
                "is_alumni": rec["is_alumni"],
                "text": rec["text"],
                "source_url": src
            })

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "iit","reviewed_date","degree","branch","batch_year","is_alumni","text","source_url"
        ])
        w.writeheader()
        w.writerows(out_rows)
    print(f"Wrote {len(out_rows)} reviews -> {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
