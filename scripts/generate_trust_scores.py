import duckdb
import pandas as pd
from urllib.parse import urlparse
import os

def main():
    print("Starting Source Trust Score Generation (DuckDB Powered)...")

    # Define file paths
    notes_path = '../data/notes-00000.tsv'
    status_path = '../data/noteStatusHistory-00000.tsv'

    # Check if files exist
    if not os.path.exists(notes_path) or not os.path.exists(status_path):
        print(f"Error: Data files not found.")
        return

    con = duckdb.connect(database=':memory:')

    # 1. Load Data
    print("Loading Data via DuckDB...")
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
    con.execute("""
        CREATE TABLE latest_status AS
        SELECT noteId, currentStatus
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY noteId ORDER BY createdAtMillis DESC) as rn
            FROM status_history
        ) WHERE rn = 1;
    """)
    
    query = """
        SELECT n.noteId, n.summary, s.currentStatus
        FROM notes n
        JOIN latest_status s ON n.noteId = s.noteId
    """
    
    df = con.execute(query).df()
    print(f"Total Notes with Status: {len(df)}")

    # 3. Extract Domains
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

    print("Extracting domains...")
    df['domains'] = df['summary'].apply(extract_domains)
    
    # Explode
    df_exploded = df.explode('domains')
    df_domains = df_exploded.dropna(subset=['domains'])

    # 4. Calculate Stats
    print("Calculating Trust Scores...")
    domain_stats = df_domains.groupby('domains').agg(
        times_cited=('noteId', 'count'),
        helpful_count=('currentStatus', lambda x: (x == 'CURRENTLY_RATED_HELPFUL').sum())
    ).reset_index()

    # 5. Compute Metrics
    min_citations = 5
    domain_stats = domain_stats[domain_stats['times_cited'] >= min_citations].copy()
    
    domain_stats['helpful_rate'] = domain_stats['helpful_count'] / domain_stats['times_cited']
    domain_stats['source_trust_score'] = domain_stats['helpful_rate'].round(2)

    # Sort
    top_domains = domain_stats.sort_values(by=['source_trust_score', 'times_cited'], ascending=[False, False])

    # 6. Output
    output_file = '../data/source_trust_scores.csv'
    top_domains.to_csv(output_file, index=False)
    
    print(f"\n✅ Success! Generated {output_file}")
    print("\nTop 20 Trusted Sources:")
    print(top_domains.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
