import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("Generating visualizations...")
    
    # Load data
    try:
        df = pd.read_csv('../data/source_trust_scores.csv')
    except FileNotFoundError:
        print("Error: source_trust_scores.csv not found.")
        return

    # Set style
    sns.set_theme(style="whitegrid")
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 14))
    
    # Plot 1: Top 15 Most Trusted Sources (High Volume)
    # Filter for high volume to make it meaningful (e.g., > 50 citations)
    # If not enough data, take top overall
    high_vol = df[df['times_cited'] >= 20]
    if len(high_vol) < 10:
        high_vol = df # Fallback
        
    top_trusted = high_vol.sort_values('source_trust_score', ascending=False).head(15)
    
    sns.barplot(
        data=top_trusted,
        x='source_trust_score',
        y='domains',
        palette='viridis',
        ax=ax1
    )
    ax1.set_title('Top 15 Most Trusted Sources (Highest Helpful Rate)', fontsize=16)
    ax1.set_xlabel('Trust Score (Helpful Rate)', fontsize=12)
    ax1.set_ylabel('Domain', fontsize=12)
    ax1.set_xlim(0, 1.1)
    
    # Plot 2: Top 15 Least Trusted Sources (High Volume)
    # We want sources that are cited a lot but rarely helpful
    least_trusted = high_vol.sort_values('source_trust_score', ascending=True).head(15)
    
    sns.barplot(
        data=least_trusted,
        x='source_trust_score',
        y='domains',
        palette='magma',
        ax=ax2
    )
    ax2.set_title('Top 15 Least Trusted Sources (Lowest Helpful Rate)', fontsize=16)
    ax2.set_xlabel('Trust Score (Helpful Rate)', fontsize=12)
    ax2.set_ylabel('Domain', fontsize=12)
    ax2.set_xlim(0, 1.1)
    
    plt.tight_layout()
    output_file = '../output/trust_score_charts.png'
    plt.savefig(output_file)
    print(f"✅ Visualization saved to {output_file}")

if __name__ == "__main__":
    main()
