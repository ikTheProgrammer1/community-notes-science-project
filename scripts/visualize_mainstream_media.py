import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("Generating Mainstream Media Performance Visualization...")
    
    # Load data
    try:
        df = pd.read_csv('../data/bridge_intelligence.csv')
    except FileNotFoundError:
        print("Error: ../data/bridge_intelligence.csv not found.")
        return

    # Define MSM Domains
    msm_domains = [
        'cnn.com', 'edition.cnn.com',
        'foxnews.com',
        'msnbc.com',
        'nytimes.com',
        'washingtonpost.com',
        'bbc.com', 'bbc.co.uk',
        'reuters.com',
        'apnews.com',
        'nbcnews.com',
        'cbsnews.com',
        'abcnews.go.com',
        'theguardian.com',
        'usatoday.com',
        'wsj.com',
        'bloomberg.com',
        'npr.org',
        'nypost.com',
        'breitbart.com',
        'dailymail.co.uk'
    ]

    # Filter for MSM
    # We check if the domain is in our list
    msm_df = df[df['domains'].isin(msm_domains)].copy()
    
    if msm_df.empty:
        print("No MSM domains found in dataset.")
        return

    # Sort by Helpful Rate
    msm_df = msm_df.sort_values('helpful_rate', ascending=False)

    # Print Summary
    print("\n📰 Mainstream Media Performance in Community Notes:")
    print(msm_df[['domains', 'helpful_rate', 'bridge_score', 'battlefield_score', 'times_cited']].to_string(index=False))

    # Visualization
    sns.set_theme(style="whitegrid")
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 14))
    
    # Plot 1: Helpful Rate
    sns.barplot(
        data=msm_df,
        x='helpful_rate',
        y='domains',
        palette='coolwarm',
        ax=ax1
    )
    
    # Add baseline line
    if 'cn_baseline_helpful_rate' in df.columns:
        baseline = df['cn_baseline_helpful_rate'].iloc[0]
        ax1.axvline(baseline, color='red', linestyle='--', label=f'Avg Baseline ({baseline:.1%})')
        ax1.legend()

    ax1.set_title('Helpful Rate of Mainstream Media Sources', fontsize=16, fontweight='bold')
    ax1.set_xlabel('Helpful Rate (Percent of citations in Helpful notes)', fontsize=12)
    ax1.set_ylabel('')
    ax1.set_xlim(0, 0.4) # Adjust as needed

    # Add labels
    for i, (idx, row) in enumerate(msm_df.iterrows()):
        ax1.text(
            row['helpful_rate'] + 0.005, 
            i, 
            f"{row['helpful_rate']:.1%}", 
            va='center', 
            fontsize=10,
            color='black'
        )

    # Plot 2: Battlefield Score (Contentiousness)
    # Sort by Battlefield Score for this plot
    msm_battlefield = msm_df.sort_values('battlefield_score', ascending=False)
    
    sns.barplot(
        data=msm_battlefield,
        x='battlefield_score',
        y='domains',
        palette='Reds_r',
        ax=ax2
    )
    
    ax2.set_title('Contentiousness (Battlefield Score) of Mainstream Media', fontsize=16, fontweight='bold')
    ax2.set_xlabel('Battlefield Score (High = Often cited in contentious/mixed notes)', fontsize=12)
    ax2.set_ylabel('')
    
    # Add labels
    for i, (idx, row) in enumerate(msm_battlefield.iterrows()):
        ax2.text(
            row['battlefield_score'] + 1, 
            i, 
            f"{row['battlefield_score']:.1f}", 
            va='center', 
            fontsize=10,
            color='black'
        )

    plt.tight_layout()
    output_file = '../output/mainstream_media_chart.png'
    plt.savefig(output_file)
    print(f"\n✅ Visualization saved to {output_file}")

if __name__ == "__main__":
    main()
