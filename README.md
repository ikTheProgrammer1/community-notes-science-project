# Community Notes Forensics Workbench

Local-first analytics and investigation tooling built on the public Community Notes dataset.
It helps you answer: **what spiked, who drove it, and what narratives emerged** — with optional AI assistance.

**Demo:** *[Add Link]*
**Screenshots:** *[Add Image]*

---

## What this is
A Streamlit "war-room" UI backed by DuckDB + Pandas that turns Community Notes TSV dumps into fast, reproducible analytics.
Optionally, you can enable:
- **Local assistant** (WebGPU) for private on-device summaries
- **Cloud Investigator** (explicit API key gate) for deeper reasoning when you choose to uplink

> Default behavior is local-first. Cloud calls are opt-in and gated.

---

## Key capabilities
- **Crisis / Defense Speed:** time-to-status / response-window style metrics to locate crisis windows
- **Coordination signals:** concentration metrics to detect "dominated by a small % of authors" patterns
- **Narrative clustering:** TF-IDF + clustering to group large note corpora into themes
- **Note effectiveness signals:** lightweight correlations (e.g., sources / language) with helpful outcomes

---

## Architecture (high level)
- **Data engine:** DuckDB + Pandas (local OLAP + feature engineering)
- **App/UI:** Streamlit (multi-tab workflow + persistent state)
- **Visualization:** Altair / PyDeck
- **Optional AI:**
  - Local: WebGPU (WebLLM) for on-device assistant behavior
  - Cloud: Investigator mode via API key (only when explicitly enabled)

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

### 1) Get data + build local DB

```bash
python scripts/download_data.py
python scripts/build_db.py
```

> If you just want to see the UI quickly, use sample mode:

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

* You do **not** need to send me your data to run it.
* The repo includes scripts to download and build a local DuckDB.

See: [`docs/dataset.md`](docs/dataset.md)

---

## Privacy & Cloud Investigator mode

By default, analytics run locally and nothing is sent externally.

Cloud Investigator mode:

* is **disabled by default**
* requires an API key in your environment
* is only used after an explicit user action in the UI

---

## Known limitations

* WebGPU local model load time varies by device/browser
* Some heavy visualizations use deterministic sampling for UI responsiveness
* First-time DB build can take a while depending on dataset size

---

## Roadmap (next 1-2 weeks)

* Performance pass: caching, precomputed aggregates, faster page loads
* Exportable "investigation report" (markdown/PDF)
* Better cluster labeling + explainability
* Improve local-only mode and make cloud mode clearly optional

---

## Repo structure

```text
dashboard.py             # Streamlit entrypoint
scripts/                 # download/build utilities
data/                    # raw TSVs (gitignored)
docs/                    # dataset + architecture docs
  - analysis.md          # Analysis recipes
  - dataset.md           # Schema overview
  - strategy.md          # Architecture deep-dive
```

---

