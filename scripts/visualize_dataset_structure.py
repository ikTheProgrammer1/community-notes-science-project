import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def analyze_file(file_path, name, output_dir):
    print(f"Analyzing {name}...")
    
    # Read first 10k rows for visualization to be fast
    try:
        df = pd.read_csv(file_path, sep='\t', nrows=10000)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

    # 1. Basic Info
    info = {
        'rows_analyzed': len(df),
        'columns': list(df.columns),
        'sample': df.head(3).to_markdown(index=False)
    }

    # 2. Visualizations
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))

    if name == 'Notes':
        # Visualize Note Length Distribution
        df['length'] = df['summary'].str.len()
        sns.histplot(df['length'], bins=30, kde=True, color='skyblue', ax=ax)
        ax.set_title('Distribution of Note Lengths (Characters)', fontsize=14)
        ax.set_xlabel('Length')
    
    elif name == 'Status History':
        # Visualize Status Distribution
        status_counts = df['currentStatus'].value_counts()
        sns.barplot(x=status_counts.index, y=status_counts.values, palette='viridis', ax=ax)
        ax.set_title('Distribution of Note Statuses', fontsize=14)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45)
    
    elif name == 'Ratings':
        # Visualize Helpfulness Scores (if available) or just count of ratings per note
        # Ratings file usually has 'helpfulnessLevel' or similar? 
        # Let's check columns. Usually: noteId, raterParticipantId, helpfulnessLevel, etc.
        if 'helpfulnessLevel' in df.columns:
            sns.countplot(data=df, x='helpfulnessLevel', palette='magma', ax=ax)
            ax.set_title('Distribution of Helpfulness Ratings', fontsize=14)
        else:
            ax.text(0.5, 0.5, "No 'helpfulnessLevel' column found", ha='center')

    plt.tight_layout()
    chart_path = os.path.join(output_dir, f"{name.lower().replace(' ', '_')}_overview.png")
    plt.savefig(chart_path)
    plt.close()
    
    info['chart_path'] = chart_path
    return info

def main():
    data_dir = '../data'
    output_dir = '../output'
    docs_dir = '../docs'
    
    files = {
        'Notes': 'notes-00000.tsv',
        'Status History': 'noteStatusHistory-00000.tsv',
        'Ratings': 'ratings-00005.tsv'
    }

    report_content = "# 📂 Community Notes Dataset Overview\n\n"
    report_content += "A visual guide to understanding what's inside the TSV files.\n\n"

    for name, filename in files.items():
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            print(f"Skipping {name}: {path} not found.")
            continue
            
        info = analyze_file(path, name, output_dir)
        if info:
            report_content += f"## {name} (`{filename}`)\n\n"
            report_content += f"**Columns:** `{', '.join(info['columns'])}`\n\n"
            report_content += "### Sample Data\n"
            report_content += info['sample'] + "\n\n"
            report_content += "### Data Distribution\n"
            # Relative path for markdown
            rel_chart_path = os.path.relpath(info['chart_path'], docs_dir)
            report_content += f"![{name} Chart]({rel_chart_path})\n\n"
            report_content += "---\n\n"

    with open(os.path.join(docs_dir, 'dataset_overview.md'), 'w') as f:
        f.write(report_content)
    
    print(f"✅ Generated report at {os.path.join(docs_dir, 'dataset_overview.md')}")

if __name__ == "__main__":
    main()
