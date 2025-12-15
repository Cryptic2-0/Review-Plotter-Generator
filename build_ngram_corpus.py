import csv
import re
from collections import defaultdict
from pathlib import Path

# ---------- CONFIG ----------

INPUT_CSV   = "shiksha_reviews_enriched.csv"
TEXT_COLUMN = "text"
RATING_COLUMN = "rating_0_5"   # <- change this line


OUTPUT_DIR = "ngram_corpus"    # folder where we'll write 1–5 word corpora

MIN_N = 1
MAX_N = 5

# ----------------------------

def normalize_text(text: str) -> list[str]:
    """
    Clean and tokenize text.
    - lowercase
    - remove non-alphabetic characters (keeps spaces)
    - split on whitespace
    """
    text = text.lower()
    # replace anything that's not a-z with space
    text = re.sub(r"[^a-z]+", " ", text)
    tokens = text.split()
    return tokens


def generate_ngrams(tokens: list[str], n: int) -> list[str]:
    """Return list of n-grams as space-joined strings."""
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def build_ngram_stats(
    csv_path: str,
    text_column: str,
    rating_column: str,
    min_n: int,
    max_n: int
):
    """
    Build per-ngram stats using *document frequency*:
      - each n-gram counted at most once per review
      - we accumulate rating sums to later compute avg rating.

    Returns: { n: { ngram: [review_count, rating_sum] } }
    """
    stats = {
        n: defaultdict(lambda: [0, 0.0])
        for n in range(min_n, max_n + 1)
    }

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if text_column not in reader.fieldnames:
            raise ValueError(
                f"Column '{text_column}' not found. "
                f"Available columns: {reader.fieldnames}"
            )
        if rating_column not in reader.fieldnames:
            raise ValueError(
                f"Column '{rating_column}' not found. "
                f"Available columns: {reader.fieldnames}"
            )

        for row in reader:
            text = row.get(text_column, "")
            if not text:
                continue

            # parse rating
            try:
                rating = float(row[rating_column])
            except (TypeError, ValueError):
                # skip reviews with bad / missing rating
                continue

            tokens = normalize_text(text)
            if not tokens:
                continue

            for n in range(min_n, max_n + 1):
                ngrams = generate_ngrams(tokens, n)
                if not ngrams:
                    continue

                # *** key change: only 1 instance per review ***
                unique_ngrams = set(ngrams)

                for ng in unique_ngrams:
                    stats[n][ng][0] += 1          # review count
                    stats[n][ng][1] += rating     # sum of ratings

    return stats


def save_stats_to_csv(stats, output_dir: str):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    name_map = {
        1: "unigrams.csv",
        2: "bigrams.csv",
        3: "trigrams.csv",
        4: "fourgrams.csv",
        5: "fivegrams.csv",
    }

    for n, ngram_dict in stats.items():
        filename = name_map.get(n, f"{n}grams.csv")
        out_path = Path(output_dir) / filename

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "ngram",
                "reviews_mentioning_ngram",  # document frequency
                "avg_rating_0_5",
                "avg_rating_percent",        # helpful for 0–100% sentiment axis
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for ngram, (review_count, rating_sum) in ngram_dict.items():
                # keep your old rule: for n >= 2, drop n-grams seen only once
                if n >= 2 and review_count <= 1:
                    continue

                avg_rating = rating_sum / review_count
                avg_rating_pct = avg_rating / 5.0 * 100.0  # assuming 0–5 scale

                writer.writerow({
                    "ngram": ngram,
                    "reviews_mentioning_ngram": review_count,
                    "avg_rating_0_5": f"{avg_rating:.3f}",
                    "avg_rating_percent": f"{avg_rating_pct:.1f}",
                })

        print(f"Saved {n}-gram stats to: {out_path}")


def main():
    print(f"Reading reviews from: {INPUT_CSV}")
    print(f"Building {MIN_N}–{MAX_N}-gram stats…")

    stats = build_ngram_stats(
        INPUT_CSV,
        TEXT_COLUMN,
        RATING_COLUMN,
        MIN_N,
        MAX_N,
    )

    print(f"Writing CSVs to folder: {OUTPUT_DIR}")
    save_stats_to_csv(stats, OUTPUT_DIR)

    print("Done.")


if __name__ == "__main__":
    main()
