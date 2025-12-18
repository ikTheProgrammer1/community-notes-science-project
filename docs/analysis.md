# Extracting Patterns from Community Notes Data

This guide outlines how to analyze the official X (Twitter) Community Notes dataset to extract insights and patterns.

## 1. Data Overview

You have three key files:

*   **`notes-00000.tsv`**: The core content.
    *   `noteId`: Unique ID.
    *   `tweetId`: The tweet being noted.
    *   `summary`: The text of the note.
    *   `classification`: The user's initial verdict (e.g., "Misinformed").
*   **`noteStatusHistory-00000.tsv`**: The "Verdict".
    *   `noteId`: Links to the note.
    *   `currentStatus`: **CRITICAL**. Values are `HELPFUL`, `NOT_HELPFUL`, or `NEEDS_MORE_RATINGS`.
    *   `timestamp`: When the status was locked in.
*   **`ratings-00005.tsv`**: Granular voting data.
    *   Individual user votes on notes. Useful for deep dives but less critical for high-level pattern extraction.

## 2. Strategy: Finding the "Gold Standard"

The most valuable insight comes from comparing **Helpful** notes vs. **Not Helpful** notes.

### The "Helpfulness" Filter
We only care about notes that reached a consensus.
1.  **Join** `notes` with `noteStatusHistory` on `noteId`.
2.  **Filter** for `currentStatus == 'HELPFUL'`.

## 3. Pattern Extraction Recipes

Here are specific patterns to look for using Python (Pandas):

### A. Linguistic Patterns (What do they say?)
*   **Neutrality**: Do helpful notes use more neutral language? (Avoid "liar", "fake", "idiot").
*   **Length**: Is there a "Goldilocks" length? (Too short = vague, Too long = boring).
*   **Keywords**: Common words in helpful notes (e.g., "context", "official", "report", "data").

### B. Structural Patterns (How do they say it?)
*   **Citations**: Check for the presence of URLs. Helpful notes almost *always* cite sources.
*   **Directness**: Do they start with "No," or "Yes," or do they jump straight to the fact?

## 4. Python Implementation

Create a script or notebook with the following code to perform this analysis.

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Load Data
print("Loading data...")
notes = pd.read_csv('notes-00000.tsv', sep='\t')
status = pd.read_csv('noteStatusHistory-00000.tsv', sep='\t')

# 2. Merge Data
# We want the latest status for each note
latest_status = status.sort_values('createdAtMillis').groupby('noteId').tail(1)
df = pd.merge(notes, latest_status[['noteId', 'currentStatus']], on='noteId', how='inner')

print(f"Total Notes: {len(df)}")
print(df['currentStatus'].value_counts())

# 3. Feature Engineering
df['note_length'] = df['summary'].str.len()
df['has_url'] = df['summary'].str.contains('http')
df['is_helpful'] = df['currentStatus'] == 'HELPFUL'

# 4. Pattern Analysis

# Pattern 1: Citation Impact
print("\n--- Impact of Citations ---")
citation_stats = df.groupby('has_url')['is_helpful'].mean()
print(citation_stats)
# Visualization
sns.barplot(x=citation_stats.index, y=citation_stats.values)
plt.title("Probability of Being 'Helpful' vs. Having a URL")
plt.show()

# Pattern 2: Length Analysis
print("\n--- Impact of Length ---")
plt.figure(figsize=(10,6))
sns.histplot(data=df, x='note_length', hue='currentStatus', kde=True, bins=50)
plt.title("Note Length Distribution by Status")
plt.show()

# Pattern 3: Keyword Extraction (Simple)
from collections import Counter
import re

def get_common_words(text_series):
    all_text = ' '.join(text_series.dropna()).lower()
    words = re.findall(r'\w+', all_text)
    # Filter common stop words (simplified list)
    stop_words = set(['the', 'a', 'to', 'of', 'in', 'is', 'and', 'that', 'for', 'on', 'it', 'this'])
    filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
    return Counter(filtered_words).most_common(10)

print("\nTop Words in HELPFUL Notes:")
print(get_common_words(df[df['currentStatus'] == 'HELPFUL']['summary']))

print("\nTop Words in NOT HELPFUL Notes:")
print(get_common_words(df[df['currentStatus'] == 'NOT_HELPFUL']['summary']))
```

## 6. Bonus: Building a "Source Trust Score" Table (DuckDB Powered)

This script extracts every URL from the notes, normalizes them to domains, and calculates a "Trust Score". We use **DuckDB** for high-performance data loading.

```python
import duckdb
import pandas as pd
from urllib.parse import urlparse
import os

# ... (See generate_trust_scores.py for full code)
```

# 2. Extract Domains
def extract_domains(text):
    if not isinstance(text, str): return []
    words = text.split()
    domains = []
    for word in words:
        # Simple extraction for http/https links
        if word.startswith('http'):
            try:
                # Clean punctuation from end of URL
                clean_url = word.rstrip('.,!?")')
                domain = urlparse(clean_url).netloc
                # Remove 'www.' for cleaner aggregation
                if domain.startswith('www.'):
                    domain = domain[4:]
                if domain:
                    domains.append(domain)
            except:
                pass
    return domains

print("Extracting domains...")
# Explode the dataframe so each domain gets its own row
df['domains'] = df['summary'].apply(extract_domains)
df_exploded = df.explode('domains')
# Filter out rows with no domains
df_domains = df_exploded.dropna(subset=['domains'])

# 3. Calculate Stats
print("Calculating Trust Scores...")
domain_stats = df_domains.groupby('domains').agg(
    times_cited=('noteId', 'count'),
    helpful_count=('currentStatus', lambda x: (x == 'HELPFUL').sum())
).reset_index()

# 4. Compute Metrics
# Filter for domains with meaningful volume (e.g., cited at least 5 times)
min_citations = 5
domain_stats = domain_stats[domain_stats['times_cited'] >= min_citations].copy()

domain_stats['helpful_rate'] = domain_stats['helpful_count'] / domain_stats['times_cited']

# Simple Trust Score: Weighted by volume confidence?
# For now, let's just use the helpful_rate as the base score.
# You could add a Wilson Score Interval here for better ranking of low-volume domains.
domain_stats['source_trust_score'] = domain_stats['helpful_rate'].round(2)

# Sort by Trust Score (descending) and then Volume
top_domains = domain_stats.sort_values(by=['source_trust_score', 'times_cited'], ascending=[False, False])

# 5. Output
print(top_domains.head(20))
top_domains.to_csv('source_trust_scores.csv', index=False)
print("Saved to source_trust_scores.csv")
```

### How to use this table
1.  **Whitelist**: High-score domains (e.g., > 0.90) are "Gold Standards". If your AI finds a claim supported by these, it's likely true.
2.  **Blacklist**: Low-score domains (e.g., < 0.10) are "Red Flags". If a tweet cites these, it's likely misinformation.

