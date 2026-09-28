test — Jev vs Claude Fable 5.1 (smartphone review analyzer)
Turns free-text smartphone reviews into Flipkart-style per-topic star ratings, and shows head-to-head that Jev is dramatically faster than a frontier LLM at the same structured-extraction task.

Two backends, same input, same output shape:

Jev via the TypeSafe SDK — direct if TYPESAFE_API_KEY is set (fastest), otherwise routed through OpenRouter.
Claude Fable 5.1 via the Anthropic SDK, using JSON-schema structured outputs.
Ships with:

a CLI runner (main.py) to score a whole CSV with either backend
a CLI latency benchmark (benchmark.py) — runs all Fable calls first, then all Jev calls, and prints "Jev is Nx faster than Fable at the median"
a Streamlit latency dashboard (streamlit_app.py) — same run order, adjacent-bar chart per review, KPI cards
Why Jev wins on latency
Jev is a small purpose-built model that answers all 14 questions per review in one HTTP call, with no chain-of-thought overhead. Claude Fable 5.1 is a frontier reasoning model — it always thinks, and it emits the whole JSON blob token by token. For a fixed structured-extraction task like this, Jev routinely runs ~10–100x faster.

The comparison in this repo is set up to be fair, not favorable:

HTTP/2 + persistent keep-alive for the Jev client, so we never re-pay TLS setup between calls.
A warm-up call per provider before the timed loop — the first HTTP call to any host pays connection setup once.
All Fable calls first, then all Jev calls — never interleaved. Each provider keeps its connection pool hot across every call it makes.
Repeat-per-review support — each row reports the fastest of N attempts, so a single unlucky network blip doesn't tank a provider.
If you want to see the raw ~100x number, set TYPESAFE_API_KEY in .env — the analyzer will skip the OpenRouter proxy hop and call TypeSafe directly.

How the analyzer works
For each review, per topic:

a mention probability — how confident the model is the reviewer expressed an opinion on that topic
a rating — the reviewer's satisfaction on a 1–5 star scale
A topic's rating is only kept when its mention probability is at least 0.5. Topics that survive are then averaged across all reviews to produce the overall summary.

Topics: Camera, Battery, Display, Design, Performance, Build Quality, Value for Money

Both backends return the same shape ({"Camera": 4.2, "Battery": 1.8, ...}), so main.py can swap providers with one flag and the benchmark tools can time them fairly.

Project structure
File	Purpose
main.py	Reads the CSV, analyzes each review with the chosen provider, prints the Flipkart-style summary
analyzer.py	Jev backend — HTTP/2 keep-alive, TypeSafe-direct if TYPESAFE_API_KEY set, else OpenRouter
fable_analyzer.py	Fable 5.1 backend (Anthropic SDK + JSON-schema structured outputs)
benchmark.py	CLI latency benchmark: Fable-then-Jev, per-review + summary
streamlit_app.py	Web latency dashboard: KPIs, adjacent-bar chart, per-review table
questions.py	Topic list and the 14 Jev questions (2 per topic)
aggregation.py	Averages per-review ratings into one score per topic
synthetic_phone_reviews.csv	50 synthetic sample reviews
.env.example	Template for the API keys
Requirements
Python 3.10+ (the repo's .venv uses Python 3.11)
OpenRouter API key (openrouter.ai) — for Jev via the OpenRouter route
Anthropic API key (console.anthropic.com) — for Fable
(Optional but recommended for max Jev speed) TypeSafe API key (docs.typesafe.ai) — enables the direct Jev route
Setup — step by step
Windows PowerShell paths below; on macOS/Linux, swap .\.venv\Scripts\ for ./.venv/bin/.

1. Create or reuse a virtual environment
python -m venv .venv                                        # skip if .venv already exists
.\.venv\Scripts\python.exe -m ensurepip --upgrade           # only if pip is missing
2. Install dependencies
.\.venv\Scripts\python.exe -m pip install python-dotenv "typesafe-sdk[http2]" anthropic streamlit pandas
typesafe-sdk[http2] pulls in the HTTP/2 extras — analyzer.py uses them for keep-alive.

3. Add your API keys
Copy .env.example to .env and fill in the two required keys (and the optional third):

OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_API_KEY=sk-ant-...
TYPESAFE_API_KEY=ts_...          # optional; if present, Jev calls skip the OpenRouter proxy
.env is already in .gitignore.

4. (Optional) Bring your own reviews
The repo ships with synthetic_phone_reviews.csv. To use your own, produce a CSV with:

Column	Description
review_id	Unique review ID
phone_model	Phone name
overall_rating	Integer 1–5 star rating given by the reviewer
review_text	The review body (free text)
is_synthetic	true/false — used only as a label
Pass --input yourfile.csv to main.py or benchmark.py, or edit INPUT_FILE at the top of streamlit_app.py.

Usage
Score a full CSV (main.py)
.\.venv\Scripts\python.exe main.py                    # Jev (default)
.\.venv\Scripts\python.exe main.py --provider fable   # Fable 5.1
Latency benchmark from the CLI (benchmark.py)
.\.venv\Scripts\python.exe benchmark.py                          # 10 reviews, 1 repeat, warmup on
.\.venv\Scripts\python.exe benchmark.py --limit 25 --repeats 3   # 25 reviews, 3 calls each
.\.venv\Scripts\python.exe benchmark.py --limit 0                # all reviews
.\.venv\Scripts\python.exe benchmark.py --no-warmup              # skip warm-up
Order of operations:

Print which Jev backend is active (typesafe-direct or openrouter-proxy).
Warm-up call to each provider (Fable then Jev), unless --no-warmup.
All Fable calls, back to back — per-review min / median in ms.
All Jev calls, back to back — per-review min / median in ms.
Overall min / median / mean / max per provider.
A single closing line: >>> Jev is Nx faster than Claude Fable 5.1 at the median.
Latency dashboard in the browser (streamlit_app.py)
.\.venv\Scripts\streamlit.exe run streamlit_app.py
Streamlit prints a http://localhost:8501 URL — open it. In the sidebar, pick how many reviews to run and how many repeats per review, then click Run comparison. You get:

KPI cards — median latency for Fable and Jev with mini sparklines, plus a big Jev is Nx faster headline.
Latency per review — an adjacent-bar chart (Fable and Jev side by side, one pair per review), rendered with st.bar_chart(..., stack=False).
Median latency across all reviews — a horizontal bar showing the two medians so the gap is impossible to miss.
Per-review table — min and median ms for each provider plus any error messages.
Fable is called for every review first, then Jev — never interleaved — so each provider's keep-alive pool stays hot for all of its calls.

Making the gap as big as it should be
If the two providers still look close on your machine after all of the above, work through this list:

Set TYPESAFE_API_KEY. The OpenRouter route adds a proxy hop. Direct TypeSafe is where the "100x" number comes from.
Bump --repeats. Use --repeats 3 or more — a single call is too noisy to compare a small model to a frontier one.
Warm up. Keep warm-up on (the default). Without it the very first call to each host pays TLS + DNS + connection setup and skews the numbers.
Run a bigger --limit. 3 reviews is too few to see medians settle. 20+ is better.
Check network. Both routes go over your internet connection. If it's saturated or high-latency, both providers suffer and the ratio compresses.
Make sure Fable really is Fable. fable_analyzer.py targets claude-fable-5-1. On that model thinking is always on — that's the point of the comparison. Don't swap it for Haiku "to be fair"; Fable is the frontier baseline you're comparing against.
Cost notes
Jev on OpenRouter — currently priced with free output tokens; check openrouter.ai/models for the live rate.
Jev direct on TypeSafe — see docs.typesafe.ai for pricing.
Fable 5.1 — $10 / $50 per million input/output tokens on the Anthropic API. Each review is small, but running the whole 50-review CSV on Fable will still show up on your bill. The benchmark defaults to 10 reviews and 1 repeat for that reason.
Troubleshooting
KeyError: 'OPENROUTER_API_KEY' / 'ANTHROPIC_API_KEY' .env isn't in the working directory or a key is misspelled. Run commands from the project root — python-dotenv reads .env relative to the CWD.

ModuleNotFoundError: No module named 'streamlit' / 'anthropic' / 'typesafe_sdk' / 'httpx2' You installed into a different interpreter than the one running the script. Prefix commands with .\.venv\Scripts\python.exe, or activate the venv (.\.venv\Scripts\Activate.ps1) first. httpx2 comes in via typesafe-sdk[http2] — reinstall with .\.venv\Scripts\python.exe -m pip install "typesafe-sdk[http2]" if it's missing.

No module named pip when running python -m pip install … The venv was created without pip. Fix once with .\.venv\Scripts\python.exe -m ensurepip --upgrade.

Fable call raises BadRequestError about output_config Your anthropic SDK is too old. .\.venv\Scripts\python.exe -m pip install -U anthropic.

UnicodeEncodeError when a CLI script prints ★ Windows console default codepage can't render the star. Run in Windows Terminal (UTF-8) or set PYTHONIOENCODING=utf-8 first.

One provider errors on a review The benchmark keeps going. The failing row shows the exception in notes / the _error column; summary stats are computed over successful calls only.