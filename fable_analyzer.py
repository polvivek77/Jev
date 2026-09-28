"""
fable_analyzer.py
Same shape as analyzer.analyze_review, but backed by Anthropic's Claude Fable 5.1
using structured outputs. Kept parallel to the Jev version so we can benchmark
speed side by side.
"""

import json
import logging
import os
import time

import anthropic
from dotenv import load_dotenv

from logging_config import setup_logging
from questions import TOPICS, SATISFACTION_LEVELS

setup_logging()
log = logging.getLogger("fable_analyzer")

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-fable-5-1"

TOPIC_DESCRIPTIONS = {
    "camera": "the camera's photos or videos",
    "battery": "battery life or charging",
    "display": "the screen",
    "design": "the phone's appearance, shape, or ergonomics",
    "performance": "speed, responsiveness, multitasking, or gaming",
    "build_quality": "the phone's materials, sturdiness, or durability",
    "value_for_money": "whether the phone is worth its price",
}

_scale_lines = "\n".join(f"  {i + 1} = {label}" for i, label in enumerate(SATISFACTION_LEVELS))
_topic_lines = "\n".join(f"  - {tid}: {desc}" for tid, desc in TOPIC_DESCRIPTIONS.items())

SYSTEM_PROMPT = f"""You analyze smartphone reviews. For each topic below, decide:

1. mentioned (true/false): did the reviewer express an opinion or experience \
about that topic?
2. rating (1-5): the reviewer's satisfaction, using this scale:
{_scale_lines}

Topics:
{_topic_lines}

If a topic isn't discussed, set mentioned=false and rating=3 as a placeholder.
Return only the JSON matching the schema."""

# Anthropic's structured-output validator does NOT accept `minimum`/`maximum`
# on number / integer types (returns 400). Use `enum` for the rating instead
# and a plain boolean for mention.
_topic_schema = {
    "type": "object",
    "properties": {
        "mentioned": {"type": "boolean"},
        "rating": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["mentioned", "rating"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {tid: _topic_schema for tid in TOPICS.values()},
    "required": list(TOPICS.values()),
    "additionalProperties": False,
}


def analyze_review(review_text):
    """Return a dict like {"Camera": 4.0, "Battery": 2.0}. Topics the model
    marked mentioned=false are left out."""

    log.debug("fable analyze start review_len=%d model=%s", len(review_text), MODEL)
    start = time.perf_counter()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": OUTPUT_SCHEMA,
                }
            },
            messages=[{"role": "user", "content": f"Review:\n{review_text}"}],
        )
    except Exception:
        log.exception(
            "fable analyze FAILED after %.1f ms review_len=%d",
            (time.perf_counter() - start) * 1000,
            len(review_text),
        )
        raise

    text = next(b.text for b in response.content if b.type == "text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.exception("fable analyze got non-JSON response: %r", text[:500])
        raise

    ratings = {}
    for topic_name, topic_id in TOPICS.items():
        entry = data.get(topic_id, {})
        if entry.get("mentioned"):
            ratings[topic_name] = float(entry["rating"])

    elapsed_ms = (time.perf_counter() - start) * 1000
    usage = getattr(response, "usage", None)
    input_toks = getattr(usage, "input_tokens", None) if usage else None
    output_toks = getattr(usage, "output_tokens", None) if usage else None
    log.info(
        "fable analyze OK ms=%.1f input_tokens=%s output_tokens=%s ratings=%s",
        elapsed_ms, input_toks, output_toks, ratings,
    )
    return ratings