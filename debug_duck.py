import duckdb
import pandas as pd

NOTES_DB_PATH = "data/notes-00000.tsv"
STATUS_DB_PATH = "data/noteStatusHistory-00000.tsv"

query = f"""
SELECT 
    n.summary,
    n.trustworthySources,
    n.classification
FROM '{NOTES_DB_PATH}' AS n
WHERE n.summary ILIKE '%Vice President%'
  AND n.summary ILIKE '%South Africa%'
LIMIT 1
"""

try:
    con = duckdb.connect(database=':memory:')
    df = con.execute(query).df()
    print(df.to_string())
    
    # Also show a few raw summaries to ensure we aren't crazy
    raw_q = f"SELECT summary FROM '{NOTES_DB_PATH}' WHERE summary ILIKE '%Tesla%' LIMIT 3"
    print("\nSample Summaries:")
    print(con.execute(raw_q).df())

except Exception as e:
    print(e)
