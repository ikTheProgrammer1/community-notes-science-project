
import duckdb
import os
import argparse
import glob

# Configuration
DATA_DIR = "data"
ARTIFACT_DIR = "artifacts"

def build_db(sample=False):
    """
    Ingests TSV files from data/ into a persistent DuckDB artifact.
    """
    db_name = "community_notes_sample.duckdb" if sample else "community_notes_full.duckdb"
    db_path = os.path.join(ARTIFACT_DIR, db_name)
    
    print(f"🔨 Building database: {db_path}")
    print(f"📂 Mode: {'SAMPLE (Small Subset)' if sample else 'FULL DATASET (Production)'}")
    
    # Ensure artifact directory exists
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    
    # Remove existing DB to ensure clean build (Idempotency)
    if os.path.exists(db_path):
        os.remove(db_path)
        print("🗑️  Removed existing database artifact.")

    try:
        con = duckdb.connect(database=db_path)
        
        # 1. Notes
        notes_files = glob.glob(os.path.join(DATA_DIR, "notes-*.tsv"))
        if notes_files:
            print(f"📝 Ingesting Notes ({len(notes_files)} files)...")
            limit_clause = "LIMIT 100000" if sample else ""
            con.execute(f"""
                CREATE TABLE notes AS 
                SELECT * FROM read_csv_auto('{DATA_DIR}/notes-*.tsv', sep='\t')
                {limit_clause}
            """)
            print(f"   ✅ loaded {con.execute('SELECT COUNT(*) FROM notes').fetchone()[0]} notes.")
        else:
            print("⚠️  No notes-*.tsv files found.")

        # 2. Status History
        status_files = glob.glob(os.path.join(DATA_DIR, "noteStatusHistory-*.tsv"))
        if status_files:
            print(f"⏱️  Ingesting Status History ({len(status_files)} files)...")
            
            if sample:
                # INTEGRITY FIX: Only ingest status for notes that exist in the random sample
                print("   🔗 Enforcing referential integrity for sample...")
                con.execute(f"""
                    CREATE TABLE status_history AS 
                    SELECT * FROM read_csv_auto('{DATA_DIR}/noteStatusHistory-*.tsv', sep='\t')
                    WHERE noteId IN (SELECT noteId FROM notes)
                """)
            else:
                con.execute(f"""
                    CREATE TABLE status_history AS 
                    SELECT * FROM read_csv_auto('{DATA_DIR}/noteStatusHistory-*.tsv', sep='\t')
                """)
                
            print(f"   ✅ loaded {con.execute('SELECT COUNT(*) FROM status_history').fetchone()[0]} status records.")
        else:
            print("⚠️  No noteStatusHistory-*.tsv files found.")

        # 3. Ratings
        ratings_files = glob.glob(os.path.join(DATA_DIR, "ratings-*.tsv"))
        if ratings_files:
            print(f"⭐ Ingesting Ratings ({len(ratings_files)} files)...")
            
            if sample:
                # INTEGRITY FIX: Only ingest ratings for notes that exist
                con.execute(f"""
                    CREATE TABLE ratings AS 
                    SELECT * FROM read_csv_auto('{DATA_DIR}/ratings-*.tsv', sep='\t', union_by_name=True)
                    WHERE noteId IN (SELECT noteId FROM notes)
                    LIMIT 5000
                """)
            else:
                 con.execute(f"""
                    CREATE TABLE ratings AS 
                    SELECT * FROM read_csv_auto('{DATA_DIR}/ratings-*.tsv', sep='\t', union_by_name=True)
                """)
            print(f"   ✅ loaded {con.execute('SELECT COUNT(*) FROM ratings').fetchone()[0]} ratings.")
        else:
            print("⚠️  No ratings-*.tsv files found.")
            
        con.close()
        print(f"🎉 Success! Database built at: {db_path}")
        
    except Exception as e:
        print(f"❌ Error building database: {e}")
        if os.path.exists(db_path):
            os.remove(db_path) # Cleanup partial build
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Community Notes DuckDB Artifact")
    parser.add_argument("--sample", action="store_true", help="Build a small sample DB for testing")
    args = parser.parse_args()
    
    build_db(sample=args.sample)
