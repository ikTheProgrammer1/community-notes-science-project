
import pandas as pd
import pytest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard import generate_narrative_lifecycle

def test_lifecycle_filtering():
    # Helper to create timestamps
    def make_ts(year, month, day):
        return pd.Timestamp(f'{year}-{month}-{day}').value // 10**6 # to millis
    
    # 1. Old Data (2021) -> Should be filtered out
    ts_old = make_ts(2021, 6, 1)
    
    # 2. Valid Data (2023) -> Should be kept
    ts_valid = make_ts(2023, 6, 1)
    
    # 3. Future Data (2099) -> Should be filtered out
    ts_future = make_ts(2099, 1, 1)
    
    df = pd.DataFrame({
        'createdAtMillis': [ts_old, ts_valid, ts_future],
        'summary': ['Old', 'Valid', 'Future']
    })
    
    themes = [
        {'id': 0, 'theme': 'Test Theme', 'count': 3, 'notes': df}
    ]
    
    # Run function
    chart = generate_narrative_lifecycle(themes)
    
    # Since we have valid data, chart should exist
    assert chart is not None
    
    # However, we can't easily inspect the Altair chart object data property in a simple unit test 
    # without diving into `chart.data` which might be the dataframe or a dict.
    # In generate_narrative_lifecycle, we pass `full_df` to alt.Chart(full_df).
    # So `chart.data` should be equal to the filtered DataFrame.
    
    filtered_df = chart.data
    
    # Check that Old and Future are gone
    # filtered_df should only have the entry corresponding to ts_valid
    # Note: The function groups by week and counts.
    
    assert len(filtered_df) == 1
    assert filtered_df.iloc[0]['Count'] == 1
    # Check the date of the remaining item
    # Since we grouped by W-MON, the date will be the Monday of that week.
    # June 1 2023 is a Thursday. Monday was May 29.
    # Let's just check it's close to 2023.
    assert filtered_df.iloc[0]['date'].year == 2023

def test_lifecycle_filtering_all_removed():
    # Only old and future data
    def make_ts(year, month, day):
        return pd.Timestamp(f'{year}-{month}-{day}').value // 10**6
        
    df = pd.DataFrame({
        'createdAtMillis': [make_ts(2021, 1, 1), make_ts(2099, 1, 1)],
        'summary': ['Old', 'Future']
    })
    
    themes = [{'id': 0, 'theme': 'Test', 'count': 2, 'notes': df}]
    
    chart = generate_narrative_lifecycle(themes)
    assert chart is None

if __name__ == "__main__":
    test_lifecycle_filtering()
    test_lifecycle_filtering_all_removed()
    print("Filtering tests passed")
