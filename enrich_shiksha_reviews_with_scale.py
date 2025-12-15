import csv, re
from datetime import datetime
from statistics import mean

IN_CSV  = "shiksha_reviews.csv"
OUT_CSV = "shiksha_reviews_enriched.csv"
OUT_MON = "monthly_summary.csv"

# ---------------- regexes ----------------
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

GOOD = 4.0
BAD  = 2.5

# --------------- sentiment (optional) ---------------
_vader = None
try:
    from nltk.sentiment import SentimentIntensityAnalyzer
    try:
        _vader = SentimentIntensityAnalyzer()
    except Exception:
        import nltk
        nltk.download("vader_lexicon", quiet=True)
        _vader = SentimentIntensityAnalyzer()
except Exception:
    _vader = None  # sentiment fallback not available

def sentiment_to_0_5(text: str):
    """Map VADER compound [-1,1] -> [0,5]."""
    if not _vader:
        return None
    try:
        comp = _vader.polarity_scores(text or "")["compound"]
        return max(0.0, min(5.0, (comp + 1.0) * 2.5))
    except Exception:
        return None

# --------------- helpers ---------------
def parse_degree_branch_year(text):
    m = DEGREE_BRANCH_RE.search(text)
    if not m:
        return "", "", ""
    deg = " ".join(m.group("degree").split())
    br  = " ".join((m.group("branch") or "").split())
    yr  = m.group("year") or ""
    return deg, br, yr

def parse_overall_rating(text):
    m = OVERALL_AFTER_BATCH_RE.search(text)
    if m:
        try:
            return float(m.group("rating"))
        except Exception:
            return None
    return None

def parse_category_ratings(text):
    vals = {}
    for name, val in CAT_RE.findall(text):
        key = CAT_MAP[name.lower()]
        try:
            vals[key] = float(val)
        except Exception:
            pass
    return vals

def month_key(yyyy_mm_dd):
    return yyyy_mm_dd[:7] if yyyy_mm_dd else ""

def label_from_rating(score):
    if score is None: return "neutral"
    if score >= GOOD: return "good"
    if score <= BAD:  return "bad"
    return "neutral"

# --------------- main ---------------
def main():
    with open(IN_CSV, newline="", encoding="utf-8") as f:
        rows_in = list(csv.DictReader(f))

    out_rows = []
    monthly = {}

    for row in rows_in:
        text = row.get("text","")

        # Parse degree/branch/year (fill only if missing)
        deg, br, yr_from_text = parse_degree_branch_year(text)
        degree = row.get("degree") or deg
        branch = row.get("branch") or br
        batch_year = row.get("batch_year") or yr_from_text or ""

        # Ratings
        overall = parse_overall_rating(text)
        cats = parse_category_ratings(text)

        rating_0_5 = None
        rating_source = ""
        if isinstance(overall, float):
            rating_0_5 = overall
            rating_source = "overall"
        elif cats:
            rating_0_5 = mean(cats.values())
            rating_source = "categories_avg"
        else:
            s = sentiment_to_0_5(text)
            if isinstance(s, float):
                rating_0_5 = s
                rating_source = "sentiment"
            else:
                rating_0_5 = None
                rating_source = ""

        label = label_from_rating(rating_0_5)

        reviewed_date = row.get("reviewed_date","")
        mon = month_key(reviewed_date)

        new = {
            "iit": row.get("iit",""),
            "reviewed_date": reviewed_date,
            "month": mon,
            "degree": degree,
            "branch": branch,
            "batch_year": batch_year,
            "is_alumni": row.get("is_alumni",""),
            "overall_rating": f"{overall:.1f}" if isinstance(overall, float) else "",
            "placements_rating": f"{cats.get('placements_rating','')}",
            "infrastructure_rating": f"{cats.get('infrastructure_rating','')}",
            "faculty_rating": f"{cats.get('faculty_rating','')}",
            "campus_rating": f"{cats.get('campus_rating','')}",
            "vfm_rating": f"{cats.get('vfm_rating','')}",
            "academics_rating": f"{cats.get('academics_rating','')}",
            "rating_0_5": f"{rating_0_5:.2f}" if isinstance(rating_0_5, float) else "",
            "rating_source": rating_source,
            "label": label,
            "text": text,
            "source_url": row.get("source_url",""),
        }
        out_rows.append(new)

        if mon:
            d = monthly.setdefault(mon, {"count":0,"good":0,"bad":0,"neutral":0,"sum_rating":0.0,"n_rating":0})
            d["count"] += 1
            d[label] += 1
            if isinstance(rating_0_5, float):
                d["sum_rating"] += rating_0_5
                d["n_rating"] += 1

    # write enriched
    fields = [
        "iit","reviewed_date","month","degree","branch","batch_year","is_alumni",
        "overall_rating","placements_rating","infrastructure_rating","faculty_rating",
        "campus_rating","vfm_rating","academics_rating",
        "rating_0_5","rating_source","label","text","source_url"
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    # write monthly summary
    with open(OUT_MON, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month","count","good","bad","neutral","avg_rating_0_5"])
        for mon in sorted(monthly):
            d = monthly[mon]
            avg = f"{(d['sum_rating']/d['n_rating']):.3f}" if d["n_rating"] else ""
            w.writerow([mon, d["count"], d["good"], d["bad"], d["neutral"], avg])

    print(f"Wrote {len(out_rows)} rows -> {OUT_CSV}")
    print(f"Wrote monthly summary -> {OUT_MON}")

if __name__ == "__main__":
    main()
