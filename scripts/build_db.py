
import argparse

def build(sample=False):
    print(f"Building Database... (Sample Mode: {sample})")
    print("In a real setup, this would ingest TSV files into a persistent DuckDB instance.")
    print("Currently, dashboard.py handles ephemeral in-memory ingestion.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="Use a small sample of data")
    args = parser.parse_args()
    build(sample=args.sample)
