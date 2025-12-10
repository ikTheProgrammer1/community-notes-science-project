
import pandas as pd
import altair as alt
import altair as alt
import pytest
import sys
import os

# Add parent directory to path to import dashboard.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard import generate_narrative_lifecycle

def test_generate_narrative_lifecycle():
    # Mock Data
    # Theme A: 2 notes in Week 1, 1 note in Week 2
    # Theme B: 1 note in Week 1, 3 notes in Week 2
    
    # Week 1: 2 Jan 2023 (Monday) -> 1672617600000 ms
    # Week 2: 9 Jan 2023 (Monday) -> 1673222400000 ms
    
    df_a = pd.DataFrame({
        'createdAtMillis': [1672617600000, 1672617600000, 1673222400000],
        'summary': ['A1', 'A2', 'A3']
    })
    
    df_b = pd.DataFrame({
        'createdAtMillis': [1672617600000, 1673222400000, 1673222400000, 1673222400000],
        'summary': ['B1', 'B2', 'B3', 'B4']
    })
    
    themes = [
        {'id': 0, 'theme': 'Theme A', 'count': 3, 'notes': df_a},
        {'id': 1, 'theme': 'Theme B', 'count': 4, 'notes': df_b}
    ]
    
    chart = generate_narrative_lifecycle(themes)
    
    assert chart is not None
    assert isinstance(chart, alt.Chart)
    
    # Check underlying data
    chart_json = chart.to_dict()
    # Deep check is hard with Altair dict structure, but we can check if it ran without error
    # and produced a chart object.
    
    print("Chart generated successfully")

def test_generate_narrative_lifecycle_empty():
    chart = generate_narrative_lifecycle([])
    assert chart is None

if __name__ == "__main__":
    test_generate_narrative_lifecycle()
    test_generate_narrative_lifecycle_empty()
