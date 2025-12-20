# Community Notes Analytics: Complete Feature Reference

## Overview
A forensic analytics dashboard for X's Community Notes data. Analyzes 2.2M+ notes to detect misinformation patterns, measure consensus, and identify effective counter-strategies.

---

## 🔍 Search Interface
**How it works:** Enter a keyword (e.g., "Elon Musk", "vaccine", "Tesla"). The app queries the DuckDB database for all notes containing that keyword in their summary text.

---

## 📊 Tab 1: Analytics Report

### 1.1 Top Metrics Row
| Metric | What It Measures | Source |
|--------|------------------|--------|
| **Total Notes** | Count of notes matching keyword | `SELECT COUNT(*) FROM notes` |
| **Confirmed Threats** | Notes rated "Currently Rated Helpful" | `WHERE currentStatus = 'CURRENTLY_RATED_HELPFUL'` |
| **Median Defense Lag** | Hours between note creation and first "Helpful" status | `timestampMillisOfFirstNonNMRStatus - createdAtMillis` |

### 1.2 Attack Signature (Bar Chart)
**Purpose:** Profile the *type* of misinformation being flagged.

**Algorithm:** Aggregates boolean columns from the `notes` table:
- `misleadingFactualError`
- `misleadingManipulatedMedia`
- `misleadingOutdatedInformation`
- `misleadingMissingImportantContext`

**Chart:** Horizontal bar chart showing count per category.

### 1.3 Arsenal of Truth (Bar Chart)
**Purpose:** Identify which websites are most frequently cited in *helpful* notes.

**Algorithm:** Regex extract domains from `summary` field → count occurrences → rank.

**Insight:** `.gov`, `.edu`, and primary sources (original tweets) correlate with higher success rates.

### 1.4 Astroturf Meter
**Purpose:** Detect coordinated campaigns (bot networks).

**Algorithm:**
1. Count notes per author (`noteAuthorParticipantId`).
2. Calculate **Top 1% Control**: What % of notes are written by the top 1% of authors?
3. **Repeat Offenders**: Authors with >1 note on this topic.

| Metric | Meaning |
|--------|---------|
| Top 1% Control >20% | Possible coordination |
| Repeat Offenders high | Organized campaign likely |

### 1.5 Crisis Response Heatmap
**Purpose:** Identify *when* misinformation activity peaks.

**Algorithm:** 
1. Parse `createdAtMillis` → extract Day of Week + Hour (UTC).
2. Aggregate count into 7×24 grid.

**Chart:** Altair heatmap (X: Hour 0-23, Y: Day of week, Color: Note count).

**Use Case:** Staffing optimization — when should responders be active?

### 1.6 Narrative Themes (Clustering)
**Purpose:** Group thousands of notes into coherent narratives.

**Algorithm:**
1. Sample 3,000 notes (for performance).
2. **TF-IDF Vectorization** (max 1,000 features, English+Spanish stop words removed).
3. **KMeans Clustering** (k = min(5, n/10)).
4. Label each cluster by top 3 TF-IDF terms.

**Output:** Expandable list of themes with sample notes.

### 1.7 Narrative Life-Cycle (Stacked Area Chart)
**Purpose:** Track how narratives evolve over time.

**Algorithm:**
1. For each cluster, group notes by week (`resample('W-MON')`).
2. Stack counts by theme.

**Chart:** Altair stacked area (X: Time, Y: Volume, Color: Theme).

**Insight:** See if a narrative is growing, stable, or fading.

### 1.8 Evidence Locker
**Purpose:** Raw data exploration.

**Output:** DataTable of top 20 notes (summary, status, tweet ID).

---

## 🔥 Tab 2: Controversy Monitor

### 2.1 Top Metrics
| Metric | What It Measures |
|--------|------------------|
| **Top Crisis Velocity** | Ratings/day for the hottest note |
| **Max Heat** | Total ratings on the most contested note |
| **Active Battles** | Count of "Needs More Ratings" notes |

### 2.2 Conflict Velocity
**Purpose:** Find notes with rapid rating activity (high engagement = wedge issue).

**Algorithm:**
1. Filter notes with `currentStatus = 'NEEDS_MORE_RATINGS'`.
2. Aggregate ratings per note.
3. Calculate `velocity = rating_count / days_since_creation`.
4. Sort DESC.

### 2.3 Stalemate Analysis
**Purpose:** Understand *why* notes are stuck (not reaching consensus).

**Algorithm:** Count rating reasons:
- `argumentativeOrBiased`
- `noteNotNeeded`
- `sourcesNotVerified`

**Chart:** Bar chart of reason counts.

### 2.4 Wedge Clustering
**Purpose:** Apply narrative clustering specifically to controversial notes.

**Algorithm:** Same TF-IDF + KMeans as Analytics Report, but only on "Needs More Ratings" subset.

### 2.5 Active Battles List
**Output:** Expandable list of high-velocity notes with:
- Velocity (ratings/day)
- Total ratings
- Note summary
- Tweet ID link

---

## 🏆 Tab 3: The Winning Formula

### 3.1 Success Driver Analysis
**Purpose:** Identify *what makes a note successful*.

**Algorithm:**
1. Fetch ~500 HELPFUL notes + ~500 NOT_HELPFUL notes.
2. Extract features:
   - **Sentiment:** TextBlob polarity (Positive/Neutral/Negative)
   - **Length:** Short (<100 chars) / Medium / Long (>200)
   - **Source Type:** `.gov`/`.edu` vs `youtube`/`twitter`
3. Calculate **Win Rate** per feature.
4. Compare to baseline win rate.

**Output:**
- ✅ **Best Practices:** Features with highest win rate boost.
- ❌ **Risky Tactics:** Features that correlate with failure.

### 3.2 Win Rate Bar Chart
**Chart:** Bar chart (X: Feature, Y: Win Rate %, Color: Category).

### 3.3 Hall of Fame
**Purpose:** Find "gold standard" notes for inspiration.

**Algorithm:**
1. Find HELPFUL notes matching keyword.
2. Count ratings per note.
3. Deduplicate (SequenceMatcher similarity >0.8 = skip).
4. Return top 5 unique.

**Output:** Cards with:
- 🏆 Score (rating count)
- Note text
- Source links (with "Primary Source (Tweet)" labeling)

---

## 🕵️ Tab 4: Investigator (Cloud AI)

### Gatekeeper
**Requires:** API key for xAI (Grok), OpenAI (GPT-4), or Anthropic (Claude).

**Why:** Local WebGPU models (Llama-3.2) are insufficient for deep forensic reasoning.

### Forensic Query Interface
**Input:** Natural language query (e.g., "Trace the first instance of the 'fraud' claim").

**Context:** Top 50 most recent notes for the keyword.

**Output:** Streaming Markdown report generated by the selected LLM.

### Agentic Protocol
For xAI (Grok), the model can use:
- `web_search`: Cross-reference claims against real-time news.
- `x_search`: Find original tweets by ID.

---

## 🧠 WebGPU Inline Insight Buttons

### What Are They?
Throughout the dashboard, you'll see red **"⚡ GENERATE STRATEGIC INSIGHT"** buttons next to each major visualization. These buttons trigger **local AI analysis** using WebLLM (Llama-3.2-3B) running entirely in your browser via WebGPU.

### Where They Appear
| Section | Button Context |
|---------|----------------|
| Attack Signature | "Analyze the misinformation tactics. Explain why X is the dominant vector." |
| Arsenal of Truth | "Analyze the defensive sources. Which websites are winning the argument?" |
| Astroturf Meter | "Analyze the bot coordination levels. Is this organic or artificial?" |
| Crisis Heatmap | "Analyze the attack timing. When should the client be most alert?" |
| Narrative Themes | "Analyze the narrative clusters. Identify the most dangerous theme." |
| Controversy Analysis | "Analyze the wedge issues. What's driving the stalemate?" |
| Hall of Fame | "Analyze these top-rated notes. Create a 'Style Guide' for effective counter-misinformation." |

### How It Works
1. **Click the button** — The component loads Llama-3.2-3B into GPU memory (first load takes ~10-20 seconds).
2. **Context injection** — The visualization data (JSON) is passed as context to the LLM.
3. **Streaming output** — The AI generates a 3-bullet "Strategic Briefing" in real-time.
4. **Zero data leakage** — All inference runs locally; no data is sent to any server.

### Output Format
```
📋 STRATEGIC BRIEFING

• [Key Insight 1]
• [Key Insight 2]  
• [Strategic Recommendation]
```

### Technical Details
- **Model:** Llama-3.2-3B-Instruct (quantized)
- **Engine:** WebLLM (MLC-AI)
- **Compute:** WebGPU (browser GPU acceleration)
- **Prompt:** 3-layer system (base analyst role + section context + task instruction)

### Limitations
- Requires WebGPU-compatible browser (Chrome 113+, Edge 113+)
- First load is slow (~10-20s model download/compile)
- Less capable than cloud models (GPT-4, Grok, Claude)
- Best for quick summaries, not deep forensic analysis

---

## Data Sources

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `notes` | All Community Notes | `noteId`, `summary`, `tweetId`, `classification`, `createdAtMillis` |
| `status_history` | Verdict timeline | `noteId`, `currentStatus`, `timestampMillisOfFirstNonNMRStatus` |
| `ratings` | User votes | `noteId`, `helpfulnessLevel`, `argumentativeOrBiased`, etc. |

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Streamlit | Rapid "War Room" UI |
| Database | DuckDB | Fast columnar OLAP on 2.2M rows |
| ML | scikit-learn | TF-IDF + KMeans clustering |
| NLP | TextBlob | Sentiment analysis |
| Charts | Altair | Interactive visualizations |
| Cloud AI | xAI, OpenAI, Anthropic | Deep forensic reasoning |
| Local AI | WebLLM | Zero-leakage inference via WebGPU |
