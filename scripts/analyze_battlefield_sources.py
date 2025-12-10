import pandas as pd

def main():
    print("Analyzing Contentious Sources by Topic (Battlefield Score)...")
    
    try:
        df = pd.read_csv('../data/bridge_intelligence.csv')
    except FileNotFoundError:
        print("Error: bridge_intelligence.csv not found.")
        return

    # Get unique topics
    topics = df['top_topic'].unique()
    
    for topic in topics:
        print(f"\n--- {topic} ---")
        # Filter by topic and sort by Battlefield Score
        topic_df = df[df['top_topic'] == topic].sort_values('battlefield_score', ascending=False)
        
        # Show top 5, but only if they have significant volume (e.g. > 20 citations)
        battlefield_sources = topic_df[topic_df['times_cited'] > 20].head(5)
        
        if battlefield_sources.empty:
            print("No high-volume contentious sources found.")
        else:
            print(battlefield_sources[['domains', 'battlefield_score', 'helpful_rate', 'times_cited']].to_string(index=False))

if __name__ == "__main__":
    main()
