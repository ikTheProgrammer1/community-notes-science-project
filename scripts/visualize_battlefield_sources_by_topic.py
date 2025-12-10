import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    print("Generating Battlefield Sources Visualizations...")
    
    try:
        df = pd.read_csv('../data/bridge_intelligence.csv')
    except FileNotFoundError:
        print("Error: bridge_intelligence.csv not found.")
        return

    # Filter for significant volume
    df = df[df['times_cited'] > 20]

    # Get unique topics
    topics = df['top_topic'].unique()
    topics = sorted([t for t in topics if t != 'Other']) + ['Other']
    
    num_topics = len(topics)
    
    # Set style
    sns.set_theme(style="whitegrid")
    
    # Create subplots
    fig, axes = plt.subplots(num_topics, 1, figsize=(12, 4 * num_topics))
    if num_topics == 1: axes = [axes]
    
    for i, topic in enumerate(topics):
        ax = axes[i]
        
        # Get top 5 contentious sources for this topic
        topic_data = df[df['top_topic'] == topic].sort_values('battlefield_score', ascending=False).head(5)
        
        if topic_data.empty:
            ax.text(0.5, 0.5, "No data", ha='center')
            continue
            
        sns.barplot(
            data=topic_data,
            x='battlefield_score',
            y='domains',
            palette='Reds_r',
            ax=ax
        )
        
        ax.set_title(f'Top Contentious Sources in Dataset: {topic}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Battlefield Score', fontsize=10)
        ax.set_ylabel('')
        ax.set_xlim(0, 110)
        
        # Add labels with citation counts
        for j, (idx, row) in enumerate(topic_data.iterrows()):
            ax.text(
                row['battlefield_score'] + 1, 
                j, 
                f"(n={row['times_cited']})", 
                va='center', 
                fontsize=9,
                color='gray'
            )

    plt.tight_layout()
    output_file = '../output/battlefield_sources_charts.png'
    plt.savefig(output_file)
    print(f"✅ Visualization saved to {output_file}")

if __name__ == "__main__":
    main()
