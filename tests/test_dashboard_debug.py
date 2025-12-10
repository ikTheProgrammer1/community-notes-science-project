import pytest
import pandas as pd
import duckdb
import os
import tempfile
from dashboard import search_notes_by_keyword

# Fixtures for Data Paths
@pytest.fixture
def mock_data_files(tmp_path):
    """Create temporary mock TSV files for testing."""
    notes_path = tmp_path / "notes-00000.tsv"
    status_path = tmp_path / "noteStatusHistory-00000.tsv"
    ratings_path = tmp_path / "ratings-00000.tsv"
    
    # 1. Notes (Include headers as exact strings to avoid type issues)
    df_notes = pd.DataFrame({
        'noteId': ['100', '101', '102', '103'],
        'tweetId': ['t_attack_1', 't_attack_2', 't_attack_3', 't_contro'],
        'classification': ['MISINFORMED_OR_POTENTIALLY_MISLEADING', 'MISINFORMED_OR_POTENTIALLY_MISLEADING', 'NOT_MISLEADING', 'MISINFORMED_OR_POTENTIALLY_MISLEADING'],
        'summary': ['Fake news about Tesla', 'Another fake Tesla story', 'Actually true', 'Controversial Tesla Debate'],
        'trustworthySources': ['http://good.com', 'http://news.com', '', ''],
        'createdAtMillis': [1600000000000, 1600000000000, 1600000000000, 1600000000000],
        'misleadingFactualError': [1, 0, 0, 0],
        'misleadingManipulatedMedia': [0, 1, 0, 0],
        'misleadingOutdatedInformation': [0, 0, 0, 0],
        'misleadingMissingImportantContext': [0, 0, 0, 0],
        'misleadingUnverifiedClaimAsFact': [0, 0, 0, 0],
        'noteAuthorParticipantId': ['auth_1', 'auth_1', 'auth_2', 'auth_3']
    })
    df_notes.to_csv(notes_path, sep='\t', index=False)
    
    # 2. Status (Include NEEDS_MORE_RATINGS for controversy test)
    df_status = pd.DataFrame({
        'noteId': ['100', '101', '102', '103'],
        'currentStatus': ['CURRENTLY_RATED_HELPFUL', 'NOTE_NOT_NEEDED', 'NEEDS_MORE_RATINGS', 'NEEDS_MORE_RATINGS'],
        'timestampMillisOfCurrentStatus': [1600003600000, 1600000000000, 1600000000000, 1600000000000],
        'timestampMillisOfFirstNonNMRStatus': [1600003600000, 1600000000000, 1600000000000, 1600000000000]
    })
    df_status.to_csv(status_path, sep='\t', index=False)
    
    # 3. Ratings (Mock counts)
    # Note 103 has 5 ratings, Note 102 has 2 ratings
    df_ratings = pd.DataFrame({
        'noteId': ['103']*5 + ['102']*2,
        'rating': [1]*7,
        'notHelpfulArgumentativeOrBiased': [1, 0, 1, 0, 0, 0, 0],
        'notHelpfulOpinionSpeculationOrBias': [0, 1, 0, 0, 0, 0, 0],
        'notHelpfulSourcesMissingOrUnreliable': [0, 0, 0, 1, 1, 0, 0]
    })
    df_ratings.to_csv(ratings_path, sep='\t', index=False)
    
    yield str(notes_path), str(status_path), str(ratings_path)

def test_calculate_coordination():
    """Test Astroturf meter logic."""
    from dashboard import calculate_coordination
    
    # Mock DF with author IDs
    # 10 notes.
    # Auth A: 6 notes (Top 10%)
    # Auth B: 1 note
    # Auth C: 1 note
    # ...
    authors = ['A']*6 + ['B', 'C', 'D', 'E']
    df = pd.DataFrame({'noteAuthorParticipantId': authors})
    
    metrics = calculate_coordination(df)
    
    assert metrics is not None
    assert metrics['total_authors'] == 5 # A, B, C, D, E
    
    # Top 1% of 5 authors = max(1, 0.05) = 1 author (Auth A)
    # Auth A wrote 6 notes out of 10.
    # Share = 0.6
    assert metrics['top_1_percent_share'] == 0.6
    
    # Repeat offenders: Authors with > 1 note. Only A (6).
    assert metrics['repeat_offenders'] == 1

def test_generate_crisis_heatmap():
    """Test Heatmap logic (Day/Hour extraction)."""
    from dashboard import generate_crisis_heatmap
    import altair as alt
    
    # Mock DF with timestamps
    # 2020-09-13 14:00:00 UTC is a Sunday
    ts_sunday_14 = 1600005600000 
    
    df = pd.DataFrame({
        'createdAtMillis': [ts_sunday_14, ts_sunday_14]
    })
    
    chart = generate_crisis_heatmap(df)
    
    assert chart is not None
    assert isinstance(chart, alt.Chart)
    
    # Verify data inside the chart
    data = chart.data
    assert not data.empty
    assert 'Day' in data.columns
    assert 'Hour' in data.columns
    
    row = data.iloc[0]
    assert row['Day'] == 'Sunday'
    assert row['Hour'] == 14
    assert row['Count'] == 2

def test_search_controversial_notes(mock_data_files, monkeypatch):
    """Test controversy monitor ranking and metrics."""
    notes_path, status_path, ratings_path = mock_data_files
    
    import dashboard
    monkeypatch.setattr(dashboard, 'NOTES_DB_PATH', notes_path)
    monkeypatch.setattr(dashboard, 'STATUS_DB_PATH', status_path)
    monkeypatch.setattr(dashboard, 'RATINGS_DB_PATH', ratings_path)
    
    from dashboard import search_controversial_notes
    
    df = search_controversial_notes("Tesla")
    
    assert not df.empty
    assert len(df) == 1
    row = df.iloc[0]
    assert str(row['noteId']) == '103'
    assert row['currentStatus'] == 'NEEDS_MORE_RATINGS'
    assert row['rating_count'] == 5 
    
    # New Metrics Checks
    # 1. Stalemate Analysis sums
    # id 103 has 5 ratings. 
    # indices in mock: 0,1,2,3,4.
    # Arg: 1+0+1+0+0 = 2
    # Opn: 0+1+0+0+0 = 1
    # Src: 0+0+0+1+1 = 2
    assert row['count_argumentative'] == 2
    assert row['count_opinion'] == 1
    assert row['count_missing_sources'] == 2
    
    # 2. Velocity
    # Duration = status - created = 0
    # Logic sets min duration to 1 hour (1/24 days).
    # Velocity = 5 / (1/24) = 120.0 ratings/day
    assert row['velocity'] == 120.0

def test_cluster_narratives(mock_data_files):
    """Test clustering logic with synthesized data."""
    # Need > 50 notes to trigger clustering
    from dashboard import cluster_narratives
    import pandas as pd
    
    # Create 60 notes with distinct themes and noise
    themes = (
        ["crypto scam http://bad.com"] * 20 + 
        ["election &quot;fraud&quot;"] * 20 + 
        ["vaccine chip https://fake.news/1"] * 20
    )
    df = pd.DataFrame({'summary': themes})
    
    clusters = cluster_narratives(df, n_clusters=3)
    assert clusters is not None
    assert len(clusters) == 3
    
    # Check if themes are clean (no http, no &quot;)
    # We can check the first theme label
    for c in clusters:
        assert 'http' not in c['theme']
        assert 'quot' not in c['theme']
    
def test_cluster_narratives_small_data():
    """Test clustering fallback for small data."""
    from dashboard import cluster_narratives
    import pandas as pd
    df = pd.DataFrame({'summary': ["test"] * 10})
    assert cluster_narratives(df) is None

def test_search_notes_by_keyword(mock_data_files, monkeypatch):
    """Test offline keyword search logic."""
    notes_path, status_path, _ = mock_data_files
    
    # Monkeypatch the module-level constants
    import dashboard
    monkeypatch.setattr(dashboard, 'NOTES_DB_PATH', notes_path)
    monkeypatch.setattr(dashboard, 'STATUS_DB_PATH', status_path)
    
    # Case 1: Search for 'Fake' (Should match 'Fake news' in summary)
    df = dashboard.search_notes_by_keyword('Fake')
    assert len(df) == 1
    assert df.iloc[0]['tweetId'] == 't_attack_1'
    
    # Case 2: Search for 'true' (Should NOT match match 'Actually true' because it is NOT MISLEADING)
    df_clean = dashboard.search_notes_by_keyword('true')
    assert len(df_clean) == 0
    
    # Case 3: Search for 'Biased' (Should NOT match because status is NEEDS_MORE_RATINGS)
    df_status_fail = dashboard.search_notes_by_keyword('Biased')
    assert len(df_status_fail) == 0
    
    # Case 4: Search for something not there
    df_empty = dashboard.search_notes_by_keyword('Unicorn')
    assert len(df_empty) == 0
