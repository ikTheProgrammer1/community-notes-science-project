import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("Generating Underperforming Sources Visualization...")
    
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

    # 2. Use Pre-calculated Metrics
    if 'cn_underperformer_score' not in df.columns:
        print("Error: cn_underperformer_score not found in CSV. Please regenerate bridge_intelligence.csv.")
        return

    # Global baseline from CSV if available, else calculate
    if 'cn_baseline_helpful_rate' in df.columns:
        global_helpful = df['cn_baseline_helpful_rate'].iloc[0]
    else:
        global_helpful = (df['helpful_rate'] * df['times_cited']).sum() / df['times_cited'].sum()

    # 3. Prepare Data for Plotting
    # Filter for underperformers (Score > 1.0 is the default threshold we set, but let's just take top 20)
    top_underperformers = df.sort_values('cn_underperformer_score', ascending=False).head(20)

    # Set style
    sns.set_theme(style="whitegrid")
    
    plt.figure(figsize=(12, 10))
    
    # Create bar chart
    ax = sns.barplot(
        data=top_underperformers,
        x='cn_underperformer_score',
        y='domains',
        palette='viridis_r'
    )
    
    plt.title('Top 20 Underperforming Sources in Community Notes Dataset', fontsize=16, fontweight='bold')
    plt.xlabel('Underperformer Score (Trust Deficit × Volume × Engagement)', fontsize=12)
    plt.ylabel('')
    
    # Add annotations
    for i, (idx, row) in enumerate(top_underperformers.iterrows()):
        # Label with helpful rate vs baseline
        label = f"Helpful Rate: {row['helpful_rate']:.0%} (vs {global_helpful:.0%})"
        ax.text(
            row['cn_underperformer_score'] + 0.05, 
            i, 
            label, 
            va='center', 
            fontsize=10,
            color='black'
        )

    plt.tight_layout()
    output_file = '../output/underperforming_sources_chart.png'
    plt.savefig(output_file)
    print(f"✅ Visualization saved to {output_file}")

if __name__ == "__main__":
    main()
