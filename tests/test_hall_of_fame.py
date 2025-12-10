
import pandas as pd
import pytest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard import fetch_hall_of_fame

def test_hall_of_fame_final_polish():
    # Verify imports for polish features
    try:
        from urllib.parse import urlparse
        import re
        from difflib import SequenceMatcher
    except ImportError:
        pytest.fail("Missing dependencies for polish features")

    # Resilience check
    try:
        df = fetch_hall_of_fame("Test")
        # Just ensure it doesn't crash with the new language filter logic inside
        assert isinstance(df, pd.DataFrame)
    except Exception as e:
        pytest.fail(f"Crashed with error: {e}")

if __name__ == "__main__":
    test_hall_of_fame_final_polish()
