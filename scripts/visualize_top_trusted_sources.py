import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("Generating Top Trusted Sources Visualization...")
    
    # Load data
    try:
        df = pd.read_csv('../data/bridge_intelligence.csv')
    except FileNotFoundError:
        print("Error: ../data/bridge_intelligence.csv not found.")
        return

    # 1. Filter for significant volume
    # To be a "Top Trusted Source", you need a decent sample size.
    min_citations = 50
    df = df[df['times_cited'] >= min_citations].copy()
    
    if df.empty:
        print("No sources found with >= 50 citations.")
        return

    # 2. Sort by Bridge Score (Helpfulness + Engagement + Volume)
    # This identifies sources that are consistently helpful and impactful.
    top_100 = df.sort_values('bridge_score', ascending=False).head(100)

    # 3. Save Top 100 to CSV
    output_csv = '../output/top_100_trusted_sources.csv'
    cols = ['domains', 'bridge_score', 'helpful_rate', 'times_cited', 'top_topic', 'avg_engagement']
    top_100[cols].to_csv(output_csv, index=False)
    print(f"✅ Saved Top 100 list to {output_csv}")

    # 4. Visualize Top 40 (for readability)
    top_40 = top_100.head(40)

    # Set style
    sns.set_theme(style="whitegrid")
    
    plt.figure(figsize=(12, 16))
    
    # Create bar chart
    ax = sns.barplot(
        data=top_40,
        x='bridge_score',
        y='domains',
        palette='viridis'
    )
    
    plt.title('Top 40 Trusted "Bridge Sources" in Community Notes', fontsize=16, fontweight='bold')
    plt.xlabel('Bridge Score (Helpfulness × Volume × Engagement)', fontsize=12)
    plt.ylabel('')
    
    # Add labels
    for i, (idx, row) in enumerate(top_40.iterrows()):
        # Label with helpful rate
        label = f"Helpful Rate: {row['helpful_rate']:.0%}"
        ax.text(
            row['bridge_score'] + 0.5, 
            i, 
            label, 
            va='center', 
            fontsize=9,
            color='black'
        )

    plt.tight_layout()
    output_chart = '../output/top_trusted_sources_chart.png'
    plt.savefig(output_chart)
    print(f"✅ Visualization saved to {output_chart}")

if __name__ == "__main__":
    main()
