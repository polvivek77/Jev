"""
Streamlit dashboard: latency comparison of Claude Fable 5.1 vs Jev on the same
reviews. Fable is called for every review first, then Jev — so each provider
keeps its HTTP keep-alive pool warm across all its calls.

Also shows per-review ratings from both providers (Flipkart-style summary),
same shape as main.py's output. All activity is logged to app.log.

Run:
    streamlit run streamlit_app.py
"""

import csv
import logging
import statistics
import time

import pandas as pd
import streamlit as st

from logging_config import setup_logging

setup_logging()
log = logging.getLogger("streamlit_app")

INPUT_FILE = "synthetic_phone_reviews.csv"
WARMUP_TEXT = "Battery lasts all day and the camera is decent."

st.set_page_config(
    page_title="Jev vs Fable — latency",
    page_icon=":material/speed:",
    layout="wide",
)


@st.cache_data
def load_reviews(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@st.cache_resource
def get_jev_analyzer():
    from analyzer import BACKEND, analyze_review
    return analyze_review, BACKEND


@st.cache_resource
def get_fable_analyzer():
    from fable_analyzer import analyze_review
    return analyze_review


def timed(fn, text: str):
    """Return (ratings_or_None, elapsed_ms, exception_or_None)."""
    start = time.perf_counter()
    try:
        ratings = fn(text)
        return ratings, (time.perf_counter() - start) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return None, (time.perf_counter() - start) * 1000, exc


@st.cache_resource
def warmed_analyzers():
    """Once-per-session warm-up so the first real call doesn't pay TLS setup."""
    log.info("streamlit warm-up start")
    jev, backend = get_jev_analyzer()
    fable = get_fable_analyzer()
    for label, fn in (("Fable", fable), ("Jev", jev)):
        try:
            fn(WARMUP_TEXT)
            log.info("streamlit warm-up %s OK", label)
        except Exception:
            log.exception("streamlit warm-up %s FAILED", label)
    return fable, jev, backend


def run_sequential(reviews: list[dict], repeats: int, progress_slot) -> pd.DataFrame:
    """Fable ALL first, then Jev ALL. Two separate loops, not interleaved."""
    fable, jev, backend = warmed_analyzers()
    log.info("run_sequential start n_reviews=%d repeats=%d backend=%s",
             len(reviews), repeats, backend)

    per_review = {
        r["review_id"]: {
            "phone": r["phone_model"],
            "reviewer_stars": r.get("overall_rating", ""),
            "review": r["review_text"],
        }
        for r in reviews
    }
    total = len(reviews)
    bar = progress_slot.progress(0.0, text="Starting...")

    def _run(label, fn, phase_offset):
        for i, review in enumerate(reviews, start=1):
            ms_list, last_ratings, last_err = [], None, None
            for r_i in range(repeats):
                bar.progress(
                    phase_offset + (i - 1 + (r_i + 1) / repeats) / (total * 2),
                    text=f"{label} [{i}/{total}] {review['review_id']} "
                         f"(repeat {r_i + 1}/{repeats})",
                )
                ratings, ms, err = timed(fn, review["review_text"])
                ms_list.append(ms)
                if ratings is not None:
                    last_ratings = ratings
                elif err:
                    last_err = err
            per_review[review["review_id"]][f"{label}_min"] = min(ms_list)
            per_review[review["review_id"]][f"{label}_median"] = statistics.median(ms_list)
            per_review[review["review_id"]][f"{label}_ratings"] = last_ratings or {}
            per_review[review["review_id"]][f"{label}_error"] = repr(last_err) if last_err else ""

    _run("fable", fable, 0.0)
    _run("jev", jev, 0.5)

    bar.empty()
    rows = [{"review_id": rid, **cols} for rid, cols in per_review.items()]
    df = pd.DataFrame(rows)
    df["backend"] = backend
    log.info("run_sequential done rows=%d", len(df))
    return df


def _fmt_ms(x: float) -> str:
    return f"{x:,.0f} ms" if x >= 1000 else f"{x:.1f} ms"


def _ratings_to_str(d: dict) -> str:
    if not d:
        return "—"
    return ", ".join(f"{k} {v}★" for k, v in d.items())


def render_kpis(df: pd.DataFrame) -> None:
    fable = df["fable_min"].dropna()
    jev = df["jev_min"].dropna()
    f_med, j_med = fable.median(), jev.median()

    with st.container(horizontal=True):
        st.metric(
            "Fable median",
            _fmt_ms(f_med),
            f"min {_fmt_ms(fable.min())}   max {_fmt_ms(fable.max())}",
            border=True,
            chart_data=fable.tolist(),
            chart_type="bar",
            delta_color="off",
        )
        st.metric(
            "Jev median",
            _fmt_ms(j_med),
            f"min {_fmt_ms(jev.min())}   max {_fmt_ms(jev.max())}",
            border=True,
            chart_data=jev.tolist(),
            chart_type="bar",
            delta_color="off",
        )

    if j_med and f_med and j_med > 0:
        ratio = f_med / j_med
        st.markdown(
            f"### :material/rocket_launch: Jev is **{ratio:.1f}x** faster than "
            f"Claude Fable 5.1 at the median."
        )


def render_side_by_side(df: pd.DataFrame) -> None:
    with st.container(border=True):
        st.subheader("Latency per review — adjacent bars, milliseconds")
        chart_df = (
            df.set_index("review_id")[["fable_min", "jev_min"]]
              .rename(columns={"fable_min": "Fable (ms)", "jev_min": "Jev (ms)"})
        )
        st.bar_chart(chart_df, stack=False, height=340)
        st.caption(
            "Bars for the two providers sit side by side per review. Lower is faster. "
            "A hidden warm-up call runs once per session so these numbers exclude "
            "TLS/DNS setup."
        )


def render_horizontal_comparison(df: pd.DataFrame) -> None:
    summary = pd.DataFrame(
        [
            {"provider": "Claude Fable 5.1", "median_ms": df["fable_min"].median()},
            {"provider": f"Jev ({df['backend'].iloc[0]})", "median_ms": df["jev_min"].median()},
        ]
    )
    with st.container(border=True):
        st.subheader("Median latency across all reviews")
        st.bar_chart(summary, x="provider", y="median_ms", horizontal=True, height=200)


def render_review_outputs(df: pd.DataFrame) -> None:
    """Show what each provider produced for every review — same shape as main.py."""
    with st.container(border=True):
        st.subheader("Per-review outputs (like main.py)")
        st.caption(
            "For each review, both providers' Flipkart-style per-topic ratings. "
            "Only topics the provider thinks were discussed are shown."
        )
        for _, row in df.iterrows():
            rid = row["review_id"]
            with st.expander(
                f"**{rid}** — {row['phone']}  ·  "
                f"reviewer overall: {row['reviewer_stars']} ★",
                expanded=False,
            ):
                st.markdown(f"> {row['review']}")

                left, right = st.columns(2)
                with left:
                    st.markdown("**Jev**")
                    st.caption(f"{row['jev_min']:.1f} ms (min of repeats)")
                    if row["jev_error"]:
                        st.error(row["jev_error"])
                    else:
                        st.write(_ratings_to_str(row["jev_ratings"]))
                with right:
                    st.markdown("**Claude Fable 5.1**")
                    st.caption(f"{row['fable_min']:.1f} ms (min of repeats)")
                    if row["fable_error"]:
                        st.error(row["fable_error"])
                    else:
                        st.write(_ratings_to_str(row["fable_ratings"]))


def render_details(df: pd.DataFrame) -> None:
    display = df.copy()
    display["jev_ratings"] = display["jev_ratings"].apply(_ratings_to_str)
    display["fable_ratings"] = display["fable_ratings"].apply(_ratings_to_str)
    display = display.rename(
        columns={
            "review_id": "id",
            "phone": "phone",
            "reviewer_stars": "reviewer ★",
            "review": "review text",
            "fable_min": "fable min (ms)",
            "fable_median": "fable median (ms)",
            "jev_min": "jev min (ms)",
            "jev_median": "jev median (ms)",
            "jev_ratings": "jev topics",
            "fable_ratings": "fable topics",
        }
    )
    cols = [
        "id", "phone", "reviewer ★", "review text",
        "fable min (ms)", "fable median (ms)", "fable topics",
        "jev min (ms)", "jev median (ms)", "jev topics",
    ]
    if display["fable_error"].any() or display["jev_error"].any():
        cols += ["fable_error", "jev_error"]

    with st.container(border=True):
        st.subheader("Per-review table")
        st.caption("Wider `review text` column: hover a cell or click to expand.")
        st.dataframe(
            display[cols],
            hide_index=True,
            width="stretch",
            column_config={
                "review text": st.column_config.TextColumn(
                    "review text", width="large", help="Original review body"
                ),
                "jev topics": st.column_config.TextColumn("jev topics", width="medium"),
                "fable topics": st.column_config.TextColumn("fable topics", width="medium"),
            },
        )


def render_recent_log(lines: int = 60) -> None:
    """Tail app.log for a quick in-UI debug view."""
    from logging_config import LOG_FILE

    with st.container(border=True):
        st.subheader(f"Recent log tail — {LOG_FILE.name}")
        st.caption(f"Full log at `{LOG_FILE}`. Set `LOG_LEVEL=DEBUG` for verbose.")
        try:
            with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
                text = "".join(f.readlines()[-lines:])
        except FileNotFoundError:
            text = "(no log file yet — will appear after the first call)"
        st.code(text or "(empty)", language="log")


# --- UI --------------------------------------------------------------------

st.title("Jev vs Claude Fable 5.1 — latency")
st.caption(
    "Same phone-review dataset, two backends. Fable is called for every review "
    "first, then Jev, so each provider keeps its keep-alive pool warm across "
    "all its calls."
)

try:
    reviews = load_reviews(INPUT_FILE)
except FileNotFoundError:
    st.error(f"Couldn't find `{INPUT_FILE}` in the working directory.")
    st.stop()

with st.sidebar:
    st.header("Benchmark")
    with st.form("bench_form", border=False):
        limit = st.slider(
            "Reviews to run",
            min_value=1, max_value=len(reviews),
            value=min(5, len(reviews)),
        )
        repeats = st.slider(
            "Repeats per review",
            min_value=1, max_value=5, value=2,
            help="Each provider is called N times per review. The fastest call wins on the "
                 "row; all calls feed the summary.",
        )
        run = st.form_submit_button(
            "Run comparison", type="primary", icon=":material/play_arrow:"
        )

    st.divider()
    st.caption(
        "Requires `OPENROUTER_API_KEY` and `ANTHROPIC_API_KEY` in `.env`. "
        "Set `TYPESAFE_API_KEY` too to route Jev direct (skips the OpenRouter proxy). "
        f"Dataset: `{INPUT_FILE}` ({len(reviews)} reviews)."
    )

progress_slot = st.empty()

if run:
    log.info("streamlit user clicked run limit=%d repeats=%d", limit, repeats)
    with st.spinner(f"Running {limit} reviews x {repeats} repeats — Fable first, then Jev..."):
        st.session_state["results"] = run_sequential(reviews[:limit], repeats, progress_slot)

results: pd.DataFrame | None = st.session_state.get("results")

if results is None:
    st.info(
        "Pick the number of reviews and repeats in the sidebar, then click **Run comparison**. "
        "Fable runs first for every review, then Jev — keeping each connection pool warm across "
        "all its calls."
    )
    render_recent_log()
else:
    render_kpis(results)

    tab_chart, tab_outputs, tab_table, tab_log = st.tabs(
        [":material/bar_chart: Latency charts",
         ":material/reviews: Per-review outputs",
         ":material/table_view: Table",
         ":material/description: Log tail"]
    )
    with tab_chart:
        render_side_by_side(results)
        render_horizontal_comparison(results)
    with tab_outputs:
        render_review_outputs(results)
    with tab_table:
        render_details(results)
    with tab_log:
        render_recent_log()