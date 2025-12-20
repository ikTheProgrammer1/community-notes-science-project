import duckdb
import os

# Mock the artifact path (assuming it exists locally for testing)
DB_PATH = "artifacts/community_notes.duckdb"

if not os.path.exists(DB_PATH):
    print(f"Artifact not found at {DB_PATH}, skipping reproduction.")
    exit(0)

con = duckdb.connect(DB_PATH, read_only=True)

try:
    print("Attempting: SELECT count(*) FROM 'notes'")
    con.execute("SELECT count(*) FROM 'notes'").fetchall()
    print("Success (Unexpected)")
except Exception as e:
    print(f"Failed as expected: {e}")

try:
    print("\n--- Debugging Filters ---")
    
    # 1. Total matches for keyword
    query_total = "SELECT count(*) FROM notes WHERE summary ILIKE '%elon musk%'"
    count_total = con.execute(query_total).fetchone()[0]
    print(f"Total 'elon musk' matches: {count_total}")

    if count_total > 0:
        # 2. Check statuses for these matches
        query_statuses = """
            SELECT s.currentStatus, count(*)
            FROM notes n
            JOIN status_history s ON n.noteId = s.noteId
            WHERE n.summary ILIKE '%elon musk%'
            GROUP BY s.currentStatus
        """
        print("Statuses for matches:")
        print(con.execute(query_statuses).df())

        # 3. Check classifications for these matches
        query_class = """
            SELECT n.classification, count(*)
            FROM notes n
            WHERE n.summary ILIKE '%elon musk%'
            GROUP BY n.classification
        """
        print("Classifications for matches:")
        print(con.execute(query_class).df())

        # 4. Deep Dive on JOIN failure
        print("\n--- JOIN Investigation ---")
        status_count = con.execute("SELECT count(*) FROM status_history").fetchone()[0]
        print(f"Total rows in status_history: {status_count}")
        
        # Get a noteId that matched
        sample_note_id = con.execute("SELECT noteId FROM notes WHERE summary ILIKE '%elon musk%' LIMIT 1").fetchone()[0]
        print(f"Sample Note ID (matching 'elon musk'): {sample_note_id}")
        
        # Check if it exists in status
        in_status = con.execute(f"SELECT count(*) FROM status_history WHERE noteId = {sample_note_id}").fetchone()[0]
        print(f"Does Note {sample_note_id} exist in status_history? {'YES' if in_status > 0 else 'NO'}")

except Exception as e:
    print(f"Filter debug failed: {e}")
