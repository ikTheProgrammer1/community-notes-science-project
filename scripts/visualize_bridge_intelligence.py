import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("Generating Bridge Intelligence Visualizations...")
    
    # Load data
    try:
        df = pd.read_csv('../data/bridge_intelligence.csv')
    except FileNotFoundError:
        print("Error: bridge_intelligence.csv not found.")
        return

    # Set style
    sns.set_theme(style="whitegrid")
    
    # Create figure with 3 subplots
    fig = plt.figure(figsize=(15, 18))
    gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 1])
    
    # Plot 1: Bridge Score vs. Volume (Scatter)
    # Highlight top sources
    ax1 = fig.add_subplot(gs[0])
    
    # Filter for readability
    plot_df = df[df['times_cited'] > 10].copy()
    
    sns.scatterplot(
        data=plot_df,
        x='times_cited',
        y='bridge_score',
        hue='top_topic',
        size='avg_engagement',
        sizes=(20, 500),
        alpha=0.7,
        palette='deep',
        ax=ax1
    )
    
    # Annotate top 5 Bridge Sources
    top_bridge = plot_df.sort_values('bridge_score', ascending=False).head(5)
    for _, row in top_bridge.iterrows():
        ax1.text(
            row['times_cited'], 
            row['bridge_score'], 
            row['domains'], 
            fontsize=10, 
            fontweight='bold',
            ha='left',
            va='bottom'
        )

    ax1.set_xscale('log')
    ax1.set_title('Bridge Score vs. Volume (Log Scale)', fontsize=16)
    ax1.set_xlabel('Total Citations (Log Scale)', fontsize=12)
    ax1.set_ylabel('Bridge Score', fontsize=12)
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)
    
    # Plot 2: Top Bridge Sources by Topic
    ax2 = fig.add_subplot(gs[1])
    
    # Get top 3 from each topic
    top_by_topic = plot_df.groupby('top_topic').apply(lambda x: x.nlargest(3, 'bridge_score')).reset_index(drop=True)
    
    sns.barplot(
        data=top_by_topic,
        x='bridge_score',
        y='domains',
        hue='top_topic',
        dodge=False,
        palette='deep',
        ax=ax2
    )
    
    ax2.set_title('Top Bridge Sources by Topic', fontsize=16)
    ax2.set_xlabel('Bridge Score', fontsize=12)
    ax2.set_ylabel('Domain', fontsize=12)
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

    # Plot 3: Battlefield Score vs. Volume (Scatter)
    ax3 = fig.add_subplot(gs[2])
    
    sns.scatterplot(
        data=plot_df,
        x='times_cited',
        y='battlefield_score',
        hue='top_topic',
        size='avg_engagement',
        sizes=(20, 500),
        alpha=0.7,
        palette='magma',
        ax=ax3
    )
    
    # Annotate top 5 Contentious Sources
    top_risky = plot_df.sort_values('battlefield_score', ascending=False).head(5)
    for _, row in top_risky.iterrows():
        ax3.text(
            row['times_cited'], 
            row['battlefield_score'], 
            row['domains'], 
            fontsize=10, 
            fontweight='bold',
            color='red',
            ha='left',
            va='bottom'
        )

    ax3.set_xscale('log')
    ax3.set_title('Battlefield Score vs. Volume (Log Scale)', fontsize=16)
    ax3.set_xlabel('Total Citations (Log Scale)', fontsize=12)
    ax3.set_ylabel('Battlefield Score', fontsize=12)
    ax3.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)

    plt.tight_layout()
    output_file = '../output/bridge_intelligence_charts.png'
    plt.savefig(output_file, bbox_inches='tight')
    print(f"✅ Visualization saved to {output_file}")

if __name__ == "__main__":
    main()
