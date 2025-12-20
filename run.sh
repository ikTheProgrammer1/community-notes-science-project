#!/bin/bash
# Run the dashboard with uv
# Local dev: App auto-detects artifacts (no CN_DUCKDB_PATH needed)
uv run streamlit run dashboard.py
