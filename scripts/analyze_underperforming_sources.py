import pandas as pd
import numpy as np

def main():
    print("Analyzing Underperforming Sources in Community Notes Dataset...")
    
    # Load data
    try:
        df = pd.read_csv('../data/bridge_intelligence.csv')
    except FileNotFoundError:
        print("Error: ../data/bridge_intelligence.csv not found.")
        return

    # 1. Filter out low-volume noise
    min_citations = 50
    df = df[df['times_cited'] >= min_citations].copy()
    
    if df.empty:
        print("No sources found with >= 50 citations.")
        return

    # 2. Compute global helpfulness baseline
    # We sum up counts to get the true weighted average across the filtered set
    # Note: helpful_count might need to be reconstructed if not in CSV, 
    # but bridge_intelligence.csv usually has: domains, times_cited, helpful_count, helpful_rate...
    # Let's check if helpful_count is in there. If not, we can derive it or use helpful_rate * times_cited.
    
    if 'helpful_count' not in df.columns:
        df['helpful_count'] = df['helpful_rate'] * df['times_cited']

    global_helpful = df['helpful_count'].sum() / df['times_cited'].sum()
    print(f"Global Helpfulness Baseline (for sources with >={min_citations} citations): {global_helpful:.3f}")

    # 3. Compute Trust Deficit
    df['trust_deficit'] = global_helpful - df['helpful_rate']
    # Clip to 0 (no deficit if better than average)
    df['trust_deficit'] = df['trust_deficit'].clip(lower=0)

    # 4. Compute Underperformer Score
    # Weight by deficit, log(volume), and log(engagement)
    df['underperformer_score'] = (
        df['trust_deficit'] *
        np.log1p(df['times_cited']) *
        np.log1p(df['avg_engagement'])
    )

    # 5. Sort and Display
    top_underperformers = df.sort_values('underperformer_score', ascending=False).head(20)

    print("\n📉 Top 20 Underperforming Sources in this Dataset:")
    print("(Domains that are cited frequently but have a lower Helpful rate than average)")
    print("-" * 80)
    
    # Select columns to display
    cols = ['domains', 'underperformer_score', 'helpful_rate', 'times_cited', 'avg_engagement']
    print(top_underperformers[cols].to_string(index=False))
    
    print("-" * 80)
    print("\nInterpretation:")
    for _, row in top_underperformers.head(3).iterrows():
        print(f"* According to this CN-based metric, {row['domains']} is an underperforming source (Score: {row['underperformer_score']:.1f}).")
        print(f"  Notes citing it have a helpful rate of {row['helpful_rate']:.2f}, which is below the baseline of {global_helpful:.3f}.")

if __name__ == "__main__":
    main()
