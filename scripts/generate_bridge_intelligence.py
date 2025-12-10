import duckdb
import pandas as pd
import numpy as np
from urllib.parse import urlparse
import os

def main():
    print("Starting Bridge Source Intelligence Generation (DuckDB Powered)...")

    # Files
    notes_path = '../data/notes-00000.tsv'
    status_path = '../data/noteStatusHistory-00000.tsv'
    ratings_path = '../data/ratings-00005.tsv'

    # Check files
    for p in [notes_path, status_path, ratings_path]:
        if not os.path.exists(p):
            print(f"Error: {p} not found.")
            return

    # Initialize DuckDB connection
    con = duckdb.connect(database=':memory:')

    # 1. Load Data & Calculate Engagement (SQL is much faster for this)
    print("Loading Data & Calculating Engagement via DuckDB...")
    
    # We create a view for ratings to avoid loading everything into memory if possible, 
    # but DuckDB handles CSV reading very efficiently.
    con.execute(f"""
        CREATE TABLE ratings AS SELECT noteId FROM read_csv_auto('{ratings_path}', sep='\\t');
    """)
    
    con.execute("""
        CREATE TABLE note_engagement AS 
        SELECT noteId, COUNT(*) as total_ratings 
        FROM ratings 
        GROUP BY noteId;
    """)
    
    # Load Notes and Status
    con.execute(f"""
        CREATE TABLE notes AS SELECT noteId, summary FROM read_csv_auto('{notes_path}', sep='\\t');
    """)
    
    con.execute(f"""
        CREATE TABLE status_history AS 
        SELECT noteId, currentStatus, createdAtMillis 
        FROM read_csv_auto('{status_path}', sep='\\t');
    """)

    # 2. Merge Data
    print("Merging Data...")
    
    # Get latest status
    con.execute("""
        CREATE TABLE latest_status AS
        SELECT noteId, currentStatus
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY noteId ORDER BY createdAtMillis DESC) as rn
            FROM status_history
        ) WHERE rn = 1;
    """)

    # Join everything
    # We bring it back to Pandas here because the domain extraction and topic classification 
    # are complex text operations that might be easier in Python, 
    # OR we can try to do some of it in SQL. 
    # Let's pull the joined data to Pandas for the text processing part.
    
    query = """
        SELECT n.noteId, n.summary, s.currentStatus, COALESCE(e.total_ratings, 0) as total_ratings
        FROM notes n
        JOIN latest_status s ON n.noteId = s.noteId
        LEFT JOIN note_engagement e ON n.noteId = e.noteId
    """
    
    df = con.execute(query).df()
    print(f"Loaded {len(df)} notes with status and engagement.")

    # 3. Topic Classification (Python)
    print("Classifying Topics...")
    topics = {
        'Politics': ['election', 'vote', 'democrat', 'republican', 'biden', 'trump', 'policy', 'government', 'senate', 'congress'],
        'Health': ['covid', 'vaccine', 'virus', 'doctor', 'study', 'health', 'medicine', 'pfizer', 'moderna', 'cdc', 'who'],
        'Conflict': ['war', 'israel', 'gaza', 'ukraine', 'russia', 'military', 'attack', 'hamas', 'idf', 'putin'],
        'Economy': ['money', 'tax', 'inflation', 'market', 'crypto', 'bank', 'economy', 'stock', 'price'],
        'Tech': ['ai', 'crypto', 'internet', 'algorithm', 'data', 'google', 'apple', 'microsoft', 'facebook', 'twitter', 'x.com']
    }

    def get_topic(text):
        if not isinstance(text, str): return 'Other'
        text = text.lower()
        for topic, keywords in topics.items():
            if any(k in text for k in keywords):
                return topic
        return 'Other'

    df['topic'] = df['summary'].apply(get_topic)

    # 4. Extract Domains (Python)
    print("Extracting Domains...")
    def extract_domains(text):
        if not isinstance(text, str): return []
        words = text.split()
        domains = []
        for word in words:
            if word.startswith('http'):
                try:
                    clean_url = word.rstrip('.,!?")')
                    domain = urlparse(clean_url).netloc
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    if domain:
                        domains.append(domain)
                except:
                    pass
        return domains

    df['domains'] = df['summary'].apply(extract_domains)
    df_exploded = df.explode('domains').dropna(subset=['domains'])

    # 5. Aggregate Stats (Pandas is fine for this aggregated size)
    print("Aggregating Domain Stats...")
    
    domain_stats = df_exploded.groupby('domains').agg(
        times_cited=('noteId', 'count'),
        helpful_count=('currentStatus', lambda x: (x == 'CURRENTLY_RATED_HELPFUL').sum()),
        avg_engagement=('total_ratings', 'mean'),
        top_topic=('topic', lambda x: x.mode()[0] if not x.mode().empty else 'Other')
    ).reset_index()

    # 6. Calculate Scores
    print("Computing Bridge & Risky Scores...")
    min_citations = 5
    domain_stats = domain_stats[domain_stats['times_cited'] >= min_citations].copy()
    
    domain_stats['helpful_rate'] = domain_stats['helpful_count'] / domain_stats['times_cited']
    
    # Bridge Score
    domain_stats['bridge_score'] = (
        domain_stats['helpful_rate'] * 
        np.log1p(domain_stats['times_cited']) * 
        np.log1p(domain_stats['avg_engagement'])
    )
    
    # Battlefield Score (formerly Risky Score)
    # "How often this domain appears in big, high-engagement, mixed-outcome fights."
    domain_stats['battlefield_score'] = (
        (1 - domain_stats['helpful_rate']) * 
        np.log1p(domain_stats['times_cited']) * 
        np.log1p(domain_stats['avg_engagement'])
    )

    # --- Underperformance Metrics ---
    # 1. Global Helpfulness Baseline
    global_helpful = domain_stats['helpful_count'].sum() / domain_stats['times_cited'].sum()
    domain_stats['cn_baseline_helpful_rate'] = round(global_helpful, 3)

    # 2. Trust Deficit
    domain_stats['trust_deficit'] = global_helpful - domain_stats['helpful_rate']
    domain_stats['trust_deficit'] = domain_stats['trust_deficit'].clip(lower=0)

    # 3. Underperformer Score
    domain_stats['cn_underperformer_score'] = (
        domain_stats['trust_deficit'] *
        np.log1p(domain_stats['times_cited']) *
        np.log1p(domain_stats['avg_engagement'])
    )

    # 4. Label as Underperformer (Threshold: Score > 1.0 and Volume > 50)
    # This is an arbitrary threshold based on our analysis, can be tuned.
    domain_stats['cn_underperformer'] = (domain_stats['cn_underperformer_score'] > 1.0) & (domain_stats['times_cited'] >= 50)

    # 5. Aliases
    domain_stats['cn_helpful_rate'] = domain_stats['helpful_rate']

    # Normalize Scores (0-100)
    if not domain_stats.empty:
        domain_stats['bridge_score'] = (domain_stats['bridge_score'] / domain_stats['bridge_score'].max() * 100).round(1)
        domain_stats['battlefield_score'] = (domain_stats['battlefield_score'] / domain_stats['battlefield_score'].max() * 100).round(1)
        # We don't necessarily normalize underperformer score to 100 as it's a specific derived metric, 
        # but let's keep it raw for now or normalize if requested. User didn't ask to normalize it.
        
    domain_stats['helpful_rate'] = domain_stats['helpful_rate'].round(2)
    domain_stats['avg_engagement'] = domain_stats['avg_engagement'].round(1)
    domain_stats['cn_underperformer_score'] = domain_stats['cn_underperformer_score'].round(2)

    # 7. Output
    output_file = '../data/bridge_intelligence.csv'
    domain_stats.sort_values('bridge_score', ascending=False).to_csv(output_file, index=False)
    
    print(f"\n✅ Generated {output_file}")
    print("\n🏆 Top 10 Bridge Sources in this Dataset (High Helpfulness + Engagement):")
    print("These sources often appear in notes that raters find helpful.")
    print(domain_stats.sort_values('bridge_score', ascending=False).head(10)[['domains', 'bridge_score', 'helpful_rate', 'top_topic', 'times_cited']].to_string(index=False))
    
    print("\n⚔️ Top 10 Contentious Sources in this Dataset (High Battlefield Score):")
    print("These sources appear in many high-engagement notes with mixed outcomes.")
    print(domain_stats.sort_values('battlefield_score', ascending=False).head(10)[['domains', 'battlefield_score', 'helpful_rate', 'top_topic', 'times_cited']].to_string(index=False))

if __name__ == "__main__":
    main()
