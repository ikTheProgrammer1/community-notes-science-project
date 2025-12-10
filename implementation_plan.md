# Narrative Life-Cycle Visualization

## Goal Description
Add a Time-Series Analysis ("Narrative Life-Cycle") to the dashboard to visualize the momentum of narrative themes over time. This helps identify if a threat is growing, stable, or fading.

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
