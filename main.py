"""
main.py
1. Read the reviews CSV
2. Analyze every review with the chosen provider (Jev by default, or Fable)
3. Print a Flipkart-style summary

Usage:
  python main.py                    # Jev via OpenRouter
  python main.py --provider fable   # Claude Fable 5.1 via Anthropic
"""

import argparse
import csv

from aggregation import aggregate

INPUT_FILE = "synthetic_phone_reviews.csv"


def get_analyzer(name):
    if name == "jev":
        from analyzer import analyze_review
    elif name == "fable":
        from fable_analyzer import analyze_review
    else:
        raise ValueError(f"unknown provider: {name}")
    return analyze_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["jev", "fable"], default="jev")
    parser.add_argument("--input", default=INPUT_FILE)
    args = parser.parse_args()

    analyze_review = get_analyzer(args.provider)

    with open(args.input, encoding="utf-8") as f:
        reviews = list(csv.DictReader(f))

    all_ratings = []
    for review in reviews:
        ratings = analyze_review(review["review_text"])
        all_ratings.append(ratings)
        print(review["review_id"], ratings)

    overall = sum(int(r["overall_rating"]) for r in reviews) / len(reviews)
    summary = aggregate(all_ratings)

    print()
    print(f"{overall:.1f} ★  based on {len(reviews)} ratings  [{args.provider}]")
    print("-" * 40)
    for topic, info in summary.items():
        if info["average"] is None:
            print(f"{topic:<16} no ratings yet")
        else:
            print(f"{topic:<16} {info['average']:.1f} ★  ({info['count']} reviews)")


if __name__ == "__main__":
    main()