# Narrative Life-Cycle Visualization

## Goal Description
Add a Time-Series Analysis ("Narrative Life-Cycle") to the dashboard to visualize the momentum of narrative themes over time. This helps identify if a threat is growing, stable, or fading.

### Phase 3: Data Integrity Pipeline (Pipeline Split)
- **Goal**: Resolve metric fluctuations ("Hallucinations") caused by random sampling.
- **Metric Engine**:
  - Remove `LIMIT` from all DuckDB queries (`search_notes_by_keyword`, `search_controversial_notes`).
  - Calculate stats on 100% of matching rows.
- **Visual Engine**:
  - Implement `deterministic_sample(df, n=5000)` using `random_state=42`.
  - Use this sampled subset ONLY for rendering heavy charts (e.g. Scatterplots).
- **Verification**: Run "Elon Musk" search 3x, verify identical metrics.

## Proposed Changes

### Dashboard Logic
#### [MODIFY] [dashboard.py](file:///Users/nicolasmatta/dev/x-API-Docs/dashboard.py)
- Implement `generate_narrative_lifecycle(themes)` function.
    - Iterate through clusters.
    - **[NEW] Filter Data**: Remove records with `date > Now` and Optional `date < 2022`.
    - Aggregate Note Count by Week (`freq='W-MON'`).
    - Create a stacked dataframe.
    - Generate an Altair Stacked Area Chart.

## Winning Formula Analysis
### Goal Description
Identify prescriptive insights by comparing successful (HELPFUL) and failed (NOT_HELPFUL) notes.

### Dashboard Logic
#### [MODIFY] [dashboard.py](file:///Users/nicolasmatta/dev/x-API-Docs/dashboard.py)
- **New Query Function**: `fetch_comparative_data(keyword)`
    - Select notes where status is HELPFUL or NOT_HELPFUL.
    - Limit to ~500 of each for performance.
- **Analysis Logic**: `analyze_success_drivers(df)`
    - **Sentiment**: Use `TextBlob` to classify Positive/Neutral/Negative.
    - **Length**: Group into Short (<100), Medium (100-200), Long (>200).
    - **Sources**: Regex check for `.gov`, `.edu`, `.pdf` vs `youtube`, `twitter`.
    - **Metric**: Calculate "Diff from Average Win Rate" for each attribute.
- **Visualization**:
    - Display "Key Drivers" (Attributes with highest positive correlation).
    - Bar chart comparing Win Rates.
- Update `run_intelligence_report` to call this function after clustering.

## Semantic Precedent Search (Hall of Fame)
### Goal Description
Provide "Best in Class" examples to inspire users by finding the highest-rated helpful notes for a topic.

### Dashboard Logic
#### [MODIFY] [dashboard.py](file:///Users/nicolasmatta/dev/x-API-Docs/dashboard.py)
- **New Query Function**: `fetch_hall_of_fame(keyword)`
    - 1. Search `notes` for `keyword` and status `HELPFUL` (Limit ~100).
    - 2. Query `ratings` for those `noteId`s where `helpfulnessLevel = 'HELPFUL'`.
    - 3. Count ratings per note.
    - 4. Join and Sort by Count DESC.
    - **[NEW] Deduplication**: Iterate through candidates, skip if `SequenceMatcher(a, b).ratio() > 0.8`.
    - 5. Return Top 5 Unique.
- **UI Logic**:
    - Display cards with "🏆 Hall of Fame" badge.
    - **[NEW] Formatting**:
        - Convert Tweet ID to `https://x.com/i/web/status/...` link.
        - Extract URLs from summary text and move to bottom.
    - **[FINAL] Language Filter**:
        - Filter `fetch_hall_of_fame` results using stop-word heuristic (English vs Portuguese/Spanish).
    - **[FINAL] UI Polish**:
        - Label: "Consensus Rating" (Gold > 30, Silver < 30).
        - Sources: Rename `x.com` / `twitter.com` to "Primary Source (Tweet)".
    - **[VISUAL] Unbox Results**:
        - Render notes in `st.success` containers.
        - Show text in blockquote.
        - Footer for sources/links.

## Verification Plan

### Automated Tests
- Create a test case in `tests/test_dashboard_debug.py` that mocks the clustering output and verifies the chart generation logic throws no errors.

### Manual Verification
- Run the dashboard (`bash run.sh`).
- Search for a topic with sufficient history (e.g., "Covid", "Ukraine", or general terms like "The").
- Verify the "Narrative Life-Cycle" chart appears under the Narrative Themes section.
- Check that the x-axis is time and y-axis is volume, stacked by theme.

### Phase 5: Smart Context & Conversational Workflow
- **Goal**: "Tab-Aware" context injection and seamless "Prime & Chat" flow.
- **Architecture Change**: Replace `st.tabs` with `st.radio` (Nav Bar) to track `active_view` server-side.
- **Context Payloads**:
  - `Intelligence Report`: Top 10 Search Results + Summary stats.
  - `Controversy Monitor`: Narrative Clusters (Top 5 themes, growth).
  - `Winning Formula`: Success Stats (Win Rates by length, sentiment).
- **Workflow**: 
  - Sidebar checks `active_view`.
  - "Analyze" button loads specific JSON payload into `st.session_state['webllm_context']`.
  - AI is "Primed" with this data but Chat Input remains open for questions.

### Phase 6: Explicit Context Workflow
- **Goal**: Manual, Explicit Control. One Context at a time.
- **Helper Function**: `inject_context(data, primer_text)`
  - Updates `ai_active_context` and `ai_system_primer`.
  - Triggers sidebar focus.
- **Integration Points**:
  - `Astroturf Meter`: "Analyze Coordination" (Gini/Author stats).
  - `Crisis Heatmap`: "Analyze Timing" (Hour/Day tables).
  - `Narrative Themes`: "Analyze Narratives" (Cluster summaries).
  - `Evidence Locker`: "Analyze Raw Logs" (Top 10 notes).
- **JS Update**: Receive `system_primer` to customize initial AI prompt (e.g. "You are looking for bots...").
