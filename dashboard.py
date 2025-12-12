import streamlit as st
import pandas as pd
import duckdb
import os
import json
from urllib.parse import urlparse

# ... (Configuration and CSS remain similar, updating Title)
st.set_page_config(
    page_title="VIP Intelligence Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ... (CSS: Add metric styling) ...
# Constants
NOTES_DB_PATH = "data/notes-00000.tsv"
STATUS_DB_PATH = "data/noteStatusHistory-00000.tsv"
RATINGS_DB_PATH = "data/ratings-*.tsv"

# --- Helper Functions ---

def deterministic_sample(df, n=5000, seed=42):
    """
    Visual Engine: Downsample data for rendering performance while keeping it frozen.
    """
    if df is None or df.empty:
        return df
    if len(df) <= n:
        return df
    return df.sample(n=n, random_state=seed)

# --- Data Engine (DuckDB) ---

# --- In-Line Insight Generator (WebLLM) ---
import streamlit.components.v1 as components

def render_inline_insight(context_data, element_id):
    """
    Renders a self-contained WebLLM component for In-Line Insight Generation.
    Default: 'Generate Strategic Insight' Button.
    Active: Streams AI Summary properly formatted.
    """
    
    # Serialize context
    context_json = json.dumps(context_data)
    
    # 3-Layer System Prompt (Hardcoded)
    system_prompt = "You are a Forensic Intelligence Analyst for the 'VIP Intelligence Platform'. Data Source: You are analyzing 'Community Notes' (user-generated fact-checks) on X/Twitter. Definitions: 'Clusters' are groups of misinformation narratives. 'Volume' indicates the threat level (High Volume = High Danger)."
    task_instruction = "Write a 3-bullet executive summary explaining the specific threat revealed in this data. Be brief, strategic, and direct. Do not mention JSON."
    
    # HTML/JS Template
    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Source Sans Pro', sans-serif; background: transparent; color: #e0e0e0; margin: 0; padding: 0; }}
            
            #container {{
                border: 1px solid #333;
                background: #0e1117;
                border-radius: 8px;
                padding: 15px;
                min-height: 60px;
                transition: all 0.3s ease;
            }}
            
            #generate-btn {{
                width: 100%;
                padding: 10px;
                background: linear-gradient(90deg, #FF4B4B 0%, #FF9056 100%);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 600;
                cursor: pointer;
                text-transform: uppercase;
                letter-spacing: 1px;
                font-size: 13px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }}
            
            #generate-btn:hover {{ opacity: 0.9; }}
            #generate-btn:disabled {{ background: #444; cursor: not-allowed; }}
            
            #insight-content {{
                display: none;
                font-size: 14px;
                line-height: 1.5;
            }}
            
            #insight-content ul {{ padding-left: 20px; margin: 0; }}
            #insight-content li {{ margin-bottom: 8px; }}
            
            .spinner {{
                border: 3px solid rgba(255,255,255,0.3);
                border-radius: 50%;
                border-top: 3px solid #fff;
                width: 16px;
                height: 16px;
                animation: spin 1s linear infinite;
            }}
            
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            
        </style>
        <script type="module">
            import {{ CreateMLCEngine }} from "https://esm.run/@mlc-ai/web-llm";

            const SELECTED_MODEL = "Llama-3.2-3B-Instruct-q4f32_1-MLC";
            let engine = null;
            
            const btn = document.getElementById("generate-btn");
            const content = document.getElementById("insight-content");
            const container = document.getElementById("container");
            
            const contextPayload = {context_json};
            const systemPrompt = "{system_prompt}";
            const taskInstruction = "{task_instruction}";
            
            btn.onclick = async () => {{
                btn.disabled = true;
                btn.innerHTML = '<div class="spinner"></div> Analyze Secure Channel...';
                
                try {{
                    // 1. Initialize Engine (Cached)
                    if (!engine) {{
                        engine = await CreateMLCEngine(SELECTED_MODEL, {{
                            initProgressCallback: (report) => {{
                                // Optional: Show progress text if needed
                                console.log(report.text);
                            }}
                        }});
                    }}
                    
                    // 2. Prepare Prompt
                    const messages = [
                        {{ role: "system", content: systemPrompt }},
                        {{ role: "user", content: "Current Data: " + JSON.stringify(contextPayload) + "\\n\\n" + taskInstruction }}
                    ];
                    
                    // 3. UI Transition
                    btn.style.display = 'none';
                    content.style.display = 'block';
                    content.innerHTML = "<i>Analyzing intelligence stream...</i>";
                    
                    // 4. Stream Response
                    const chunks = await engine.chat.completions.create({{
                        messages: messages,
                        stream: true
                    }});

                    let fullText = "";
                    content.innerHTML = ""; // Clear loader
                    
                    for await (const chunk of chunks) {{
                        const delta = chunk.choices[0]?.delta?.content || "";
                        fullText += delta;
                        // Basic Markdown Parsing for Bullets
                        content.innerHTML = fullText.replace(/\\n/g, '<br>').replace(/- /g, '• ');
                    }}
                    
                }} catch (err) {{
                    content.innerHTML = "<span style='color: #ff4b4b'>Encryption Error: " + err.message + "</span>";
                    btn.style.display = 'block';
                    btn.disabled = false;
                    btn.innerHTML = "⚠️ Retry Connection";
                }}
            }};
        </script>
    </head>
    <body>
        <div id="container">
            <button id="generate-btn">✨ Generate Strategic Insight</button>
            <div id="insight-content"></div>
        </div>
    </body>
    </html>
    """
    
    # Render Component (Height adjusts based on content roughly, but fixed for now)
    components.html(html_code, height=250, scrolling=True)

# ----------------------------

def extract_domain(url_list_str):
    """Extract domains from a comma-separated string of URLs."""
    if not url_list_str or pd.isna(url_list_str):
        return []
    
    domains = []
    import re
    urls = re.findall(r'(https?://\S+)', str(url_list_str))
    
    for url in urls:
        # urlparse is imported globally
        domain = urlparse(url).netloc.replace('www.', '')
        if domain:
            domains.append(domain)
    return domains

def search_notes_by_keyword(keyword):
    """
    Search for HELPFUL notes and retrieve columns needed for strategic analysis.
    """
    if not keyword:
        return pd.DataFrame()
    
    keyword = keyword.replace("'", "''")
    
    query = f"""
    SELECT 
        CAST(n.tweetId AS VARCHAR) AS tweetId,
        n.classification,
        n.summary,
        CAST(n.trustworthySources AS VARCHAR) AS trustworthySources,
        CAST(n.createdAtMillis AS BIGINT) AS createdAtMillis,
        n.misleadingFactualError,
        n.misleadingManipulatedMedia,
        n.misleadingOutdatedInformation,
        n.misleadingMissingImportantContext,
        n.misleadingUnverifiedClaimAsFact,
        CAST(n.noteAuthorParticipantId AS VARCHAR) AS noteAuthorParticipantId,
        s.currentStatus,
        CAST(s.timestampMillisOfCurrentStatus AS BIGINT) AS timestampMillisOfCurrentStatus,
        CAST(s.timestampMillisOfFirstNonNMRStatus AS BIGINT) AS timestampMillisOfFirstNonNMRStatus
    FROM '{NOTES_DB_PATH}' AS n
    JOIN '{STATUS_DB_PATH}' AS s ON n.noteId = s.noteId
    WHERE n.summary ILIKE '%{keyword}%'
      AND s.currentStatus = 'CURRENTLY_RATED_HELPFUL'
      AND n.classification = 'MISINFORMED_OR_POTENTIALLY_MISLEADING'
    ORDER BY n.createdAtMillis DESC
    """
    
    try:
        con = duckdb.connect(database=':memory:')
        if not os.path.exists(NOTES_DB_PATH) or not os.path.exists(STATUS_DB_PATH):
            st.error("Data files not found!")
            return pd.DataFrame()

        df = con.execute(query).df()
        return df
    except Exception as e:
        st.error(f"DuckDB Error: {e}")
        return pd.DataFrame()

def search_controversial_notes(keyword):
    """
    Find notes that match the keyword, are NEEDS_MORE_RATINGS, 
    and rank them by Conflict Velocity (Ratings/Hour) and Total Intensity.
    Also Aggregates 'Stalemate Reasons'.
    """
    # 1. Find relevant notes first (Cheap)
    keyword = keyword.replace("'", "''")
    query_notes = f"""
    SELECT 
        CAST(n.tweetId AS VARCHAR) AS tweetId,
        n.noteId,
        n.summary,
        n.classification,
        s.currentStatus,
        CAST(n.createdAtMillis AS BIGINT) AS createdAtMillis,
        CAST(s.timestampMillisOfCurrentStatus AS BIGINT) AS timestampMillisOfCurrentStatus
    FROM '{NOTES_DB_PATH}' AS n
    JOIN '{STATUS_DB_PATH}' AS s ON n.noteId = s.noteId
    WHERE n.summary ILIKE '%{keyword}%'
      AND s.currentStatus = 'NEEDS_MORE_RATINGS'
    ORDER BY n.createdAtMillis DESC
    """
    
    try:
        con = duckdb.connect(database=':memory:')
        if not os.path.exists(NOTES_DB_PATH): return pd.DataFrame()
        
        df_notes = con.execute(query_notes).df()
        
        if df_notes.empty:
            return pd.DataFrame()
            
        # 2. Aggregating Ratings for specific notes (Expensive-ish)
        # Convert list of noteIds to string for SQL IN clause
        note_ids = df_notes['noteId'].tolist()
        ids_str = ",".join([f"'{nid}'" for nid in note_ids])
        
        # SUM boolean/integer flags for stalemate analysis
        # Using simple SUM(column) assuming 0/1 integers.
        query_ratings = f"""
        SELECT 
            noteId,
            COUNT(*) as rating_count,
            SUM(notHelpfulArgumentativeOrBiased) as count_argumentative,
            SUM(notHelpfulOpinionSpeculationOrBias) as count_opinion,
            SUM(notHelpfulSourcesMissingOrUnreliable) as count_missing_sources
        FROM '{RATINGS_DB_PATH}'
        WHERE noteId IN ({ids_str})
        GROUP BY noteId
        ORDER BY rating_count DESC
        """
        
        df_ratings = con.execute(query_ratings).df()
        
        # 3. Merge
        result = pd.merge(df_notes, df_ratings, on='noteId', how='left')
        
        # Fill NA
        cols_to_fill = ['rating_count', 'count_argumentative', 'count_opinion', 'count_missing_sources']
        result[cols_to_fill] = result[cols_to_fill].fillna(0)
        
        # 4. Calculate Velocity (Ratings per Day)
        # Duration = status_time - created_time
        # Avoid division by zero: min 1 hour (as a fraction of a day)
        result['duration_ms'] = result['timestampMillisOfCurrentStatus'] - result['createdAtMillis']
        result['duration_days'] = result['duration_ms'] / (3600000.0 * 24.0)
        # Enforce minimum duration of 1 hour (1/24 days) to prevent massive inflation on instant ratings
        min_duration = 1.0 / 24.0 
        result['duration_days'] = result['duration_days'].apply(lambda x: max(x, min_duration))
        
        result['velocity'] = result['rating_count'] / result['duration_days']
        
        # Sort by Velocity (High Crisis) instead of just raw count
        result = result.sort_values(by='velocity', ascending=False)
        
        return result

    except Exception as e:
        st.error(f"DuckDB Error: {e}")
        return pd.DataFrame()

# --- Clustering Module ---
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

import html
import re

def clean_text(text):
    if not text: return ""
    # 1. HTML Unescape (&quot; -> ")
    text = html.unescape(str(text))
    # 2. Remove URLs
    text = re.sub(r'http\S+', '', text)
    # 3. Remove non-alphanumeric noise (optional, but good for cleanliness)
    # keeping basic punctuation for now handled by vectorizer, but can strip handles
    return text

def cluster_narratives(df, keyword=None, n_clusters=5):
    """
    Cluster notes into narrative themes using TF-IDF + KMeans.
    Returns: list of dicts [{'theme': 'keyword, keyword', 'count': 10, 'notes': df_subset}]
    """
    # Visual Engine: Sample first for performance & stability (Clustering is heavy)
    df_sampled = deterministic_sample(df, n=3000, seed=42)
    
    # Clean text: fillna and apply cleaning
    texts = df_sampled['summary'].fillna('').apply(clean_text)
    
    if len(texts) < 50:
        return None  # Too few to cluster meaningfuly
    
    # Multilingual Stop Words
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    
    # Comprehensive Spanish Stop Words
    spanish_stop_words = [
        'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como',
        'más', 'pero', 'sus', 'le', 'ya', 'o', 'este', 'sí', 'porque', 'esta', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'también', 'me', 'hasta', 
        'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante', 'ellos', 
        'e', 'esto', 'mí', 'antes', 'algunos', 'qué', 'unos', 'yo', 'otro', 'otras', 'otra', 'él', 'tanto', 'esa', 'estos', 'mucho', 'quienes', 
        'nada', 'muchos', 'cual', 'poco', 'ella', 'estar', 'estas', 'algunas', 'algo', 'nosotros', 'mi', 'mis', 'tú', 'te', 'ti', 'tu', 'tus', 
        'ellas', 'nosotras', 'vosotros', 'vosotras', 'os', 'mío', 'mía', 'míos', 'mías', 'tuyo', 'tuya', 'tuyos', 'tuyas', 'suyo', 'suya', 
        'suyos', 'suyas', 'nuestro', 'nuestra', 'nuestros', 'nuestras', 'vuestro', 'vuestra', 'vuestros', 'vuestras', 'es', 'soy', 'eres', 
        'somos', 'sois', 'son', 'sea', 'seas', 'seamos', 'seáis', 'sean', 'sere', 'serás', 'será', 'seremos', 'seréis', 'serán', 'sería', 
        'serías', 'seríamos', 'seríais', 'serían', 'era', 'eras', 'éramos', 'erais', 'eran', 'fui', 'fuiste', 'fue', 'fuimos', 'fuisteis', 
        'fueron', 'fuera', 'fueras', 'fuéramos', 'fuerais', 'fueran', 'fuese', 'fueses', 'fuésemos', 'fueseis', 'fuesen', 'sintiendo', 'sentido', 
        'sentida', 'sentidos', 'sentidas', 'siente', 'sentid', 'tengo', 'tienes', 'tiene', 'tenemos', 'tenéis', 'tienen', 'tenga', 'tengas', 
        'tengamos', 'tengáis', 'tengan', 'tendré', 'tendrás', 'tendrá', 'tendremos', 'tendréis', 'tendrán', 'tendría', 'tendrías', 
        'tendríamos', 'tendríais', 'tendrían', 'tenía', 'tenías', 'teníamos', 'teníais', 'tenían', 'tuve', 'tuviste', 'tuvo', 'tuvimos', 'tuvisteis', 
        'tuvieron', 'tuviera', 'tuvieras', 'tuviéramos', 'tuvierais', 'tuvieran', 'tuviese', 'tuvieses', 'tuviésemos', 'tuvieseis', 'tuviesen', 
        'teniendo', 'tenido', 'tenida', 'tenidos', 'tenidas', 'tened'
    ]
    
    # Combined Stop Words
    final_stop_words = list(ENGLISH_STOP_WORDS.union(spanish_stop_words))

    # 1. Vectorize
    # max_df=0.9 removes terms appearing in >90% of documents (e.g. the search keyword itself)
    vectorizer = TfidfVectorizer(
        max_features=1000, 
        stop_words=final_stop_words, 
        max_df=0.9
    )
    
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return None # Empty vocabulary or other issue

    # 2. Cluster
    # Determine distinct clusters (max 5, or less if small dataset)
    true_k = min(n_clusters, len(texts) // 10) 
    if true_k < 2: return None
    
    kmeans = KMeans(n_clusters=true_k, random_state=42, n_init=10)
    kmeans.fit(tfidf_matrix)
    
    # 3. Label Themes
    # Get top terms for each cluster center
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    terms = vectorizer.get_feature_names_out()
    
    clusters = []
    df_sampled['cluster'] = kmeans.labels_
    
    for i in range(true_k):
        # dynamic label: top 3 keywords
        top_terms = [terms[ind] for ind in order_centroids[i, :3]]
        theme_name = ", ".join(top_terms)
        
        cluster_notes = df_sampled[df_sampled['cluster'] == i]
        
        clusters.append({
            'id': i,
            'theme': theme_name,
            'count': len(cluster_notes),
            'notes': cluster_notes
        })
    
    # Sort by size
    clusters.sort(key=lambda x: x['count'], reverse=True)
    return clusters

def generate_narrative_lifecycle(themes):
    """
    Generate a Stacked Area Chart (Streamgraph) of narrative themes over time.
    X-Axis: Time (Weekly)
    Y-Axis: Volume of Notes
    Color: Theme
    """
    if not themes: return None
    
    all_series = []
    
    for cluster in themes:
        df = cluster['notes'].copy()
        # Ensure date format
        if not pd.api.types.is_datetime64_any_dtype(df['createdAtMillis']):
            df['date'] = pd.to_datetime(df['createdAtMillis'], unit='ms')
        else:
            df['date'] = df['createdAtMillis']
            
        # Filter Data Cleaning
        # 1. Remove Future Dates (Dirty Data)
        now = pd.Timestamp.now()
        df = df[df['date'] <= now]
        
        # 2. Remove Pre-2022 Outliers (Optional cleanup)
        # Keeps chart focused on relevant modern era
        df = df[df['date'] >= pd.Timestamp('2022-01-01')]
        
        if df.empty: continue
            
        # Aggregate by Week
        # Using W-MON start
        counts = df.groupby(pd.Grouper(key='date', freq='W-MON')).size().reset_index(name='Count')
        counts['Theme'] = cluster['theme']
        all_series.append(counts)
        
    if not all_series: return None
    
    full_df = pd.concat(all_series)
    
    # Altair Chart
    chart = alt.Chart(full_df).mark_area().encode(
        x=alt.X('date:T', title='Time (Weekly)'),
        y=alt.Y('Count:Q', stack='center', title='Volume of Notes'),
        color=alt.Color('Theme:N', title='Narrative Theme'),
        tooltip=['date', 'Theme', 'Count']
    ).properties(
        title="Narrative Life-Cycle (Momentum over Time)"
    ).interactive()
    
    return chart



# --- Winning Formula Logic ---
from textblob import TextBlob

def fetch_comparative_data(keyword):
    """
    Fetch both HELPFUL and NOT_HELPFUL notes for comparative analysis.
    """
    keyword = keyword.replace("'", "''")
    query = f"""
    SELECT 
        n.classification,
        n.summary,
        CAST(n.trustworthySources AS VARCHAR) AS trustworthySources,
        s.currentStatus
    FROM '{NOTES_DB_PATH}' AS n
    JOIN '{STATUS_DB_PATH}' AS s ON n.noteId = s.noteId
    WHERE n.summary ILIKE '%{keyword}%'
      AND s.currentStatus IN ('CURRENTLY_RATED_HELPFUL', 'CURRENTLY_RATED_NOT_HELPFUL')
    ORDER BY n.createdAtMillis DESC
    """
    try:
        con = duckdb.connect(database=':memory:')
        if not os.path.exists(NOTES_DB_PATH): return pd.DataFrame()
        return con.execute(query).df()
    except Exception as e:
        return pd.DataFrame()

def analyze_success_drivers(df):
    """
    Compare attributes of HELPFUL (Winners) vs NOT_HELPFUL (Losers).
    Returns: DataFrame of attributes with their respective Win Rates.
    """
    if df.empty: return None
    
    # Label Target
    df['is_helpful'] = df['currentStatus'] == 'CURRENTLY_RATED_HELPFUL'
    total_win_rate = df['is_helpful'].mean()
    
    # 1. Feature Extraction
    
    # Sentiment
    def get_sentiment(text):
        try:
            polarity = TextBlob(str(text)).sentiment.polarity
            if polarity > 0.1: return 'Positive Tone'
            if polarity < -0.1: return 'Negative Tone'
            return 'Neutral Tone'
        except:
            return 'Neutral Tone'
            
    df['sentiment'] = df['summary'].apply(get_sentiment)
    
    # Length
    df['length'] = df['summary'].fillna('').str.len()
    df['length_group'] = pd.cut(df['length'], bins=[0, 100, 200, 1000], labels=['Short (<100 chars)', 'Medium (100-200 chars)', 'Long (>200 chars)'])
    
    # Source Types
    df['sources'] = df['trustworthySources'].fillna('').str.lower()
    df['has_gov_edu'] = df['sources'].str.contains(r'\.gov|\.edu', regex=True)
    df['src_type'] = 'Standard Source'
    df.loc[df['sources'].str.contains(r'\.pdf'), 'src_type'] = 'PDF / Official Doc'
    df.loc[df['has_gov_edu'], 'src_type'] = 'Gov/Edu Source'
    df.loc[df['sources'].str.contains(r'youtube|twitter|x\.com'), 'src_type'] = 'Social Media/Video'
    
    # 2. Aggregation
    insights = []
    
    # Function to calculate impact
    def calc_impact(group_col, label_map=None):
        grouped = df.groupby(group_col)['is_helpful'].agg(['mean', 'count'])
        grouped = grouped[grouped['count'] > 5] # Min sample
        for val, row in grouped.iterrows():
            label = str(val)
            if label_map and val in label_map: label = label_map[val]
            
            insights.append({
                'Attribute': label,
                'Category': group_col,
                'Win_Rate': row['mean'],
                'Note_Count': row['count'],
                'Impact': row['mean'] - total_win_rate
            })
            
    calc_impact('sentiment')
    calc_impact('length_group')
    calc_impact('src_type')
    
    if not insights: return None
    
    insight_df = pd.DataFrame(insights).sort_values(by='Win_Rate', ascending=False)
    insight_df['Win_Rate_Pct'] = (insight_df['Win_Rate'] * 100).round(1)
    
    return {
        'baseline': total_win_rate,
        'data': insight_df
    }
    
def fetch_hall_of_fame(keyword):
    """
    Find the highest-rated HELPFUL notes for a keyword (Semantic Precedents).
    Strategy:
    1. Find candidate notes (Status=HELPFUL, Text match)
    2. Get rating counts for these notes
    3. Sort by count DESC
    4. Deduplicate (Similarity Check)
    """
    from difflib import SequenceMatcher
    
    keyword = keyword.replace("'", "''")
    
    # 1. Candidate Notes (Limit to 150 to ensure enough pool after deduplication)
    query_notes = f"""
    SELECT 
        n.noteId,
        n.summary,
        CAST(n.tweetId AS VARCHAR) AS tweetId,
        CAST(n.createdAtMillis AS BIGINT) AS createdAtMillis
    FROM '{NOTES_DB_PATH}' AS n
    JOIN '{STATUS_DB_PATH}' AS s ON n.noteId = s.noteId
    WHERE n.summary ILIKE '%{keyword}%'
      AND s.currentStatus = 'CURRENTLY_RATED_HELPFUL'
    ORDER BY n.createdAtMillis DESC
    LIMIT 150
    """
    
    try:
        con = duckdb.connect(database=':memory:')
        if not os.path.exists(NOTES_DB_PATH): return pd.DataFrame()
        
        df_notes = con.execute(query_notes).df()
        if df_notes.empty: return pd.DataFrame()
        
        # 2. Get Scores
        note_ids = df_notes['noteId'].tolist()
        ids_str = ",".join([f"'{nid}'" for nid in note_ids])
        
        query_scores = f"""
        SELECT 
            noteId,
            COUNT(*) as helpful_count
        FROM '{RATINGS_DB_PATH}'
        WHERE noteId IN ({ids_str})
          AND helpfulnessLevel = 'HELPFUL'
        GROUP BY noteId
        ORDER BY helpful_count DESC
        """
        
        df_scores = con.execute(query_scores).df()
        
        # 3. Merge
        merged = pd.merge(df_scores, df_notes, on='noteId', how='left')
        
        def is_mostly_english(text):
            """Simple heuristic to detect non-English notes (e.g. Portuguese)."""
            if not text: return False
            text_lower = text.lower()
            
            # Distinctive stop words
            # Portuguese/Spanish: de, que, para, com, por, uma, como
            # English: the, and, with, that, have, from, this
            
            pt_score = 0
            en_score = 0
            
            pt_words = {' de ', ' que ', ' para ', ' com ', ' por ', ' uma ', ' como ', ' em ', ' não ', ' na ', ' do ', ' ao '}
            en_words = {' the ', ' and ', ' with ', ' that ', ' have ', ' from ', ' this ', ' are ', ' for ', ' not ', ' but '}
            
            for w in pt_words:
                if w in text_lower: pt_score += 1
                
            for w in en_words:
                if w in text_lower: en_score += 1
                
            return en_score >= pt_score

        # 4. Deduplication & Language Filter
        final_notes = []
        seen_texts = []
        
        for _, row in merged.iterrows():
            text = row['summary']
            
            # Language Filter
            if not is_mostly_english(text):
                continue
                
            is_dup = False
            for seen in seen_texts:
                # Check similarity: > 0.8 is duplicate
                ratio = SequenceMatcher(None, text, seen).ratio()
                if ratio > 0.8:
                    is_dup = True
                    break
            
            if not is_dup:
                final_notes.append(row)
                seen_texts.append(text)
                
            if len(final_notes) >= 5:
                break
                
        return pd.DataFrame(final_notes)
        
    except Exception as e:
        st.error(f"Error fetching Hall of Fame: {e}")
        return pd.DataFrame()
        


def calculate_coordination(df):
    """
    Analyze author concentration to detect Astroturfing.
    Returns: dict with metrics and proper dataframe for checking distribution.
    """
    if df.empty: return None
    
    # 1. Author Counts
    author_counts = df['noteAuthorParticipantId'].value_counts()
    total_notes = len(df)
    total_authors = len(author_counts)
    
    # 2. Top 1% Control
    # How many authors make up the top 1%? (Min 1 author)
    top_1_percent_count = max(1, int(total_authors * 0.01))
    top_authors = author_counts.head(top_1_percent_count)
    top_1_control_share = top_authors.sum() / total_notes
    
    # 3. Repeat Offenders
    # Count authors with > 1 note
    repeat_offenders = author_counts[author_counts > 1].count()
    
    # 4. Chart Data (Lorentz-ish / Heavy Hitter)
    # create a cumulative distribution
    # Sort authors (already sorted by value_counts detailed)
    # We want: X axis = % of Authors, Y axis = % of Notes
    # But for display, maybe just "Rank" vs "Notes" is clearer for 'Concentration'
    # Let's do a tailored dataframe for 'Concentration of Force'
    chart_df = pd.DataFrame({
        'Author Rank': range(1, len(author_counts) + 1),
        'Notes Written': author_counts.values
    })
    
    return {
        'total_authors': total_authors,
        'top_1_percent_share': top_1_control_share,
        'repeat_offenders': repeat_offenders,
        'chart_data': chart_df
    }

import altair as alt

def generate_crisis_heatmap(df):
    """
    Generate a 2D Heatmap (Day x Hour) of note creation activity.
    """
    if df.empty: return None
    
    # 1. Prepare Data
    # Ensure createdAtMillis is numeric
    df['created_dt'] = pd.to_datetime(df['createdAtMillis'], unit='ms')
    
    # Extract components
    # day_name() returns 'Monday', 'Tuesday', etc.
    # hour returns 0-23
    heatmap_data = df.copy()
    heatmap_data['Day'] = heatmap_data['created_dt'].dt.day_name()
    heatmap_data['Hour'] = heatmap_data['created_dt'].dt.hour
    
    # Aggregate
    chart_data = heatmap_data.groupby(['Day', 'Hour']).size().reset_index(name='Count')
    
    # Sort Days for Y-Axis
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # 2. Altair Chart
    chart = alt.Chart(chart_data).mark_rect().encode(
        x=alt.X('Hour:O', title='Hour of Day (0-23) [UTC]'),
        y=alt.Y('Day:O', sort=days_order, title=None),
        color=alt.Color('Count:Q', scale=alt.Scale(scheme='orangered'), title='Note Count'),
        tooltip=['Day', 'Hour', 'Count']
    ).properties(
        title='Volume by Creation Time (UTC)'
    )
    
    return chart

def run_intelligence_report(keyword):
    with st.spinner(f"Analyzing intelligence for '{keyword}'..."):
        
        results = search_notes_by_keyword(keyword)
        
        if results.empty:
            st.warning(f"No confirmed threats found matching '{keyword}'.")
            return

        # --- 1. Defense Lag Logic ---
        # USE timestampMillisOfFirstNonNMRStatus for accurate speed of defense
        # Fallback to current if first is missing (NaN), though typically present for Helpful notes.
        results['final_ts'] = results['timestampMillisOfFirstNonNMRStatus'].fillna(results['timestampMillisOfCurrentStatus'])
        
        results['lag_hours'] = (results['final_ts'] - results['createdAtMillis']) / 3600000.0
        # Filter negative lag and unrealistic future outliers
        # Valid lag: > 0 
        valid_lag = results[results['lag_hours'] > 0]['lag_hours']
        
        # Determine strict average
        avg_lag = valid_lag.mean() if not valid_lag.empty else 0
        
        # --- 2. Arsenal of Truth Logic ---
        all_domains = []
        # Combine trustworthySources and summary to catch ALL links (contributors often put links in summary)
        # Handle NaN/None by converting to empty string
        sources_text = results['trustworthySources'].fillna('').astype(str) + " " + results['summary'].fillna('').astype(str)
        
        for text in sources_text:
            all_domains.extend(extract_domain(text))
        
        source_counts = pd.Series(all_domains).value_counts().head(10)
        
        # --- 3. Attack Signature Logic ---
        signature_cols = {
            'Factual Error': 'misleadingFactualError',
            'Manipulated Media': 'misleadingManipulatedMedia',
            'Outdated': 'misleadingOutdatedInformation',
            'Missing Context': 'misleadingMissingImportantContext',
            'Unverified': 'misleadingUnverifiedClaimAsFact'
        }
        
        signature_data = {}
        for label, col in signature_cols.items():
            if col in results.columns:
                signature_data[label] = results[col].sum()
        
        sig_df = pd.DataFrame.from_dict(signature_data, orient='index', columns=['Count'])
        
        # --- Visualization Layout ---
        st.markdown("---")
        
        st.markdown("---")
        
        # Save context for Private Intelligence Assistant
        # st.session_state['current_view_data'] = results.head(10).to_dict(orient='records') <-- REMOVED (Implicit)


        # Calculate additional metrics for display
        top_vector = max(signature_data, key=signature_data.get) if signature_data else "Unknown"
        unique_sources_count = len(source_counts)

        # Row 1: High Level Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Confirmed Threats", len(results))
        col2.metric("Avg Defense Speed", f"{results['lag_hours'].mean():.1f}h")
        col3.metric("Top Attack Vector", top_vector)
        col4.metric("Arsenal Size", f"{unique_sources_count} Sources")
        
        st.markdown("---")
        
        # Row 2: Charts (Signatures + Sources)
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("⚠️ Attack Signature")
            st.caption("Breakdown of misinformation tactics used against the target.")
            st.bar_chart(sig_df, use_container_width=True)
            
        with c2:
            st.subheader("🛡️ Arsenal of Truth")
            st.caption("Sources most frequently cited in successful defenses.")
            if not source_counts.empty:
                st.dataframe(source_counts, use_container_width=True, column_config={"value": st.column_config.ProgressColumn("Citations")})
            else:
                st.info("No sources cited in these notes.")

        # Row 2.5: Astroturf Meter (NEW)
        st.markdown("---")
        st.subheader("🤖 Astroturf Meter (Coordination Analysis)")
        st.caption("Detecting artificial amplification by analyzing author concentration.")
        
        coord_data = calculate_coordination(results)
        
        if coord_data:
            am1, am2, am3 = st.columns(3)
            # Top 1% Share
            share_pct = coord_data['top_1_percent_share'] * 100
            am1.metric("Top 1% Control", f"{share_pct:.1f}%", help="Percentage of notes written by the top 1% of authors. >20% suggests coordination.")
            
            # Repeat Offenders
            am2.metric("Repeat Offenders", coord_data['repeat_offenders'], help="Number of authors who wrote more than 1 note on this topic.")
            
            # Total Authors
            am3.metric("Total Authors", coord_data['total_authors'])
            
            # Chart
            st.caption("Concentration of Force (Author Distribution)")
            st.bar_chart(coord_data['chart_data'], x='Author Rank', y='Notes Written', use_container_width=True)
        else:
            st.info("Not enough data for coordination analysis.")

        # Row 2.6: Crisis Response Heatmap (NEW)
        st.markdown("---")
        st.subheader("⏰ Crisis Response Windows (Note Creation Time)")
        st.caption("Forensic Analysis: When is the crisis activity hottest? (Timezone / Staffing Optimization)")
        
        heatmap_chart = generate_crisis_heatmap(results)
        if heatmap_chart:
            st.altair_chart(heatmap_chart, use_container_width=True)
        if heatmap_chart:
            st.altair_chart(heatmap_chart, use_container_width=True)
            # In-Line Insight
            render_inline_insight(
                heatmap_chart.to_dict(), 
                element_id="crisis-heatmap-insight"
            )
        else:
            st.info("No timing data available.")

        # Row 3: Narrative Themes (NEW)
        st.markdown("---")
        st.subheader("🧠 Identified Narrative Themes")
        st.caption("AI-Powered Clustering of Community Note Summaries")
        
        themes = cluster_narratives(results, keyword=keyword)
        
        if themes:
            # Narrative Life-Cycle Chart (NEW)
            lifecycle_chart = generate_narrative_lifecycle(themes)
            if lifecycle_chart:
                st.altair_chart(lifecycle_chart, use_container_width=True)
                
            # In-Line Insight
            # Prepare serializable context (DataFrame is not JSON serializable)
            insight_context = []
            for t in themes[:5]:
                insight_context.append({
                    'theme': t['theme'],
                    'count': t['count'],
                    'top_notes': t['notes']['summary'].head(5).tolist()
                })
            
            render_inline_insight(
                insight_context, 
                element_id="narrative-insight"
            )
            
            for cluster in themes:
                with st.expander(f"Theme: {cluster['theme']} ({cluster['count']} notes)"):
                    # Show top 5 examples
                    st.dataframe(cluster['notes'][['summary']].head(5), use_container_width=True, hide_index=True)
        else:
            if len(results) < 50:
                st.info("Not enough data to cluster narratives (<50 notes). Showing raw feed below.")
            else:
                st.warning("Could not identify distinct themes.")

        # Row 4: Evidence Locker
        st.markdown("---")
        st.subheader("📂 Evidence Locker (Raw Feed)")
        for _, row in results.iterrows():
            with st.expander(f"Incident #{row['tweetId']} ({row['lag_hours']:.1f}h Lag)", expanded=False):
                st.markdown(f"**Community Note:** {row['summary']}")
                links = extract_domain(row['trustworthySources'])
                if links:
                    st.write(f"**Sources:** {', '.join(links)}")
        
        # In-Line Insight for Raw Feed
        render_inline_insight(
             results.head(5).to_dict(orient='records'),
             element_id="evidence-insight"
        )
        
        # st.session_state['current_view_data'] = results.head(10).to_dict(orient='records') <-- REMOVED



def run_controversy_monitor(keyword):
    st.subheader("🔥 Controversy Monitor")
    st.caption("Crisis Radar: High-Velocity Debates & Wedge Issues")
    
    with st.spinner(f"Scanning battlegrounds for '{keyword}'..."):
        df = search_controversial_notes(keyword)
        
        if df.empty:
            st.info("No active controversy found (no high-engagement notes in Needs More Ratings).")
            return

        # --- Metrics Row ---
        # Top Velocity Note
        top_vel = df.iloc[0]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Battlegrounds", len(df), help="Number of distinct notes in 'Needs More Ratings'.")
        m2.metric("Highest Velocity", f"{top_vel['velocity']:.1f} Ratings/Day", help="Speed of rating accumulation (Ratings per Day).")
        m3.metric("Most Heated", f"{int(df['rating_count'].max())} Total Ratings", help="Highest total volume of ratings.")

        st.markdown("---")
        
        # --- Charts Row ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("⚡ Crisis Radar (Velocity)")
            st.caption("Which controversies are exploding RIGHT NOW?")
            # Plot Velocity vs Total Ratings
            st.scatter_chart(df, x='rating_count', y='velocity', color='classification', use_container_width=True)
            
        with c2:
            st.subheader("🛑 Stalemate Reasoning")
            st.caption("Why is the community rejecting these notes?")
            # Aggregate sums
            reasons = {
                "Argumentative/Biased": df['count_argumentative'].sum(),
                "Opinion/Speculation": df['count_opinion'].sum(),
                "Missing Sources": df['count_missing_sources'].sum()
            }
            st.bar_chart(pd.Series(reasons), horizontal=True, use_container_width=True)

        # --- Wedge Narrative Clusters ---
        st.markdown("---")
        st.subheader("🧩 Wedge Issues (Clustered Narratives)")
        st.caption("Thematic grouping of unresolved debates.")
        
        # Reuse robust clustering logic
        themes = cluster_narratives(df, keyword=keyword)
        
        # Smart Context: Export themes to sidebar
        if themes:
            # Serialize themes for context (just top 5 themes and their top notes)
            export_themes = []
            for t in themes[:5]:
                export_themes.append({
                    "theme": t['theme'],
                    "volume": t['count'],
                    "top_notes": t['notes'].head(3)['summary'].tolist()
                })
            
            # Explicit Button for Themes
            if st.button("🧠 Analyze Narratives (Clusters)"):
                inject_context(export_themes, primer_text="You are a narrative analyst. Identify the core wedge issues and rumor clusters from this data.")
            
            # st.session_state['current_view_data'] = export_themes <-- REMOVED (Implicit)

    
        
        if themes:
            for cluster in themes:
                with st.expander(f"Theme: {cluster['theme']} (Intensity: {int(cluster['notes']['rating_count'].sum())} votes)"):
                    # Show top velocity notes in this cluster
                    top_cluster_notes = cluster['notes'].sort_values(by='velocity', ascending=False).head(5)
                    for _, row in top_cluster_notes.iterrows():
                        st.markdown(f"**{row['velocity']:.1f} ratings/day** | {row['summary']}")
        else:
            if len(df) < 50:
                 st.info("Not enough data to cluster (>50 required).")
            else:
                 st.warning("No distinct themes found.")

        # --- Raw List (Sorted by Velocity) ---
        st.markdown("---")
        st.subheader("⚔️ Active Battles (Sorted by Velocity)")
        for _, row in df.head(50).iterrows():
             with st.expander(f"🔥 {row['velocity']:.1f}/day | Total: {int(row['rating_count'])} | #{row['tweetId']}"):
                st.markdown(f"**Note:** {row['summary']}")
                st.caption(f"Reason: {row['classification']} | Created: {pd.to_datetime(row['createdAtMillis'], unit='ms')}")
                # Show breakdown for this specific note
                st.write(f"Arg: {int(row['count_argumentative'])} | Opn: {int(row['count_opinion'])} | Src: {int(row['count_missing_sources'])}")


def run_winning_formula(keyword):
    st.subheader("🏆 The Winning Formula")
    st.caption("Success Driver Analysis: How to write notes that WIN.")
    
    with st.spinner(f"Analyzing success patterns for '{keyword}'..."):
        df = fetch_comparative_data(keyword)
        
        if df.empty or len(df) < 20:
            st.warning("Insufficient data for statistical analysis (need > 20 mixed notes).")
            return
            
        analysis = analyze_success_drivers(df)
        
        if not analysis:
            st.info("No significant drivers found.")
            return
            
        baseline = analysis['baseline'] * 100
        drivers = analysis['data']
        
        if st.button("🧠 Analyze Success Formula"):
             inject_context(drivers.head(10).to_dict(orient='records'), primer_text="You are a content strategist. Analyze these 'Winning' and 'Losing' attributes. Give actionable advice on how to write better notes.")
        
        # st.session_state['current_view_data'] = drivers.head(10).to_dict(orient='records') <-- REMOVED


        
        # --- Metrics ---
        col1, col2 = st.columns(2)
        col1.metric("Community Baseline", f"{baseline:.1f}%", help="Global Helpful Rate for this topic.")
        
        best_attrib = drivers.iloc[0]
        col2.metric("Top Success Driver", best_attrib['Attribute'], f"+{best_attrib['Impact']*100:.1f}% Boost")
        
        st.markdown("---")
        
        # --- Scorecard ---
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.subheader("✅ Best Practices (High Win Rate)")
            # Top 3
            top_drivers = drivers.head(3)
            for _, row in top_drivers.iterrows():
                boost = row['Impact'] * 100
                st.success(f"**{row['Attribute']}**: {row['Win_Rate_Pct']}% Success (+{boost:.1f}%)")
                
        with c2:
            st.subheader("❌ Risky Tactics (Low Win Rate)")
            # Bottom 3
            bad_drivers = drivers.tail(3).sort_values(by='Win_Rate', ascending=True)
            for _, row in bad_drivers.iterrows():
                drop = row['Impact'] * 100
                st.error(f"**{row['Attribute']}**: {row['Win_Rate_Pct']}% Success ({drop:.1f}%)")
                
        # --- Chart ---
        st.markdown("---")
        st.caption("Success Rate by Attribute")
        st.bar_chart(drivers, x='Attribute', y='Win_Rate_Pct', color='Category', use_container_width=True)

        # --- Hall of Fame (NEW) ---
        st.markdown("---")
        st.subheader("🏛️ Hall of Fame (Semantic Precedents)")
        st.caption("Top-Rated Notes for Inspiration")
        
        hof_df = fetch_hall_of_fame(keyword)
        if not hof_df.empty:
            for _, row in hof_df.iterrows():
                # Polish: Tweet Link & URL cleaning
                tweet_link = f"https://x.com/i/web/status/{row['tweetId']}"
                
                # Simple cleaning: Move URLs to bottom?
                # Actually, let's keep it simple: Just Bold the note text and link the header
                # Extract URLs for footer if we want, but regex replacement is safer.
                
                # Remove http links from main text for readability
                main_text = re.sub(r'http\S+', '', row['summary']).strip()
                if not main_text: 
                    main_text = row['summary']
                
                # Create a safe display version (escape $, and ensure blockquote works)
                display_text = main_text.replace('$', '\$')
                
                # Extract original sources
                sources = re.findall(r'(https?://\S+)', row['summary'])
                
                # Unbox: Use container with border for distinct visual hierarchy
                with st.container(border=True):
                    # Header Logic
                    score = row['helpful_count']
                    if score >= 30:
                        header_label = f"🏆 Score: {score} (Viral Consensus)"
                    elif score >= 10:
                        header_label = f"🥈 Score: {score} (Strong Consensus)"
                    else:
                        header_label = f"✅ Score: {score} (Verified)"
                        
                    st.markdown(f"### {header_label}")
                    st.markdown("**(Net Count of Highly-Rated Contributors who agreed)**")
                    
                    # Body
                    st.markdown(f"**The Precedent:**")
                    # Use standard blockquote
                    st.markdown(f"> {display_text}")
                    st.markdown("---")
                    
                    # Footer
                    cols = st.columns([3, 1])
                    with cols[0]:
                        if sources:
                            st.caption("📚 Supported By:")
                            for src in sources:
                                domain = urlparse(src).netloc.lower()
                                
                                # Default: Clean domain (no brackets)
                                label = domain
                                
                                if 'twitter.com' in domain or 'x.com' in domain:
                                    label = "Primary Source (Tweet)"
                                elif 'youtube.com' in domain or 'youtu.be' in domain:
                                    label = "Video Evidence (YouTube)"
                                elif '.gov' in domain:
                                    label = "Official Source (.gov)"
                                elif '.edu' in domain:
                                    label = "Official Source (.edu)"
                                
                                st.markdown(f"- [{label}]({src})")
                    
                    with cols[1]:
                         st.markdown(f"🔗 [Original Tweet]({tweet_link})")
                         st.caption(f"{pd.to_datetime(row['createdAtMillis'], unit='ms').strftime('%Y-%m-%d')}")
        else:
            st.info("No Hall of Fame data available (could not retrieve rating counts for top notes).")


# --- Main App ---
def main():
    st.title("🛡️ VIP Intelligence Platform")
    st.markdown("### Strategic Analysis of Misinformation Campaigns")

    # Main Input (Search)
    with st.form(key='search_form'):
        col1, col2 = st.columns([4, 1])
        with col1:
            keyword = st.text_input("Intelligence Target (e.g. 'Elon Musk', 'Tesla')", placeholder="Enter keyword to analyze...")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button(label="Generate Report", type="primary", use_container_width=True)

    if submit_button:
        if not keyword:
            st.warning("Please enter a target keyword.")
        else:
            # Create Tabs
            tab_intel, tab_contro, tab_coach = st.tabs(["📊 Intelligence Report", "🔥 Controversy Monitor", "🏆 Winning Formula"])
            
            with tab_intel:
                run_intelligence_report(keyword)
def main():
    st.title("🛡️ VIP Intelligence Platform")
    st.markdown("### Strategic Analysis of Misinformation Campaigns")

    # Initialize Session State
    if 'active_keyword' not in st.session_state:
        st.session_state['active_keyword'] = None
    if 'webllm_context' not in st.session_state:
        st.session_state['webllm_context'] = "{}"

    # Main Input (Search)
    with st.form(key='search_form'):
        col1, col2 = st.columns([4, 1])
        with col1:
            keyword_input = st.text_input("Intelligence Target (e.g. 'Elon Musk', 'Tesla')", placeholder="Enter keyword to analyze...")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button(label="Generate Report", type="primary", use_container_width=True)

    # 1. Handle Form Submission
    if submit_button and keyword_input:
        st.session_state['active_keyword'] = keyword_input
        # Reset context on new search to avoid stale data
        st.session_state['webllm_context'] = "{}" 
        st.rerun()

    # 2. Render Main Dashboard (Persistent)
    if st.session_state['active_keyword']:
        keyword = st.session_state['active_keyword']
        
        # Smart Navigation (Stateful)
        if 'active_view' not in st.session_state:
            st.session_state['active_view'] = "📊 Intelligence Report"
            
        view = st.radio(
            "Navigation", 
            ["📊 Intelligence Report", "🔥 Controversy Monitor", "🏆 The Winning Formula"],
            horizontal=True,
            key='active_view',
            label_visibility="collapsed"
        )
        st.markdown("---")
        
        # Router Logic
        if view == "📊 Intelligence Report":
            run_intelligence_report(keyword)
        elif view == "🔥 Controversy Monitor":
            run_controversy_monitor(keyword)
        elif view == "🏆 The Winning Formula":
            run_winning_formula(keyword)

    # --- END OF DASHBOARD ---
    
if __name__ == "__main__":
    main()
