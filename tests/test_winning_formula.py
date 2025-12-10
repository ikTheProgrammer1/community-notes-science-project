
import pandas as pd
import pytest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard import analyze_success_drivers

def test_analyze_success_drivers():
    # Mock Data
    data = {
        'currentStatus': [
            'CURRENTLY_RATED_HELPFUL', 'CURRENTLY_RATED_HELPFUL', 'CURRENTLY_RATED_HELPFUL', # 3 Wins
            'CURRENTLY_RATED_NOT_HELPFUL', 'CURRENTLY_RATED_NOT_HELPFUL', # 2 Losses
            'CURRENTLY_RATED_HELPFUL', 'CURRENTLY_RATED_NOT_HELPFUL', # Mixed
            'CURRENTLY_RATED_HELPFUL', 'CURRENTLY_RATED_HELPFUL', # More Wins
            'CURRENTLY_RATED_NOT_HELPFUL' # Loss
        ],
        # Total: 10 notes. 6 Wins (60%).
        
        'summary': [
            'This is a neutral statement.', 'Good facts.', 'Neutral tone here.',
            'I hate this!', 'This is bad!',
            'Neutral.', 'Worst ever.', 
            'Neutral again.', 'Neutral.',
            'Bad.'
        ],
        'trustworthySources': [
            'https://www.google.com', 'https://www.cdc.gov/report.pdf', 'http://example.edu',
            'http://youtube.com', 'http://twitter.com',
            'http://google.com', 'http://youtube.com',
            'http://google.com', 'http://google.com',
            'http://youtube.com'
        ]
    }
    
    # Needs > 5 count per group to show up in insights
    # Let's ensure we have enough data points for groups
    # Replicate data 3 times to hit thresholds
    df = pd.DataFrame(data)
    df = pd.concat([df, df, df], ignore_index=True) # 30 rows
    
    # Run Analysis
    result = analyze_success_drivers(df)
    
    assert result is not None
    assert 'baseline' in result
    assert 'data' in result
    
    # Baseline check (6 wins out of 10) -> 0.6
    assert result['baseline'] == 0.6
    
    drivers = result['data']
    
    # Check Categories exist
    categories = drivers['Category'].unique()
    assert 'sentiment' in categories
    assert 'src_type' in categories
    
    # Check specific logic
    # "Neutral Tone" should have high win rate (from mock data)
    neutral_row = drivers[drivers['Attribute'] == 'Neutral Tone']
    if not neutral_row.empty:
        # Neutral notes in mock are mostly helpful
        assert neutral_row.iloc[0]['Win_Rate'] > 0.5
        
    print("Winning Formula Analysis Test Passed")

if __name__ == "__main__":
    test_analyze_success_drivers()
