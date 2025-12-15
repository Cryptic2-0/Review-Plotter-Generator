import os, re, csv, glob, argparse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

DATE_RE  = re.compile(r"Reviewed on\s+(\d{1,2}\s+\w{3,}\s+\d{4})", re.I)
BATCH_RE = re.compile(r"\bBatch\s+of\s+(\d{4})\b", re.I)
ASPECT_HINTS = ("Placements","Infrastructure","Faculty","Campus Life","Crowd & Campus Life","Value for Money","Academics")

def parse_dt(s):
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try: return datetime.strptime(s.strip(), fmt)
        except ValueError: pass
    return None

def clean(s): 
    import re
    return re.sub(r"\s+"," ",(s or "").strip())

def split_degree_branch(title: str):
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

    course_title, degree, branch = "", "", ""
    if mb:
        pre = text[:mb.start()]
        parts = re.split(r"\s[-–—|]\s", pre)
        course_title = parts[-1] if parts else pre
        course_title = re.sub(r"^\W+|\W+$","", course_title)
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
    files = []
    patterns = ("*.html","*.htm")
    if recursive:
        for ext in patterns:
            files += glob.glob(os.path.join(folder, "**", ext), recursive=True)
    else:
        for ext in patterns:
            files += glob.glob(os.path.join(folder, ext))
    # skip obvious asset files
    return [f for f in sorted(set(files)) if "_files" not in f.lower() and "saved_resource" not in f.lower()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="Webpages")
    ap.add_argument("--out", default="shiksha_reviews.csv")
    ap.add_argument("--years", type=int, default=5, help="Keep last N years (0 = keep all)")
    ap.add_argument("--recursive", type=int, default=0, help="1 = include subfolders")
    args = ap.parse_args()

    if args.years and args.years > 0:
        keep_after = (datetime.utcnow() + timedelta(hours=5, minutes=30)) - timedelta(days=365*args.years + 2)
    else:
        keep_after = None  # keep all

    files = list_html_files(args.dir, bool(args.recursive))
    if not files:
        print(f"[error] no .html/.htm in {args.dir}")
        return

    rows = []
    total_found, total_kept = 0, 0

    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "lxml")
        iit = detect_iit(soup, path)

        found_dates = []
        kept = 0
        found = 0

        for card in iter_review_cards(soup):
            rec = parse_card(card)
            if not rec:
                continue
            dt = datetime.strptime(rec["reviewed_date"], "%Y-%m-%d")
            found += 1
            found_dates.append(dt)
            if keep_after and dt < keep_after:
                continue
            kept += 1
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

        total_found += found
        total_kept  += kept
        if found_dates:
            rng = f"{min(found_dates).date()} → {max(found_dates).date()}"
        else:
            rng = "—"
        print(f"[{os.path.basename(path)}] total:{found}  kept:{kept}  dates:{rng}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "iit","reviewed_date","degree","branch","batch_year","is_alumni","text","source_url"
        ])
        w.writeheader()
        w.writerows(rows)

    print(f"\nDONE. Files: {len(files)}  Reviews found: {total_found}  Kept: {total_kept}  -> {args.out}")

if __name__ == "__main__":
    main()
