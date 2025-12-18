# Community Notes Forensics Workbench (VIP Intelligence Platform)

Local-first analytics and investigation tooling built on the public Community Notes dataset.
It helps answer: **what spiked, who drove it, and what narratives emerged**, with optional AI assistance.

**Demo (2–3 min):** *[ADD LINK]*
**Screenshots / GIF:** *[ADD IMAGE]*
**Status:** 0→1 prototype, active development, iterating on performance and UX

---

## Mission and motivation
**Mission:** make Community Notes analysis accessible to anyone.

I built this because Community Notes is one of the few misinformation response systems that scales without becoming purely centralized moderation. Notes only gain broad visibility when people with different viewpoints converge on a rating, which pushes notes toward being evidence-based, clear, and widely defensible.

I also like that the ecosystem is open. The public dataset and the surrounding research make it possible for developers to build tools that improve transparency, analysis, and participation without privileged access.

This project turns the raw TSV dumps into a practical workbench you can run locally and use as a situation room during fast-moving events.

---

## What this is
A Streamlit "war-room" UI backed by DuckDB and Pandas that turns Community Notes TSV dumps into fast, reproducible analytics.

Optionally, you can enable:
*   **Local assistant** via WebGPU for private, on-device summaries with no LLM API calls
*   **Investigator mode** via a "bring-your-own" API key gate for deeper reasoning when you choose to uplink

> Default behavior is local-first. Cloud calls are opt-in and gated.

---

## Key capabilities
*   **Crisis and Defense Speed:** time-to-status and response-window metrics to locate crisis windows
*   **Coordination signals:** concentration metrics to detect "dominated by a small percent of authors" patterns
*   **Narrative clustering:** TF-IDF and clustering to group large note corpora into themes
*   **Note effectiveness signals:** lightweight correlations (such as sources and language) with helpful outcomes

**Investigator mode (optional, BYO API key):** a chat-style workflow that lets you ask deeper questions over Community Notes data. When enabled, the user supplies their own API key and the app uses it only after explicit action.

Examples of questions it can help answer:
*   Which tweets repeatedly attract notes in a given time window
*   Which accounts are most frequently associated with tweets that get corrected by notes
*   How a narrative evolves over time based on note themes and linked tweets

*Privacy note: Investigator mode is disabled by default and only sends the minimum selected context needed for the query, not the full dataset.*

---

## Architecture (high level)
*   **Data engine:** DuckDB and Pandas for local OLAP and feature engineering
*   **App and UI:** Streamlit multi-tab workflow with persistent state
*   **Visualization:** Altair and PyDeck
*   **Optional AI:**
    *   *Local:* WebGPU with WebLLM for on-device assistant behavior
    *   *Cloud:* Investigator mode via API key (only when explicitly enabled)

*Add a simple diagram at `docs/architecture.png` and link it here.*

---

## Quickstart

### 0) Install dependencies
This repo uses `uv` (recommended) but `pip` works too.

**uv**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

**pip (alternative)**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1) Get data and build local DB

```bash
python scripts/download_data.py
python scripts/build_db.py
```

If you just want to boot the UI quickly, use sample mode:

```bash
python scripts/build_db.py --sample
```

### 2) Run the app

```bash
bash run.sh
# or: streamlit run dashboard.py
```

---

## Data

This project is designed around the **public Community Notes TSV dataset**.

*   You do **not** need to send me your data to run it.
*   The repo includes scripts to download and build a local DuckDB.

See [`docs/dataset.md`](docs/dataset.md)

---

## Privacy, accessibility, and Investigator mode

### Local-first by default

This version is designed to run without API calls, including no LLM API calls. Optional AI assistance runs locally via WebGPU so the workflow is private and accessible.

**Tradeoffs:**
*   WebGPU model load time and performance vary by device and browser
*   Streamlit is great for moving fast, but the UI can be less responsive than a custom frontend

My next step is to add adaptive routing: if a user’s machine cannot reasonably run WebGPU, the app can optionally route to a cloud model only with explicit opt-in and with clear controls over what context is sent.

### Investigator mode (optional, gated)

Investigator mode is for deep-dive queries such as tracing how a narrative evolves, surfacing related notes and tweets, and generating structured investigation summaries for human review. It is disabled by default, requires a user-provided API key, and is only used after an explicit user action in the UI.

---

## Future direction

A direction I am exploring is integrating the **X API** to surface currently trending or rapidly spreading claims so users can prioritize what to review and respond to. The goal is to make it easier for a human to go from "this is spreading" to "here is relevant context and evidence" to "here is a well-structured draft note."

Any note-writing assistance would be **human-in-the-loop drafting**. The user reviews, edits, and submits. The intent is to reduce friction for good-faith participation while maintaining accountability and quality.

---

## Known limitations

*   WebGPU local model load time varies by device and browser
*   Some heavy visualizations use deterministic sampling for UI responsiveness
*   First-time DB build can take a while depending on dataset size

---

## Roadmap (next 1 to 2 weeks)

*   Performance pass: caching, precomputed aggregates, faster page loads
*   Exportable "investigation report" in markdown or PDF
*   Better cluster labeling and explainability
*   Adaptive inference routing for users without sufficient local resources, opt-in only
*   Improve local-only mode and keep cloud mode clearly optional

---

## Repo structure

```text
dashboard.py             # Streamlit entrypoint
scripts/                 # download and build utilities
data/                    # raw TSVs (gitignored)
db/                      # DuckDB outputs (gitignored)
docs/                    # dataset and architecture docs
  - dataset.md           # schema overview
  - analysis.md          # analysis recipes
  - strategy.md          # architecture deep dive
run.sh                  # convenience runner
```

---

## License

MIT

## Contact

**Nicolas Matta**
*   Email: [EMAIL]
*   LinkedIn: [LINKEDIN]
*   X: [X]
