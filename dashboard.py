import streamlit as st
import pandas as pd
import duckdb
import os
import json
from urllib.parse import urlparse
import sys
import shutil
import hashlib

# ... (Configuration and CSS remain similar, updating Title)
st.set_page_config(
    page_title="Community Notes Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- VISUAL ENHANCEMENT: High-Visibility Sidebar Toggle ---
st.markdown("""
<style>
    /* Make the sidebar toggle button LARGER and RED so it is impossible to miss */
    [data-testid="stSidebarCollapseButton"] {
        transform: scale(2.0) !important;
        color: #FF4B4B !important;
        margin-left: 20px !important;
        margin-top: 10px !important;
        border: 2px solid #FF4B4B !important;
        background-color: rgb(255 75 75 / 10%) !important;
        border-radius: 50% !important;
    }
    [data-testid="stSidebarCollapseButton"]:hover {
        background-color: rgb(255 75 75 / 30%) !important;
        box-shadow: 0 0 15px #FF4B4B !important;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
CN_DUCKDB_PATH = os.getenv("CN_DUCKDB_PATH")  # Mounted source contract
ALLOW_TSV_FALLBACK = os.getenv("ALLOW_TSV_FALLBACK") == "1"
IS_CLOUD_RUN = os.getenv("K_SERVICE") is not None
IS_STRICT = IS_CLOUD_RUN or os.getenv("CN_STRICT") == "1"

# --- Ephemeral Storage Optimization (Copy-Once Guard) ---
_DB_LOCALIZED = False  # Module-level: prevents Streamlit rerun re-copies

def _localize_db_once(mounted_path: str, local_path: str) -> str:
    """
    Copy DB from GCS mount to /tmp for fast local access.
    Runs ONCE per Cloud Run instance, not per Streamlit interaction.
    """
    global _DB_LOCALIZED
    if _DB_LOCALIZED:
        return local_path  # Already done this instance
    
    # Validity check: exists AND non-zero size
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        print(f"INFO: Localized DB. Source: {mounted_path}. Local: {local_path}. Size: {size_mb:.1f}MB. Action: skipped.", file=sys.stderr)
        _DB_LOCALIZED = True
        return local_path
    
    # Atomic copy: temp file → rename
    tmp_path = local_path + ".tmp"
    shutil.copy2(mounted_path, tmp_path)
    os.rename(tmp_path, local_path)
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"INFO: Localized DB. Source: {mounted_path}. Local: {local_path}. Size: {size_mb:.1f}MB. Action: copied.", file=sys.stderr)
    _DB_LOCALIZED = True
    return local_path

# --- Startup Logic (Environment-Aware) ---

def _resolve_db_path():
    """
    Resolves the database path based on environment.
    - Strict (Cloud Run or CN_STRICT=1): Validate → Localize → Connect. Fail fast.
    - Local (default): Flexible fallback. Warn on issues.
    Returns: (db_path_in_use, using_artifact, mode_label)
    """
    if IS_STRICT:
        # --- STRICT MODE: Validate → Localize → Connect ---
        if not CN_DUCKDB_PATH:
            msg = "CRITICAL ERROR: CN_DUCKDB_PATH not set. Check deployment config."
            print(msg, file=sys.stderr)
            sys.exit(1)
        if not (os.path.exists(CN_DUCKDB_PATH) and os.access(CN_DUCKDB_PATH, os.R_OK)):
            msg = f"CRITICAL ERROR: CN_DUCKDB_PATH={CN_DUCKDB_PATH} not found/readable. Check GCS mount."
            print(msg, file=sys.stderr)
            sys.exit(1)
        
        # Localize to /tmp for performance (Cloud Run only)
        if IS_CLOUD_RUN:
            local_path = "/tmp/community_notes.duckdb"
            db_path_in_use = _localize_db_once(CN_DUCKDB_PATH, local_path)
        else:
            db_path_in_use = CN_DUCKDB_PATH  # Local strict: use directly
        
        return db_path_in_use, True, "PRODUCTION" if IS_CLOUD_RUN else "LOCAL (strict)"
    
    else:
        # --- LOCAL: Flexible Mode ---
        # Priority: env var → full artifact → sample artifact → TSV
        
        if CN_DUCKDB_PATH and os.path.exists(CN_DUCKDB_PATH) and os.access(CN_DUCKDB_PATH, os.R_OK):
            return CN_DUCKDB_PATH, True, "LOCAL (env var)"
        
        if CN_DUCKDB_PATH:
            print(f"WARNING: CN_DUCKDB_PATH={CN_DUCKDB_PATH} not found. Trying defaults...", file=sys.stderr)
        
        full_artifact = "artifacts/community_notes_full.duckdb"
        sample_artifact = "artifacts/community_notes_sample.duckdb"
        
        if os.path.exists(full_artifact):
            return full_artifact, True, "LOCAL (full artifact)"
        if os.path.exists(sample_artifact):
            return sample_artifact, True, "LOCAL (sample artifact)"
        
        if ALLOW_TSV_FALLBACK:
            print("WARNING: No DuckDB artifact. Using TSV fallback.", file=sys.stderr)
            return None, False, "LOCAL (TSV fallback)"
        
        msg = "Configuration Error: No DuckDB artifact found. Run 'python scripts/build_db.py' or set ALLOW_TSV_FALLBACK=1."
        st.error(msg)
        print(msg, file=sys.stderr)
        sys.exit(1)

# Execute startup resolution
DB_PATH_IN_USE, USING_ARTIFACT, _MODE_LABEL = _resolve_db_path()

if USING_ARTIFACT:
    NOTES_DB_PATH = "notes"
    STATUS_DB_PATH = "status_history"
    RATINGS_DB_PATH = "ratings"
    
    # Startup Telemetry (after localization)
    try:
        with duckdb.connect(database=DB_PATH_IN_USE, read_only=True) as con:
            count = con.execute("SELECT count(*) FROM notes").fetchone()[0]
            print(f"INFO: Startup Complete. Mode: {_MODE_LABEL}. Path: {DB_PATH_IN_USE}. Notes: {count}.", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Startup telemetry failed: {e}", file=sys.stderr)
else:
    NOTES_DB_PATH = "data/notes-00000.tsv"
    STATUS_DB_PATH = "data/noteStatusHistory-00000.tsv"
    RATINGS_DB_PATH = "data/ratings-*.tsv"
    print(f"INFO: Startup Complete. Mode: {_MODE_LABEL}. Using TSV files.", file=sys.stderr)

# --- Helper Functions ---

def get_db_connection():
    """
    Connects to DB_PATH_IN_USE (the localized /tmp copy in Cloud Run).
    """
    if USING_ARTIFACT:
        try:
            return duckdb.connect(database=DB_PATH_IN_USE, read_only=True)
        except Exception as e:
            st.error(f"Failed to connect to artifact: {e}")
            return duckdb.connect(database=':memory:')
    else:
        return duckdb.connect(database=':memory:')

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
from cloud_intel import UniversalCloudAdapter, get_investigator_system_prompt
from case_manager import CaseManager

# Initialize Persistence Layer
cm = CaseManager()

# Startup cleanup: Remove legacy 0-turn cases older than 1 hour
# This prevents clutter from earlier versions that created cases on app load
_cleanup_count = cm.cleanup_empty_cases(max_age_hours=1.0)
if _cleanup_count > 0:
    print(f"[Dashboard] Startup cleanup removed {_cleanup_count} empty case(s)", file=sys.stderr)

def render_inline_insight(context_data, element_id, prompt_context=""):
    """
    Renders a self-contained WebLLM component for In-Line Insight Generation.
    Default: 'Generate Strategic Insight' Button.
    Active: Streams AI Summary properly formatted.
    Features: JSON Datetime Serialization, Strategic Memo UI.
    """
    
    # Serialize context with Datetime and Numpy handling
    import numpy as np
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
            return str(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        raise TypeError (f"Type {type(obj)} not serializable")

    context_json = json.dumps(context_data, default=json_serial)
    
    # 3-Layer System Prompt (Hardcoded + Dynamic Context)
    base_system_prompt = "You are a data analyst for the Community Notes Analytics platform. Data Source: 'Community Notes' (user-generated fact-checks) on X/Twitter. Definitions: 'Clusters' are groups of misinformation narratives. 'Volume' indicates the threat level."
    
    if prompt_context:
        full_system_prompt = f"{base_system_prompt} \n\nSPECIFIC TASK CONTEXT: {prompt_context}"
    else:
        full_system_prompt = base_system_prompt

    task_instruction = "Write a 3-bullet executive summary explaining the strategic implications of this data. Use a professional, direct tone. Format as a 'Strategic Briefing'. Do not mention JSON."
    
    # HTML/JS Template
    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap');

            body {{ 
                font-family: 'Inter', sans-serif; 
                background: transparent; 
                color: #e0e0e0; 
                margin: 0; 
                padding: 0;
                min-height: auto;
                height: auto;
            }}
            
            /* Button Wrapper for Alignment */
            .button-container {{
                display: flex;
                justify-content: flex-end;
                padding: 10px 0 5px 0;
                margin: 0;
                min-height: 45px;
            }}

            /* Tool-like Button State */
            #generate-btn {{
                width: auto;
                min-width: 140px;
                padding: 8px 16px;
                background: transparent;
                color: #FF4B4B;
                border: 1px solid #FF4B4B;
                border-radius: 4px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: 700;
                cursor: pointer;
                text-transform: uppercase;
                letter-spacing: 1px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                transition: all 0.2s ease;
                margin: 0;
            }}
            
            #generate-btn:hover {{ 
                background: rgba(255, 75, 75, 0.1);
                box-shadow: 0 0 15px rgba(255, 75, 75, 0.2);
                transform: translateY(-1px);
            }}
            
            #generate-btn:disabled {{ 
                border-color: #444;
                color: #666;
                cursor: not-allowed; 
                transform: none;
                box-shadow: none;
            }}
            
            /* Classified Memo Container */
            #container {{
                display: none; 
                border-left: 4px solid #FF4B4B; /* Red Accent */
                background: #1E1E1E; /* Professional Dark Slate */
                border-radius: 0 4px 4px 0;
                padding: 15px;
                margin-top: 10px;
                margin-bottom: 0;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                animation: slideDown 0.4s ease-out;
            }}

            @keyframes slideDown {{
                from {{ opacity: 0; transform: translateY(-10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}

            .memo-header {{
                display: flex;
                align-items: center;
                margin-bottom: 15px;
                border-bottom: 1px solid #333;
                padding-bottom: 10px;
            }}

            .memo-icon {{
                font-size: 24px;
                margin-right: 12px;
            }}

            .memo-title {{
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                color: #888;
                text-transform: uppercase;
                letter-spacing: 1.5px;
            }}
            
            #insight-content {{
                font-size: 15px;
                line-height: 1.6;
                color: #ddd;
            }}
            
            /* Markdown Styling */
            #insight-content ul {{ padding-left: 20px; margin: 10px 0; }}
            #insight-content li {{ margin-bottom: 8px; }}
            #insight-content strong {{ color: #FF9056; font-weight: 700; }}
            #insight-content blockquote {{ 
                border-left: 3px solid #FF9056;
                margin: 10px 0;
                padding-left: 15px;
                color: #aaa;
                font-style: italic;
            }}

            .spinner {{
                border: 2px solid rgba(255,255,255,0.1);
                border-radius: 50%;
                border-top: 2px solid #fff;
                width: 14px;
                height: 14px;
                animation: spin 0.8s linear infinite;
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
            
            // Handle potentially large payloads or special chars by encoding
            const contextPayload = {context_json};
            const systemPrompt = `{full_system_prompt}`;
            const taskInstruction = "{task_instruction}";
            
            btn.onclick = async () => {{
                // Transitions
                btn.disabled = true;
                btn.innerHTML = '<div class="spinner"></div> CHECKING WEBGPU...';
                
                try {{
                    // 0. Check WebGPU support
                    if (!navigator.gpu) {{
                        throw new Error("WebGPU not supported in this browser. Use Chrome 113+ or Edge 113+.");
                    }}
                    
                    // 1. Initialize Engine (Cached)
                    if (!engine) {{
                        btn.innerHTML = '<div class="spinner"></div> DOWNLOADING MODEL (1.5GB)...';
                        engine = await CreateMLCEngine(SELECTED_MODEL, {{
                            initProgressCallback: (report) => {{
                                console.log(report.text);
                                // Show download progress
                                if (report.progress) {{
                                    const pct = Math.round(report.progress * 100);
                                    btn.innerHTML = `<div class="spinner"></div> LOADING: ${{pct}}%`;
                                }} else {{
                                    btn.innerHTML = '<div class="spinner"></div> ' + report.text.substring(0,30) + '...';
                                }}
                            }}
                        }});
                    }}
                    
                    btn.innerHTML = '<div class="spinner"></div> GENERATING...';
                    
                    // 2. Prepare Prompt
                    const messages = [
                        {{ role: "system", content: systemPrompt }},
                        {{ role: "user", content: "MISSION DATA: " + JSON.stringify(contextPayload) + "\\n\\nINSTRUCTION: " + taskInstruction }}
                    ];
                    
                    // 3. UI Switch to Memo Mode
                    btn.style.display = 'none';
                    container.style.display = 'block';
                    content.innerHTML = "<div style='display:flex; align-items:center; gap:10px; color:#666;'><div class='spinner'></div><i>Analyzing Intelligence Stream...</i></div>";
                    
                    // 4. Stream Response
                    const chunks = await engine.chat.completions.create({{
                        messages: messages,
                        stream: true
                    }});

                    let fullText = "";
                    content.innerHTML = ""; 
                    
                    for await (const chunk of chunks) {{
                        const delta = chunk.choices[0]?.delta?.content || "";
                        fullText += delta;
                        
                        // Simple Markdown Parser for the Stream
                        let formatted = fullText
                            .replace(/\\n/g, '<br>')
                            .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                            .replace(/> (.*)/g, '<blockquote>$1</blockquote>')
                            .replace(/- /g, '• ');
                            
                        content.innerHTML = formatted;
                    }}
                    
                }} catch (err) {{
                    container.style.display = 'none';
                    btn.style.display = 'flex';
                    btn.disabled = false;
                    btn.innerHTML = "⚠️ " + err.message.substring(0, 40);
                    console.error("WebLLM Error:", err);
                }}
            }};
        </script>
    </head>
    <body>
        <div class="button-container">
            <button id="generate-btn">✨ GENERATE STRATEGIC INSIGHT</button>
        </div>
        
        <div id="container">
            <div class="memo-header">
                <span class="memo-icon">🛡️</span>
                <span class="memo-title">AI INTELLIGENCE ASSESSMENT // CLASSIFIED</span>
            </div>
            <div id="insight-content"></div>
        </div>
    </body>
    </html>
    """
    
    # Render WebGPU Component - Increased height to 350px for better readability
    components.html(html_code, height=350, scrolling=True)

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

def format_friendly_label(text):
    """Converts SCREAMING_SNAKE_CASE to Title Case with spaces."""
    if not text or not isinstance(text, str):
        return str(text)
    return text.replace('_', ' ').title()

def search_notes_by_keyword(keyword):
    """
    Search for HELPFUL notes and retrieve columns needed for strategic analysis.
    """
    if not keyword:
        return pd.DataFrame()
    
    keyword = keyword.replace("'", "''")
    
    query = f"""
    SELECT 
        CAST(n.noteId AS VARCHAR) AS noteId,
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
    WHERE (n.summary ILIKE '%{keyword}%' OR CAST(n.noteId AS VARCHAR) = '{keyword}')
      AND s.currentStatus = 'CURRENTLY_RATED_HELPFUL'
      AND n.classification = 'MISINFORMED_OR_POTENTIALLY_MISLEADING'
    ORDER BY n.createdAtMillis DESC
    """
    
    try:
        con = get_db_connection()
        # In artifact mode, we don't need to check for TSV files
        if not USING_ARTIFACT and (not os.path.exists(NOTES_DB_PATH) or not os.path.exists(STATUS_DB_PATH)):
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
        con = get_db_connection()
        if not USING_ARTIFACT and not os.path.exists(NOTES_DB_PATH): return pd.DataFrame()
        
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
        con = get_db_connection()
        if not USING_ARTIFACT and not os.path.exists(NOTES_DB_PATH): return pd.DataFrame()
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
        con = get_db_connection()
        if not USING_ARTIFACT and not os.path.exists(NOTES_DB_PATH): return pd.DataFrame()
        
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
        
        # Row 2: Charts (Signatures + Sources)
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("⚠️ Attack Signature")
            st.caption("Breakdown of misinformation tactics used against the target.")
            st.bar_chart(sig_df, use_container_width=True)
            render_inline_insight(
                signature_data,
                element_id="attack-sig-insight",
                prompt_context=f"Analyze the misinformation tactics. Explain why '{top_vector}' is the dominant vector."
            )
            
        with c2:
            st.subheader("🛡️ Arsenal of Truth")
            st.caption("Sources most frequently cited in successful defenses.")
            if not source_counts.empty:
                st.dataframe(source_counts, use_container_width=True, column_config={"value": st.column_config.ProgressColumn("Citations")})
                render_inline_insight(
                    source_counts.to_dict(),
                    element_id="arsenal-insight",
                    prompt_context="Analyze the defensive sources. Which websites are winning the argument?"
                )
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
            
            # Prepare lightweight payload (exclude chart df)
            astro_payload = {k:v for k,v in coord_data.items() if k != 'chart_data'}
            render_inline_insight(
                astro_payload,
                element_id="astroturf-insight",
                prompt_context="Analyze the bot coordination levels. Is this organic or artificial?"
            )
        else:
            st.info("Not enough data for coordination analysis.")

        # Row 2.6: Crisis Response Heatmap (NEW)
        st.markdown("---")
        st.subheader("⏰ Crisis Response Windows (Note Creation Time)")
        st.caption("Forensic Analysis: When is the crisis activity hottest? (Timezone / Staffing Optimization)")
        
        heatmap_chart = generate_crisis_heatmap(results)
        if heatmap_chart:
            st.altair_chart(heatmap_chart, use_container_width=True)
            # In-Line Insight
            render_inline_insight(
                heatmap_chart.to_dict(), 
                element_id="crisis-heatmap-insight",
                prompt_context="Analyze the attack timing. When should the client be most alert?"
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
                element_id="narrative-insight",
                prompt_context="Identify the core wedge issues and rumor clusters from this data."
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
             element_id="evidence-insight",
             prompt_context="Summarize the specific claims made in these raw logs."
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
            render_inline_insight(
                reasons,
                element_id="stalemate-insight",
                prompt_context="Analyze the rejection reasons. What psychological barriers are preventing consensus?"
            )

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
            
            # Explicit Button for Themes (REPLACED)
            render_inline_insight(
                export_themes,
                element_id="wedge-insight",
                prompt_context="Identify the core wedge issues and rumor clusters from this data."
            )

    
        
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
        
        # st.session_state['current_view_data'] = drivers.head(10).to_dict(orient='records') <-- REMOVED
        
        # st.session_state['current_view_data'] = drivers.head(10).to_dict(orient='records') <-- REMOVED
        
        render_inline_insight(
            drivers.head(10).to_dict(orient='records'),
            element_id="success-insight",
            prompt_context="Analyze these success drivers. What specific writing techniques are leading to 'Helpful' ratings?"
        )


        
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
        
        render_inline_insight(
            fetch_hall_of_fame(keyword).head(3).to_dict(orient='records'),
             element_id="hof-insight",
             prompt_context="Analyze these top-rated notes. Use them to create a 'Style Guide' for effective counter-misinformation."
        )
        
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
                display_text = main_text.replace('$', r'\$')
                
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



def render_forensic_message(data):
    """
    Renders the strictly typed Evidence Contract JSON with a Reproducibility Card.
    """
    # 1. Metadata Header (Reproducibility Card)
    meta = data.get("query_meta", {})
    stats = meta.get("retrieval_stats", {})
    filters = meta.get("filters", {})
    
    q_id = meta.get("query_id", "Unknown")[:8]
    b_id = stats.get("evidence_bundle_id", "Unknown")[:8]
    
    # Card Container
    with st.expander(f"🧾 Forensic Record: {q_id}", expanded=True):
        # Top Row: Stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Matches", stats.get('total_matches', 0))
        c2.metric("Evidence Sent", stats.get('evidence_bundle_size', 0))
        c3.caption(f"**Query ID**: `{q_id}`")
        c4.caption(f"**Bundle ID**: `{b_id}`")
        
        # Middle Row: Filters & Actions
        st.markdown("---")
        ac1, ac2 = st.columns([3, 1])
        with ac1:
            st.markdown(f"**Active Filters**: `Time: {filters.get('time_range', {}).get('start', 'N/A')[:4]}+`")
        with ac2:
             # Actions
             full_q_id = meta.get("query_id")
             bundle = st.session_state.get("evidence_bundles", {}).get(full_q_id)
             
             if bundle:
                 # Convert list of dicts to CSV
                 import pandas as pd
                 csv_data = pd.DataFrame(bundle).to_csv(index=False).encode('utf-8')
                 
                 st.download_button(
                     label="⬇️ Export Evidence",
                     data=csv_data,
                     file_name=f"evidence_bundle_{q_id}.csv",
                     mime="text/csv",
                     key=f"btn_export_{q_id}",
                     help="Download absolute evidence bundle used for this answer."
                 )
             else:
                 st.button("⬇️ Export Evidence", disabled=True, key=f"btn_export_disabled_{q_id}", help="Evidence bundle not found in archive.")
             
        # Bottom Row: Debug Details
        if st.checkbox("Show Query Details", key=f"chk_{q_id}"):
            st.code(json.dumps(meta, indent=2), language="json")

    st.markdown("### Findings") # Changed from "### findings" to "### Findings" for better title casing
    
    findings = data.get("dataset_findings", {})
    
    # 2. Claims & Evidence
    claims = findings.get("claims", [])
    if claims:
        for i, claim in enumerate(claims):
            escaped_claim = claim.get('claim_text', '').replace('$', r'\$')
            
            # Render Claim
            st.markdown(f"**{i+1}.** {escaped_claim}")
            
            # Render Evidence Citations
            evidence = claim.get("evidence", [])
            
            # Uncertainty Badge
            unc = claim.get("uncertainty", "low").lower()
            color = "green" if unc == "low" else "orange" if unc == "medium" else "red"
            
            # Create columns for uncertainty badge and evidence refs
            cols = st.columns(len(evidence) + 1)
            cols[0].markdown(f":{color}[Uncertainty: {unc.upper()}]")
            
            for j, ev in enumerate(evidence):
                nid = ev.get("note_id", "Unknown")
                support = ev.get("support_text", "No support text.")
                # Interactive Reference Button
                # Fix: Ensure uniqueness by including claim index (i) and evidence index (j)
                if cols[j+1].button(f"Ref {nid}", key=f"btn_{q_id}_c{i}_e{j}_{nid}", help=f"Note {nid}:\n{support}"):
                    st.session_state.active_inspector_note = nid
                    # BUG FIX: Use FULL Hash for lookup, not truncated display ID
                    st.session_state.active_inspector_query_hash = meta.get("query_id")
                    st.rerun()
    
    # 3. Cannot Conclude
    unknowns = findings.get("cannot_conclude", [])
    if unknowns:
        st.warning("⚠️ **Unresolved Questions**")
        for item in unknowns:
            q = item.get("question_part", "Unknown")
            r = item.get("reason", "Unknown")
            st.markdown(f"- **{q}**: {r}")

def get_note_details(note_id):
    """
    Fetches full details for a specific note ID from the database.
    Used for the Evidence Inspector to ensure ground truth.
    """
    try:
        con = get_db_connection()
        
        # Use simple single quoting like search_controversial_notes
        # Query updated to fetch ALL relevant forensic columns
        query = f"""
        SELECT 
            CAST(n.noteId AS VARCHAR) AS noteId,
            CAST(n.tweetId AS VARCHAR) AS tweetId,
            n.summary,
            CAST(n.createdAtMillis AS BIGINT) AS createdAtMillis,
            n.classification,
            n.believable,
            n.harmful,
            n.validationDifficulty,
            n.misleadingOther,
            n.misleadingFactualError,
            n.misleadingManipulatedMedia,
            n.misleadingOutdatedInformation,
            n.misleadingMissingImportantContext,
            n.misleadingUnverifiedClaimAsFact,
            n.misleadingSatire,
            n.notMisleadingOther,
            n.notMisleadingFactuallyCorrect,
            n.notMisleadingOutdatedButNotWhenWritten,
            n.notMisleadingClearlySatire,
            n.notMisleadingPersonalOpinion,
            n.trustworthySources,
            n.isMediaNote,
            s.currentStatus,
            CAST(s.timestampMillisOfCurrentStatus AS BIGINT) AS timestampMillisOfCurrentStatus
        FROM '{NOTES_DB_PATH}' AS n
        LEFT JOIN '{STATUS_DB_PATH}' AS s ON n.noteId = s.noteId
        WHERE CAST(n.noteId AS VARCHAR) = '{note_id}'
        LIMIT 1
        """
        
        df = con.execute(query).df()
        
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except Exception as e:
        print(f"Error fetching note details: {e}")
        return None

@st.dialog("Evidence Inspector")
def evidence_inspector_modal(nid):
    """
    Modal Dialog for Deep Inspection of a single evidence note.
    Forces focus and allows clean dismissal.
    Implements STRICT FORENSIC ALLOWLIST CHECK.
    """
    # 1. Forensic Access Control (Soft Check)
    q_hash = st.session_state.get("active_inspector_query_hash")
    
    # FETCH DATA FIRST (to check existence vs context)
    details = get_note_details(nid)
    
    is_context_verified = False
    
    # FETCH DATA FIRST (to check existence vs context)
    details = get_note_details(nid)
    
    is_context_verified = False
    
    if q_hash:
        # 1. Try Memory Code
        if q_hash in st.session_state.evidence_bundles:
            bundle = st.session_state.evidence_bundles[q_hash]
        # 2. Try Disk Persistence
        else:
             bundle = cm.load_bundle(q_hash)
             if bundle:
                 # Update memory cache
                 st.session_state.evidence_bundles[q_hash] = bundle
        
    if q_hash and bundle:
        # Fix: Bundle uses 'noteId' (CamelCase) from SQL query alias
        is_context_verified = any(str(item.get("noteId") or item.get("note_id")) == str(nid) for item in bundle)
    
    if is_context_verified:
        st.caption("✅ **Verified Context**: This note was present in the analysis source bundle.")
    elif details:
        # Note exists in DB, but wasn't in context
        st.warning("⚠️ **Verification Warning: Reference Not in Context**")
        st.caption(f"This note exists in the database but was NOT part of the top 50 evidence records provided to the model.")
        st.caption("The model retrieved this valid record from its internal training data (or extended memory), not the strict session context.")
    else:
        # Note does NOT exist in DB (True Hallucination)
        st.error("⛔ **Hallucinated Reference**")
        st.caption("This note ID does not exist in the database.")
        
        # Proceed to fetch data...

    # 2. Render Data (if exists)
    # details already fetched above
    
    if details:
        # --- AUDIT GRADE METADATA GRID ---
        # No truncation allowed. Use columns with explicit markup.
        
        # Row 1: Key Auditable Fields
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption("Created Date")
            st.markdown(f"**{pd.to_datetime(details.get('createdAtMillis', 0), unit='ms').strftime('%Y-%m-%d')}**")
        
        with c2:
            st.caption("Current Status")
            raw_status = details.get('currentStatus', 'Unknown')
            # Friendly label + Tooltip for raw value
            st.markdown(f"**{format_friendly_label(raw_status)}**", help=f"Raw Value: {raw_status}")
            
        with c3:
            st.caption("Classification")
            raw_class = details.get('classification', 'N/A')
            st.markdown(f"**{format_friendly_label(raw_class)}**", help=f"Raw Value: {raw_class}")
            
        st.divider()
        
        # Row 2: Note Summary (Expandable/Scrollable)
        st.caption("Note Content (Dataset Field)")
        summary_text = details.get('summary', 'No summary available.')
        
        # Use a container-like look for the summary
        with st.container(border=True):
             st.markdown(summary_text)
        
        # Row 3: Forensic IDs (Copyable)
        with st.expander("🔑 Forensic IDs & Audit Trail"):
             ic1, ic2 = st.columns(2)
             with ic1:
                 st.caption("Note ID")
                 st.code(str(nid), language="text")
                 st.caption("Tweet ID")
                 st.code(str(details.get('tweetId', 'N/A')), language="text")
             with ic2:
                 st.caption("Bundle Query Hash")
                 st.code(q_hash or "N/A", language="text")
                 st.caption("Participant ID")
                 st.code(str(details.get('noteAuthorParticipantId', 'N/A')), language="text")
        
        # Misleading Flags (Red Alerts)
        tags = []
        if details.get('misleadingFactualError'): tags.append("Factual Error")
        if details.get('misleadingManipulatedMedia'): tags.append("Manipulated Media")
        if details.get('misleadingOutdatedInformation'): tags.append("Outdated")
        if details.get('misleadingMissingImportantContext'): tags.append("Missing Context")
        if details.get('misleadingUnverifiedClaimAsFact'): tags.append("Unverified Claim")
        
        if tags:
            st.error(f"**Flags**: {', '.join(tags)}")
            
        st.divider()
        
        # 3. Raw Forensic Record
        with st.expander("📂 Raw Forensic Record (Full Row)", expanded=False):
            st.caption("This view displays the literal database row used for analysis. Null values are hidden from default view but present here.")
            # Convert milliseconds to readable datetime for display, but keep raw too?
            # Just dump details dict.
            st.json(details, expanded=True)
            
    else:
        st.error(f"Note {nid} not found in database.")

def run_chat_interface(keyword):
    """
    Cloud-Only Chat Interface for deep forensic analysis.
    Interact directly with Community Notes data via Grok/GPT-4.
    """
    # Active Inspector Check (Modal Trigger)
    if "active_inspector_note" in st.session_state and st.session_state.active_inspector_note:
        evidence_inspector_modal(st.session_state.active_inspector_note)
        # We rely on Streamlit dialog lifecycle.
        # If user closes dialog, they remain on page.
        # But active_inspector_note remains set?
        # If active_inspector_note is set, dialog opens on rerun.
        # If user closes dialog, typically Streamlit re-runs script?
        # If so, we need to clear this state or the dialog will pop open again?
        # Actually, @st.experimental_dialog handles this. It opens on call.
        # If user closes it, script might rerun?
        # Let's assume standard behavior: we just call it.
    
    st.header(f"🔎 Forensic Pattern Analysis: {keyword}")

    # --- 1. GATEKEEPER (Lock Screen) ---
    if 'cloud_api_key' not in st.session_state or not st.session_state['cloud_api_key']:
        st.warning("⚠️ CLOUD UPLINK REQUIRED")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image("https://cdn-icons-png.flaticon.com/512/3064/3064197.png", width=120)  # Generic Lock Icon
        with col2:
            st.markdown("""
            ### RESTRICTED AREA
            Deep Forensic Analysis requires **cloud neural processing**.
            Select a Provider and Model authorized for this security clearance.
            """)
            
            # --- MODEL SELECTOR ---
            
            # 1. Provider Selection
            provider = st.selectbox("Select Provider", list(UniversalCloudAdapter.PROVIDERS.keys()))
            
            # 2. Model Selection (Dynamic)
            model_options = UniversalCloudAdapter.MODEL_OPTIONS[provider]
            model_labels = list(model_options.keys())
            
            # Default Selection Logic
            default_index = 0
            if provider == "xAI":
                try:
                    default_index = model_labels.index("Grok 4.1 Fast (Standard)")
                except ValueError:
                    default_index = 0
            elif provider == "OpenAI":
                try:
                    default_index = model_labels.index("GPT-5.2 (Flagship)")
                except ValueError:
                    default_index = 0
            
            selected_model_label = st.selectbox("Select Model", model_labels, index=default_index)
            selected_model_id = model_options[selected_model_label]
            
            # Input API Key
            api_key = st.text_input("API Key", type="password", placeholder="sk-...")
            
            if st.button("🔓 AUTHORIZE UPLINK", type="primary"):
                if len(api_key) > 5: # Basic check
                    st.session_state['cloud_api_key'] = api_key
                    st.session_state['cloud_provider'] = provider
                    st.session_state['cloud_model_id'] = selected_model_id
                else:
                    st.error("Invalid API Key length.")
        # If we have history loaded, maybe we allow seeing it?
        # But 'return' stops rendering the chat blocks below.
        # Let's verify: The Chat blocks below start with 'Initialize Evidence Archive'.
        # If we return here, we won't see the chat.
        # FIX: Only return if we DON'T have history to show? 
        # Or simpler: Just return. The Sidebar handles selecting cases.
        # If the user wants to see the history, they must unlock?
        # No, the requirement is "Inaccessible".
        # If I want to see history without paying/unlocking, I should be able to.
        # So... we should ONLY return if (Not unlocked AND No history to show?)
        # For now, let's keep the return but at least the Sidebar is visible so they know cases exist.
        return # Stop rendering

    # Case Management moved to top.
    
    # Initialize Evidence Archive for Exports
    if "evidence_bundles" not in st.session_state:
        st.session_state.evidence_bundles = {}

    # Initialize Evidence Inspector State
    if "selected_evidence" not in st.session_state:
        st.session_state.selected_evidence = set()

    # Display Chat History
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            if msg.get("type") == "evidence_json":
                render_forensic_message(msg["content"])
            else:
                st.markdown(msg["content"])

    # Handle Input
    if prompt := st.chat_input(f"Interrogate data for '{keyword}'..."):
        # 1. User Message
        st.session_state.chat_messages.append({"role": "user", "content": prompt, "type": "text"})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Assistant Response
        with st.chat_message("assistant"):
            # RAG: Fetch Context
            notes_df = search_notes_by_keyword(keyword)
            # Filter again (redundant but safe)
            filtered_notes = notes_df[
                notes_df['summary'].str.contains(keyword, case=False, na=False) |
                notes_df['tweetId'].astype(str).str.contains(keyword, case=False, na=False) |
                notes_df['noteId'].astype(str).str.contains(keyword, case=False, na=False)
            ]
            
            # Start/End Date Mock
            start_date = "2024-01-01" 
            end_date = "2025-12-31"

            if filtered_notes.empty:
                # Handle Empty Result with Structured Report
                empty_meta = {
                    "query_meta": {
                        "query_id": hashlib.sha256(keyword.encode()).hexdigest(),
                        "retrieval_stats": {
                            "total_matches": 0, "sent_to_model": 0, "evidence_bundle_size": 0
                        },
                        "filters": {"time_range": {"start": start_date, "end": end_date}}
                    },
                    "dataset_findings": {
                        "claims": [], 
                        "cannot_conclude": [{"question_part": keyword, "reason": "No evidence found in database."}]
                    }
                }
                render_forensic_message(empty_meta)
                st.session_state.chat_messages.append({"role": "assistant", "content": empty_meta, "type": "evidence_json"})
                return

            # Prepare Payload (Top 50 recent)
            # Use deterministic sorting for reproducibility (Time + NoteID tiebreaker)
            context_notes = filtered_notes.sort_values(['createdAtMillis', 'noteId'], ascending=[False, True]).head(50)
            context_payload = context_notes.to_dict(orient='records')
            
            # Canonical Hash: Hashing the SORTED tuple of NoteIDs + Query
            note_ids = sorted([str(n['noteId']) for n in context_payload])
            canonical_str = f"{prompt}|{','.join(note_ids)}"
            query_id_hash = hashlib.sha256(canonical_str.encode()).hexdigest()
            
            # Archive Evidence Bundle (Memory + Disk Persistence)
            st.session_state.evidence_bundles[query_id_hash] = context_payload
            try:
                cm.save_bundle(query_id_hash, context_payload)
            except Exception as e:
                print(f"[Dashboard] Error persisting bundle: {e}")

            # DEBUG: Log Retrieval Context
            print(f"[Dashboard] Query: '{keyword}'")
            print(f"[Dashboard] Total Matches: {len(filtered_notes)}")
            print(f"[Dashboard] Bundle Sent: {len(context_payload)}")
            print(f"[Dashboard] Query Hash: {query_id_hash[:8]}")
            
            client = UniversalCloudAdapter(st.session_state['cloud_provider'], st.session_state['cloud_api_key'])
            
            try:
                # Add Metadata to Context for Model Awareness
                query_meta_obj = {
                        "query_id": query_id_hash,
                        "retrieval_stats": {
                            "total_matches": len(filtered_notes),
                            "sent_to_model": len(context_payload),
                            "evidence_bundle_size": len(context_payload),
                            "evidence_bundle_id": hashlib.sha256(",".join(note_ids).encode()).hexdigest()
                        },
                        "filters": {
                            "time_range": {"start": start_date, "end": end_date}
                        }
                    }
                
                meta_context = {
                    "query_meta": query_meta_obj,
                    "notes": context_payload
                }

                gen = client.generate_forensic_report_v2(
                    get_investigator_system_prompt(),
                    meta_context, # Pass metadata wrapper
                    prompt,
                    model_id=st.session_state.get('cloud_model_id')
                )
                
                # Stream Loop
                status_placeholder = st.empty()
                final_json = None
                
                for chunk in gen:
                    if isinstance(chunk, dict):
                        final_json = chunk
                        status_placeholder.empty() # Clear status
                    else:
                        status_placeholder.markdown(chunk)
                
                if final_json:
                    # INJECT METADATA
                    final_json["query_meta"] = query_meta_obj
                    render_forensic_message(final_json)
                    st.session_state.chat_messages.append({"role": "assistant", "content": final_json, "type": "evidence_json"})
                    
                    # PERSIST TURN (Atomic Save with Lazy Case Creation)
                    try:
                        # Lazy case creation: create case if in draft mode or no active case
                        if st.session_state.get("draft_case_mode") or not st.session_state.get("active_case_id"):
                            new_case_id = cm.create_case(f"Investigation {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
                            st.session_state.active_case_id = new_case_id
                            st.session_state.draft_case_mode = False  # Exit draft mode
                            print(f"[Dashboard] LAZY CREATE: Case {new_case_id[:8]} created on first turn (was draft)", file=sys.stderr)
                        else:
                            print(f"[Dashboard] APPEND: Adding turn to existing case {st.session_state.active_case_id[:8]}", file=sys.stderr)
                        
                        turn_payload = {
                            "user_query": prompt,
                            "assistant_response": final_json,
                            "query_meta": query_meta_obj
                        }
                        cm.save_turn(st.session_state.active_case_id, turn_payload)
                    except Exception as e:
                        st.error(f"Failed to save case history: {e}")
                
            except Exception as e:
                st.error(f"Analysis Failed: {e}")



# --- Main App ---
def main():
    st.title("Community Notes Analytics")
    st.markdown("### Historical data analysis and insights from X Community Notes")
    
    # Custom CSS for button styling and header removal
    st.markdown("""
    <style>
        /* Override primary button color */
        button[kind="primaryFormSubmit"],
        button[data-testid="stBaseButton-primaryFormSubmit"] {
            background-color: #1DA1F2 !important;
            border-color: #1DA1F2 !important;
            color: white !important;
        }
        button[kind="primaryFormSubmit"]:hover,
        button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
            background-color: #1a8cd8 !important;
            border-color: #1a8cd8 !important;
        }
        
        /* Hide Streamlit header/toolbar */
        header[data-testid="stHeader"],
        .stAppHeader,
        .stAppToolbar,
        [data-testid="stToolbar"] {
            display: none !important;
            visibility: hidden !important;
        }
        #MainMenu, footer {
            visibility: hidden !important;
        }
        
        /* --- ALIGNMENT FIX (CSS ONLY) --- */
        
        /* --- ALIGNMENT FIX (CSS ONLY) --- */
        
        /* 1. Force Horizontal Block to stretch columns */
        [data-testid="stHorizontalBlock"] {
            align-items: stretch !important;
            height: auto !important;
            min-height: 100% !important; 
        }

        /* 2. Force Columns to be Flex Containers and take full height */
        [data-testid="column"] {
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important; /* Forces column to fill the horizontal block */
            min-height: 1px !important; /* Fix for flex child height calculations */
        }
        
        /* 3. Force the inner Vertical Block to also take full height */
        /* Streamlit wraps content in a stVerticalBlock inside the column */
        [data-testid="column"] > div[data-testid="stVerticalBlock"] {
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
            min-height: 100% !important;
            flex-grow: 1 !important;
            justify-content: flex-start !important; /* Stack normally */
        }
        
        /* 4. Target the Insight Component (iframe container) and push it to bottom */
        /* We select the last element-container in the vertical block */
        [data-testid="column"] > div[data-testid="stVerticalBlock"] > div.element-container:last-child {
            margin-top: auto !important;
            padding-bottom: 0px !important;
            flex-grow: 0 !important; /* Don't stretch the button container itself */
        }
        
        /* Adjust iframe margin to be flush */
        iframe {
            display: block !important; /* Removes inline spacing */
        }

    </style>
    """, unsafe_allow_html=True)
    
    # Initialize Session State
    if 'active_keyword' not in st.session_state:
        st.session_state['active_keyword'] = None
    if 'webllm_context' not in st.session_state:
        st.session_state['webllm_context'] = "{}"

    # --- CASE MANAGEMENT BAR (Main Content - Always Visible) ---
    # Rendered in main area, NOT sidebar, to guarantee visibility
    with st.container():
        st.markdown("##### 🗂️ Active Investigation")
        existing_cases = cm.list_cases()
        
        # Check if we're in draft mode (unsaved new investigation)
        is_draft_mode = st.session_state.get("draft_case_mode", False)
        
        # Format Case Options with Metadata (Name • Turns • Time)
        case_options = {}
        
        # Add draft option first if in draft mode
        if is_draft_mode:
            case_options["__draft__"] = "📝 New Investigation (draft)"
        
        # Add existing saved cases
        if existing_cases:
            for c in existing_cases:
                updated_ts = pd.Timestamp(c['updated_at'])
                now = pd.Timestamp.now()
                time_str = updated_ts.strftime('%H:%M') if updated_ts.date() == now.date() else updated_ts.strftime('%Y-%m-%d')
                turn_count = c.get('turn_count', 0)
                label = f"{c['name']} ({turn_count} turns • {time_str})"
                case_options[c['case_id']] = label
        
        # Layout: SelectBox (main) + New (+) Button
        col_case, col_new = st.columns([0.9, 0.1])
        
        with col_case:
            # Determine current selection index
            current_index = 0
            if is_draft_mode:
                current_index = 0  # Draft is first option
            elif "active_case_id" in st.session_state and existing_cases:
                option_keys = list(case_options.keys())
                for idx, key in enumerate(option_keys):
                    if key == st.session_state.active_case_id:
                        current_index = idx
                        break
            
            # Only show selectbox if we have options
            if case_options:
                selected_case_id = st.selectbox(
                    "Select Case",
                    options=list(case_options.keys()),
                    format_func=lambda x: case_options.get(x, x),
                    index=current_index,
                    key="main_case_selector",
                    label_visibility="collapsed"
                )
            else:
                selected_case_id = None
                st.caption("No active investigation")

        with col_new:
            if st.button("➕", help="Create New Investigation", key="btn_new_case"):
                # Enter draft mode (don't persist yet)
                st.session_state.draft_case_mode = True
                st.session_state.active_case_id = None  # Clear to indicate draft
                st.session_state['active_keyword'] = None
                st.session_state.chat_messages = []  # Clear chat for new investigation
                st.rerun()

        # Handle Empty State (no cases AND not in draft)
        if not existing_cases and not is_draft_mode:
            st.info("No active investigation. Click ➕ or search a topic to begin.")
        
        # Context Switch Trigger
        if selected_case_id:
            if selected_case_id == "__draft__":
                # Staying in draft mode, ensure state is correct
                if not is_draft_mode:
                    st.session_state.draft_case_mode = True
                    st.session_state.active_case_id = None
                    st.rerun()
            elif selected_case_id != st.session_state.get("active_case_id"):
                # Switching to a saved case
                st.session_state.active_case_id = selected_case_id
                st.session_state.draft_case_mode = False  # Exit draft mode
                st.rerun()

        st.divider()  # Visual separator before search




    # Auto-select most recent case on startup (if not in draft and no active case)
    if "active_case_id" not in st.session_state and existing_cases and not is_draft_mode:
         st.session_state.active_case_id = existing_cases[0]['case_id']

    # --- DERIVED STATE: Rebuild Chat View from Case Data ---
    # This pattern ensures the UI always reflects the persisted case,
    # avoiding session state "wipe hacks" that cause data loss.
    def _build_chat_messages_from_case(case_id):
        """Compute chat messages from case data (derived state)."""
        messages = []
        if not case_id:
            return messages
        
        case_data = cm.load_case(case_id)
        if not case_data:
            return messages
        
        # Initial Greeting
        topic_str = st.session_state.get('active_keyword') or case_data.get("name") or "this investigation"
        messages.append({
            "role": "assistant",
            "content": f"**Forensic Link Active.**\n\nI have access to the Community Notes (corrections) dataset for **'{topic_str}'**.\n\nAsk me about **common misinformation patterns**, common correction themes, or specific claims.\n\n*Note: This data reflects dispute contexts, not general public sentiment.*",
            "type": "text"
        })
        
        # Rehydrate from Turns
        for turn in case_data.get("turns", []):
            messages.append({
                "role": "user", 
                "content": turn.get("user_query"), 
                "type": "text"
            })
            messages.append({
                "role": "assistant", 
                "content": turn.get("assistant_response"), 
                "type": "evidence_json"
            })
        
        return messages
    
    # Always rebuild from source of truth (disk)
    st.session_state.chat_messages = _build_chat_messages_from_case(
        st.session_state.get("active_case_id")
    )
    
    # ACTIVATION BRIDGE: If case has history, bypass search wall
    if st.session_state.chat_messages and not st.session_state.get('active_keyword'):
        if len(st.session_state.chat_messages) > 1:  # More than just greeting
            st.session_state['active_keyword'] = "Resume Investigation"
            st.rerun()  # Trigger immediate render of chat interface


    # Main Input (Search)
    with st.form(key='search_form'):
        col1, col2 = st.columns([4, 1])
        with col1:
            keyword_input = st.text_input("Search Topic (e.g. 'Elon Musk', 'Tesla')", placeholder="Enter topic or keyword to analyze...")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button(label="Generate Report", type="primary", use_container_width=True)

    # 1. Handle Form Submission
    if submit_button:
        if keyword_input:
            st.session_state['active_keyword'] = keyword_input
            # Reset context on new search to avoid stale data (but keep chat history)
            st.session_state['webllm_context'] = "{}" 
            # UX: Data Continuity - Do NOT wipe history. Append new query result to existing case.
            # st.session_state['chat_messages'] = [] 
            st.rerun()
        else:
            st.warning("⚠️ Please enter a topic to begin the analysis.")


    # 2. Render Main Dashboard (Persistent)
    if st.session_state['active_keyword']:
        keyword = st.session_state['active_keyword']
        
        # Smart Navigation (Stateful)
        if 'active_view' not in st.session_state:
            st.session_state['active_view'] = "💬 Chat with Data"
            
        view = st.radio(
            "Navigation", 
            ["💬 Chat with Data", "📊 Analytics Report", "🔥 Controversy Monitor", "🏆 The Winning Formula"],
            horizontal=True,
            key='active_view',
            label_visibility="collapsed"
        )
        st.markdown("---")
        
        # Router Logic
        if view == "💬 Chat with Data":
            run_chat_interface(keyword)
        elif view == "📊 Analytics Report":
            run_intelligence_report(keyword)
        elif view == "🔥 Controversy Monitor":
            run_controversy_monitor(keyword)
        elif view == "🏆 The Winning Formula":
            run_winning_formula(keyword)

    # --- END OF DASHBOARD ---
    
if __name__ == "__main__":
    main()
