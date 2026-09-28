"""
analyzer.py
Send ONE review to Jev (all 14 questions in one request) and turn the answers
into star ratings per topic.

Uses HTTP/2 + a persistent keep-alive pool under the hood so the second call
onwards doesn't re-pay TLS/DNS. Prefers a direct TypeSafe call if
TYPESAFE_API_KEY is present, else routes through OpenRouter.
"""

import logging
import os
import time

import httpx2
from dotenv import load_dotenv
from typesafe_sdk import TypeSafeClient

from logging_config import setup_logging
from questions import QUESTIONS, TOPICS

setup_logging()
log = logging.getLogger("analyzer")

load_dotenv()

if os.environ.get("TYPESAFE_API_KEY"):
    _api_key = os.environ["TYPESAFE_API_KEY"]
    _base_url = None
    BACKEND = "typesafe-direct"
else:
    _api_key = os.environ["OPENROUTER_API_KEY"]
    _base_url = "https://openrouter.ai/api"
    BACKEND = "openrouter-proxy"

_http = httpx2.Client(
    http2=True,
    timeout=httpx2.Timeout(30.0, connect=5.0),
    limits=httpx2.Limits(
        max_keepalive_connections=8,
        max_connections=8,
        keepalive_expiry=120.0,
    ),
)

_client_kwargs = {"api_key": _api_key, "http_client": _http}
if _base_url:
    _client_kwargs["base_url"] = _base_url
client = TypeSafeClient(**_client_kwargs)

MODEL = "jev-latest"
MENTION_THRESHOLD = 0.5

log.info("jev analyzer ready backend=%s model=%s", BACKEND, MODEL)


def analyze_review(review_text):
    """Return a dict like {"Camera": 4.2, "Battery": 1.8}.
    Topics the review doesn't talk about are left out."""

    log.debug("jev analyze start review_len=%d backend=%s", len(review_text), BACKEND)
    start = time.perf_counter()
    try:
        response = client.system_one(
            model=MODEL,
            state=review_text,
            questions=QUESTIONS,
        )
    except Exception:
        log.exception(
            "jev analyze FAILED after %.1f ms review_len=%d",
            (time.perf_counter() - start) * 1000,
            len(review_text),
        )
        raise

    answers = response.answers
    ratings, skipped = {}, {}
    for topic_name, topic_id in TOPICS.items():
        mentioned = answers[topic_id + "_mentioned"].noul
        if mentioned >= MENTION_THRESHOLD:
            level = answers[topic_id + "_rating"].score
            ratings[topic_name] = round(level + 1, 1)
        else:
            skipped[topic_name] = round(mentioned, 2)

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "jev analyze OK ms=%.1f ratings=%s skipped_below_threshold=%s",
        elapsed_ms, ratings, skipped,
    )
    return ratings