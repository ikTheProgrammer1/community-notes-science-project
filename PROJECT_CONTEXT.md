# Community Notes Analytics - Project Context

> **Purpose**: This document provides a high-level overview of all project files to give a new chat session proper context for modifications.

## Project Overview

This is a **Streamlit-based forensic analytics dashboard** for analyzing Twitter/X Community Notes data. It enables pattern analysis, evidence-based claims verification, and case management for investigative journalism workflows.

**Tech Stack**: Python, Streamlit, DuckDB, xAI/Grok API, WebLLM (local LLM via WebGPU)

---

## Core Application Files

### `dashboard.py` (2251 lines)
**The main Streamlit application.**

- Renders the full UI: search input, case management bar, chat interface, evidence inspector
- Contains data engine functions (`search_notes_by_keyword`, `cluster_narratives`, `fetch_hall_of_fame`)
- Implements the Evidence Contract rendering (`render_forensic_message`)
- Manages session state and derived state patterns
- Integrates with `CaseManager` for persistence
- Key functions:
  - `main()`: Entry point, renders case bar, search form, and routes to views
  - `run_chat_interface()`: Handles Q&A with LLM, saves turns to case files
  - `render_evidence_inspector()`: Modal dialog for verifying cited notes
  - `render_forensic_message()`: Displays structured JSON evidence with clickable refs

---

### `cloud_intel.py` (472 lines)
**Universal LLM adapter for xAI (Grok), OpenAI, and Anthropic.**

- `UniversalCloudAdapter` class: Unified interface for multiple LLM providers
- Implements streaming responses with validation/repair logic
- `validate_and_repair_json()`: Ensures LLM output matches Evidence Contract schema
- `generate_forensic_report_v2()`: Main entry point for structured evidence generation
- `get_investigator_system_prompt()`: Returns the forensic analyst persona prompt
- Supports models: `grok-2-1212`, `grok-3-mini-beta`, `grok-3-beta`, `grok-4`

---

### `case_manager.py` (152 lines)
**Persistence layer for forensic cases and evidence bundles.**

- `CaseManager` class with atomic JSON writes (crash-safe)
- Storage paths: `artifacts/cases/`, `artifacts/bundles/`
- Key methods:
  - `create_case(name)`: Creates new investigation
  - `load_case(case_id)`: Retrieves case with all turns
  - `save_turn(case_id, turn_data)`: Appends Q&A turn to case
  - `save_bundle(query_id, bundle)`: Persists evidence for reproducibility
  - `list_cases()`: Returns cases sorted by update time

---

### `private_intel.py` (209 lines)
**Local LLM interface using WebLLM (runs in browser via WebGPU).**

- `run_private_intel()`: Renders a client-side LLM chat component
- Uses Llama-3.2-3B model loaded entirely in browser
- No data leaves the user's machine (privacy-preserving)
- Receives dashboard context as input for analysis

---

## Scripts Directory (`scripts/`)

| File | Purpose |
|------|---------|
| `build_db.py` | Ingests TSV files into DuckDB artifact (`community_notes_full.duckdb`) |
| `deploy_gcp.sh` | Deploys to Google Cloud Run with GCS volume mount |
| `download_data.py` | Downloads Community Notes TSV files from Twitter |
| `generate_bridge_intelligence.py` | Generates cross-partisan "bridge" note analysis |
| `generate_trust_scores.py` | Computes source credibility scores |
| `visualize_*.py` | Various data visualization scripts |

---

## Tests Directory (`tests/`)

| File | Purpose |
|------|---------|
| `test_evidence.py` | Tests Evidence Contract schema validation |
| `test_reproducibility.py` | Tests evidence bundle persistence and replay |
| `test_dashboard_debug.py` | Integration tests for dashboard functions |
| `diagnose_xai.py` | Diagnostic script for xAI API connectivity |
| `test_lifecycle_filtering.py` | Tests narrative timeline generation |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python project metadata and dependencies |
| `requirements.txt` | Pip-installable dependencies |
| `Dockerfile` | Container definition for Cloud Run deployment |
| `run.sh` | Local dev server launcher (`uv run streamlit run dashboard.py`) |
| `.gitignore` | Excludes `artifacts/`, `.venv/`, etc. |

---

## Data Directories

| Path | Contents |
|------|----------|
| `artifacts/` | DuckDB database, case files (`cases/`), evidence bundles (`bundles/`) |
| `data/` | Raw TSV files from Community Notes (notes, ratings, status history) |
| `docs/` | Documentation files |

---

## Key Architectural Patterns

1. **Evidence Contract**: LLM outputs structured JSON with claims, evidence refs, and `cannot_conclude` fallbacks
2. **Derived State Rendering**: Chat messages rebuilt from case files on each render (no session state wipes)
3. **Atomic Persistence**: All case/bundle writes use temp file → rename pattern
4. **Reproducibility**: Every query has a `query_id` hash linking to its evidence bundle
5. **Evidence Inspector**: Modal verifies cited notes exist in the bundled context

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CN_DUCKDB_PATH` | Path to DuckDB artifact (defaults to `artifacts/community_notes_full.duckdb`) |
| `XAI_API_KEY` | xAI/Grok API key for forensic analysis |
| `K_SERVICE` | Cloud Run service name (auto-set by GCP) |
| `CN_STRICT` | Enable strict mode (fail if artifact missing) |
