# make_shiksha_reviews_enriched.py
import os, re, csv
from statistics import mean

OUT_CSV = "shiksha_reviews_enriched.csv"

# ---------- regexes (same as your working script) ----------
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TAG_RE   = re.compile(r"<[^>]+>")
WS_RE    = re.compile(r"\s+")
REVIEW_ANCHOR = re.compile(r"Reviewed on\s+([0-9]{1,2}\s+\w+\s+\d{4})", re.I)

DEGREE_BRANCH_RE = re.compile(
    r"""(?P<degree>
            (?:B\.?\s?Tech|M\.?\s?Tech|MBA|M\.?BA|B\.?Des|M\.?Des|B\.?\s?Sc|M\.?\s?Sc|BS|MS|
             Ph\.?D|Dual\s+Degree|Integrated[^–—-]*|Master\s+of\s+[^–—-]*|Bachelor\s+of\s+[^–—-]*)
        )
        \s+(?:in|of)\s+
        (?P<branch>[^–—\-|]+?)
        (?:\s*[-–—|]\s*Batch\s+of\s+(?P<year>\d{4}))?
    """,
    re.I | re.X,
)

OVERALL_AFTER_BATCH_RE = re.compile(
    r"Batch\s+of\s+(?P<year>\d{4})\D{0,30}(?P<rating>[0-5](?:\.\d)?)\b", re.I
)

CAT_RE = re.compile(
    r"(Placements|Infrastructure|Faculty|Crowd\s*&\s*Campus\s*Life|Campus\s*Life|Value\s*for\s*Money|Academics)\s+([0-5](?:\.\d)?)",
    re.I,
)
CAT_MAP = {
    "placements": "placements_rating",
    "infrastructure": "infrastructure_rating",
    "faculty": "faculty_rating",
    "crowd & campus life": "campus_rating",
    "campus life": "campus_rating",
    "value for money": "vfm_rating",
    "academics": "academics_rating",
}

MONTHS = {m.lower(): f"{i:02d}" for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)
}

# ---------- helpers ----------
def html_to_text(html: str) -> str:
    t = TAG_RE.sub(" ", html)
    t = WS_RE.sub(" ", t)
    return t

def get_title(html: str) -> str:
    m = TITLE_RE.search(html)
    return WS_RE.sub(" ", m.group(1)).strip() if m else ""

def _to_iso(dmy: str) -> str:
    m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})\s*$", dmy)
    if not m: return ""
    d = int(m.group(1)); mon = m.group(2)[:3].lower(); y = m.group(3)
    return f"{y}-{MONTHS.get(mon,'01')}-{d:02d}"

def month_key(date_iso: str) -> str:
    return date_iso[:7] if date_iso else ""

def parse_degree_branch_year(win: str):
    m = DEGREE_BRANCH_RE.search(win)
    if not m: return "", "", ""
    deg = " ".join(m.group("degree").split())
    br  = " ".join((m.group("branch") or "").split())
    yr  = (m.group("year") or "")
    return deg, br, yr

def parse_overall_rating(win: str):
    m = OVERALL_AFTER_BATCH_RE.search(win)
    if m:
        try: return float(m.group("rating"))
        except: pass
    return None

def parse_category_ratings(win: str):
    vals = {}
    for name, val in CAT_RE.findall(win):
        key = CAT_MAP[name.lower()]
        try: vals[key] = float(val)
        except: pass
    return vals

def label_from_rating(score):
    if score is None: return "neutral"
    if score >= 4.0:  return "good"
    if score <= 2.5:  return "bad"
    return "neutral"

def compute_is_alumni(batch_year: str, reviewed_date: str, window_text: str):
    try:
        by = int(batch_year) if batch_year else None
        ry = int(reviewed_date[:4]) if reviewed_date else None
        if by and ry:
            return "true" if ry >= by else "false"
    except: pass
    # fallback keyword check
    return str(("alumni" in window_text.lower()) or ("alumn" in window_text.lower())).lower()

def parse_file(path: str):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    title = get_title(html) or os.path.basename(path)
    text  = html_to_text(html)

    rows = []
    anchors = list(REVIEW_ANCHOR.finditer(text))
    for i, m in enumerate(anchors):
        date_str = m.group(1)
        date_iso = _to_iso(date_str)

        start = anchors[i-1].start() if i > 0 else max(0, m.start() - 1500)
        end   = anchors[i+1].start() if i+1 < len(anchors) else min(len(text), m.end() + 1500)
        win   = text[start:end]

        degree, branch, batch_year = parse_degree_branch_year(win)
        overall = parse_overall_rating(win)
        cats    = parse_category_ratings(win)

        rating_0_5, rating_source = None, ""
        if isinstance(overall, float):
            rating_0_5, rating_source = overall, "overall"
        elif cats:
            rating_0_5, rating_source = mean(cats.values()), "categories_avg"

        stars_int  = str(int(round(rating_0_5))) if isinstance(rating_0_5, float) else ""
        stars_half = str(round(rating_0_5 * 2) / 2) if isinstance(rating_0_5, float) else ""

        rows.append({
            "iit": title,
            "reviewed_date": date_iso,
            "month": month_key(date_iso),
            "degree": degree,
            "branch": branch,
            "batch_year": batch_year,
            "is_alumni": compute_is_alumni(batch_year, date_iso, win),
            "overall_rating": f"{overall:.1f}" if isinstance(overall, float) else "",
            "placements_rating": f"{cats.get('placements_rating','')}",
            "infrastructure_rating": f"{cats.get('infrastructure_rating','')}",
            "faculty_rating": f"{cats.get('faculty_rating','')}",
            "campus_rating": f"{cats.get('campus_rating','')}",
            "vfm_rating": f"{cats.get('vfm_rating','')}",
            "academics_rating": f"{cats.get('academics_rating','')}",
            "rating_0_5": f"{rating_0_5:.2f}" if isinstance(rating_0_5, float) else "",
            "rating_source": rating_source,
            "stars_int": stars_int,
            "stars_half": stars_half,
            "label": label_from_rating(rating_0_5),
            "text": win.strip(),
            "source_url": "file://" + os.path.abspath(path).replace("\\", "/"),
        })
    return rows

# ---------- folder selection ----------
def resolve_webpages_dirs(user_input: str):
    """Return a list of directory names to parse based on user input."""
    inp = (user_input or "").strip().lower()
    all_dirs = [d for d in os.listdir(".") if os.path.isdir(d)]
    webpages_like = [d for d in all_dirs if d.lower().startswith("webpages")]

    if inp in ("all", "*"):
        return sorted(webpages_like)

    # exact dir name match (case-insensitive)
    for d in all_dirs:
        if d.lower() == inp:
            return [d]

    # try Webpages_<token>
    token = re.sub(r"[^a-z0-9]+", "_", inp).strip("_")
    target = f"webpages_{token}" if token else "webpages"

    # exact match among webpages-like
    for d in webpages_like:
        if d.lower() == target:
            return [d]

    # fuzzy: any webpages dir containing token
    if token:
        fuzzy = [d for d in webpages_like if token in d.lower()]
        if fuzzy:
            return sorted(fuzzy)

    # as a last attempt, if plain "webpages" exists, use it
    for d in webpages_like:
        if d.lower() == "webpages":
            return [d]

    return []  # not found

def main():
    print("Which IIT folder? (e.g., Bombay, Delhi, All)")
    choice = input("> ").strip()
    dirs = resolve_webpages_dirs(choice)

    if not dirs:
        print("[error] No matching folders found.")
        existing = ", ".join(sorted([d for d in os.listdir(".") if os.path.isdir(d) and d.lower().startswith("webpages")]))
        print("Existing folders I can see:", existing or "(none)")
        return

    all_rows = []
    for folder in dirs:
        files = [os.path.join(folder, f)
                 for f in os.listdir(folder)
                 if f.lower().endswith((".html", ".htm"))]
        files.sort()
        if not files:
            print(f"[warn] no .html/.htm files in: {folder}")
            continue

        total = 0
        for fp in files:
            rows = parse_file(fp)
            total += len(rows)
            dates = [r["reviewed_date"] for r in rows if r["reviewed_date"]]
            dr = f"{min(dates)} → {max(dates)}" if dates else "—"
            print(f"[{os.path.basename(fp)}] total:{len(rows)}  dates:{dr}")
            all_rows.extend(rows)

        print(f"[{folder}] collected {total} review(s)")

    fields = [
        "iit","reviewed_date","month","degree","branch","batch_year","is_alumni",
        "overall_rating","placements_rating","infrastructure_rating","faculty_rating",
        "campus_rating","vfm_rating","academics_rating",
        "rating_0_5","rating_source","stars_int","stars_half","label","text","source_url"
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    print(f"\nDONE. Wrote {len(all_rows)} reviews -> {OUT_CSV}")

if __name__ == "__main__":
    main()
