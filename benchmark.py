"""
benchmark.py
Latency comparison of Claude Fable 5.1 (via Anthropic) and Jev (via TypeSafe
direct if TYPESAFE_API_KEY is set, otherwise via OpenRouter).

To keep the comparison fair the two providers are NOT interleaved: all Fable
calls run first, then all Jev calls, so each provider keeps its HTTP
keep-alive pool warm across every one of its calls.

Every step is written to app.log via logging_config.setup_logging(). Set the
LOG_LEVEL env var to DEBUG to log the per-review request bodies as well.

Usage:
  python benchmark.py                          # 10 reviews, 1 repeat, warmup on
  python benchmark.py --limit 25 --repeats 3   # 25 reviews, 3 calls each
  python benchmark.py --limit 0                # all reviews
  python benchmark.py --no-warmup              # skip the throwaway warm-up call
"""

import argparse
import csv
import logging
import statistics
import time
import traceback

from logging_config import setup_logging

setup_logging()
log = logging.getLogger("benchmark")

from analyzer import BACKEND as JEV_BACKEND
from analyzer import analyze_review as jev_analyze
from fable_analyzer import analyze_review as fable_analyze

INPUT_FILE = "synthetic_phone_reviews.csv"
WARMUP_TEXT = "Battery lasts all day and the camera is decent."


def timed(fn, text):
    start = time.perf_counter()
    try:
        ratings = fn(text)
        return ratings, (time.perf_counter() - start) * 1000, None
    except Exception as exc:
        return None, (time.perf_counter() - start) * 1000, exc


def warm_up():
    log.info("warm-up start (Fable then Jev)")
    print("Warming up (one throwaway call per provider)...", flush=True)
    for label, fn in (("Fable", fable_analyze), ("Jev  ", jev_analyze)):
        ratings, ms, err = timed(fn, WARMUP_TEXT)
        note = f"  {label} warm-up: {ms:9.1f} ms"
        if err:
            note += f"   ERROR: {err!r}"
            log.error("warm-up %s FAIL ms=%.1f err=%r", label.strip(), ms, err)
        else:
            log.info("warm-up %s OK ms=%.1f ratings=%s", label.strip(), ms, ratings)
        print(note, flush=True)
    print()


def run_provider(label, fn, reviews, repeats):
    print(f"\n== {label} ==".ljust(60, "="), flush=True)
    print(f"{'id':<6}  {'min ms':>10}  {'median ms':>11}  ratings")
    print("-" * 76)
    log.info("provider run start label=%r n_reviews=%d repeats=%d", label, len(reviews), repeats)

    per_review, all_ms = [], []
    for review in reviews:
        row_ms, last_ratings, last_err = [], None, None
        for _ in range(repeats):
            ratings, ms, err = timed(fn, review["review_text"])
            row_ms.append(ms)
            if ratings is not None:
                last_ratings = ratings
            elif err:
                last_err = err

        m_min = min(row_ms)
        m_med = statistics.median(row_ms)
        per_review.append({
            "review_id": review["review_id"],
            "min_ms": m_min,
            "median_ms": m_med,
            "ratings": last_ratings or {},
            "error": repr(last_err) if last_err else "",
        })
        all_ms.extend(row_ms)

        ratings_str = last_ratings if last_ratings else last_err
        print(f"{review['review_id']:<6}  {m_min:>10.1f}  {m_med:>11.1f}  {ratings_str}")

    log.info(
        "provider run done label=%r calls=%d median_ms=%.1f",
        label, len(all_ms), statistics.median(all_ms) if all_ms else -1,
    )
    return per_review, all_ms


def summarize(label, all_ms):
    if not all_ms:
        return
    print(f"\n{label}")
    print("-" * 60)
    print(f"  min    {min(all_ms):9.1f} ms")
    print(f"  median {statistics.median(all_ms):9.1f} ms")
    print(f"  mean   {statistics.mean(all_ms):9.1f} ms")
    print(f"  max    {max(all_ms):9.1f} ms   (n={len(all_ms)})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--input", default=INPUT_FILE)
    args = parser.parse_args()

    log.info("benchmark start args=%s jev_backend=%s", vars(args), JEV_BACKEND)
    print(f"Jev backend: {JEV_BACKEND}   (set TYPESAFE_API_KEY to use "
          f"typesafe-direct instead of openrouter-proxy)")
    print("Detailed log: app.log   (set LOG_LEVEL=DEBUG for verbose)\n")

    if not args.no_warmup:
        warm_up()

    with open(args.input, encoding="utf-8") as f:
        reviews = list(csv.DictReader(f))
    if args.limit:
        reviews = reviews[:args.limit]

    fable_rows, fable_all = run_provider("Claude Fable 5.1", fable_analyze,
                                         reviews, args.repeats)
    jev_rows, jev_all = run_provider(f"Jev ({JEV_BACKEND})", jev_analyze,
                                     reviews, args.repeats)

    summarize("Claude Fable 5.1", fable_all)
    summarize(f"Jev ({JEV_BACKEND})", jev_all)

    if fable_all and jev_all:
        f_med = statistics.median(fable_all)
        j_med = statistics.median(jev_all)
        if j_med > 0:
            ratio = f_med / j_med
            print(f"\n>>> Jev is {ratio:.1f}x faster than "
                  f"Claude Fable 5.1 at the median.")
            log.info("summary jev_median_ms=%.1f fable_median_ms=%.1f ratio=%.2f",
                     j_med, f_med, ratio)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        log.exception("benchmark crashed")
        traceback.print_exc()