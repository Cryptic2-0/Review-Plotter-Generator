import os, re, csv, glob
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ======= config (simple) =======
INPUT_DIR = "Webpages"                   # folder with your saved review pages
OUTPUT_CSV = "shiksha_reviews.csv"       # output file
YEARS_BACK = 5                           # keep only last N years
# set to True if you want to include subfolders; False keeps it simple/top-level only
RECURSIVE = False

# ======= patterns =======
DATE_RE  = re.compile(r"Reviewed on\s+(\d{1,2}\s+\w{3,}\s+\d{4})", re.I)
BATCH_RE = re.compile(r"\bBatch\s+of\s+(\d{4})\b", re.I)
ASPECT_HINTS = ("Placements","Infrastructure","Faculty","Campus Life","Crowd & Campus Life","Value for Money","Academics")

def boundary_date():
    today_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return today_ist.replace(tzinfo=None) - timedelta(days=365*YEARS_BACK + 2)

def parse_dt(s):
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try: return datetime.strptime(s.strip(), fmt)
        except ValueError: pass
    return None

def clean(s): 
    return re.sub(r"\s+"," ",(s or "").strip())

def split_degree_branch(title: str):
    # "B.Tech. in Computer Science and Engineering" -> ("B.Tech.", "Computer Science and Engineering")
    t = clean(title)
    parts = re.split(r"\s+(?:in|of)\s+", t, maxsplit=1, flags=re.I)
    if len(parts)==2:
        return parts[0], parts[1]
    toks = t.split()
    deg  = " ".join(toks[:6]) if len(toks)>6 else t
    br   = " ".join(toks[6:]) if len(toks)>6 else ""
    return deg, br

def detect_iit(soup: BeautifulSoup, fname: str):
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    m = re.search(r"(IIT[^|–—]+)", title, re.I)
    if m:
        return clean(m.group(1))
    base = os.path.basename(fname)
    return re.sub(r"\.html?$","", base, flags=re.I)

def iter_review_cards(soup: BeautifulSoup):
    """Find every review by anchoring on 'Reviewed on ...' and grabbing its surrounding block."""
    seen = set()
    for node in soup.find_all(string=DATE_RE):
        container = None
        for anc in node.parents:
            if not hasattr(anc, "get_text"):
                continue
            txt = anc.get_text(" ", strip=True)
            # pick the smallest ancestor that also includes either 'Batch of' or aspect labels
            if BATCH_RE.search(txt) or any(h in txt for h in ASPECT_HINTS):
                container = anc
                break
        if not container:
            continue
        key = id(container)
        if key in seen:
            continue
        seen.add(key)
        yield container

def parse_card(card):
    text = card.get_text(" ", strip=True)
    md = DATE_RE.search(text)
    if not md:
        return None
    dt = parse_dt(md.group(1))
    if not dt:
        return None

    mb = BATCH_RE.search(text)
    batch_year = int(mb.group(1)) if mb else None

    # course title is usually just before "Batch of YYYY"
    course_title = ""
    if mb:
        pre = text[:mb.start()]
        parts = re.split(r"\s[-–—|]\s", pre)
        course_title = parts[-1] if parts else pre
        course_title = re.sub(r"^\W+|\W+$","", course_title)

    degree, branch = ("","")
    if course_title:
        degree, branch = split_degree_branch(course_title)

    is_alumni = ""
    if batch_year:
        is_alumni = "true" if dt.year >= batch_year else "false"

    return {
        "reviewed_date": dt.strftime("%Y-%m-%d"),
        "degree": degree,
        "branch": branch,
        "batch_year": batch_year or "",
        "is_alumni": is_alumni,
        "text": text
    }

def list_html_files(folder: str, recursive: bool):
    if recursive:
        files = []
        for ext in ("*.html","*.htm"):
            files += glob.glob(os.path.join(folder, "**", ext), recursive=True)
        # filter out obvious asset files if any slipped in
        return [f for f in sorted(set(files)) if "_files" not in f.lower() and "saved_resource" not in f.lower()]
    else:
        files = []
        for ext in ("*.html","*.htm"):
            files += glob.glob(os.path.join(folder, ext))
        return sorted(set(files))

def main():
    keep_after = boundary_date()
    files = list_html_files(INPUT_DIR, RECURSIVE)

    if not files:
        print(f"[error] no .html/.htm files found in: {INPUT_DIR}")
        return

    rows = []
    total_found = 0
    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "lxml")
        iit = detect_iit(soup, path)

        file_count = 0
        for card in iter_review_cards(soup):
            rec = parse_card(card)
            if not rec:
                continue
            dt = datetime.strptime(rec["reviewed_date"], "%Y-%m-%d")
            if dt < keep_after:
                continue
            file_count += 1
            rows.append({
                "iit": iit,
                "reviewed_date": rec["reviewed_date"],
                "degree": rec["degree"],
                "branch": rec["branch"],
                "batch_year": rec["batch_year"],
                "is_alumni": rec["is_alumni"],
                "text": rec["text"],
                "source_url": f"file:///{os.path.abspath(path)}"
            })
        total_found += file_count
        print(f"[{os.path.basename(path)}] -> {file_count} review(s)")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "iit","reviewed_date","degree","branch","batch_year","is_alumni","text","source_url"
        ])
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote {len(rows)} reviews from {len(files)} files -> {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
