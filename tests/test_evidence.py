import unittest
import json
import sys
from unittest.mock import MagicMock

# Mock streamlit before import to avoid dependency issues
sys.modules["streamlit"] = MagicMock()

from cloud_intel import UniversalCloudAdapter

class TestEvidenceContract(unittest.TestCase):
    
    def setUp(self):
        # Bypass __init__ logic requiring API keys
        self.adapter = UniversalCloudAdapter.__new__(UniversalCloudAdapter)
        self.adapter.config = {} 

    def test_schema_valid_happy_path(self):
        """Test a perfectly valid JSON response."""
        valid_ids = {"101", "102"}
        payload = {
            "query_meta": {},
            "dataset_findings": {
                "claims": [
                    {
                        "claim_text": "Valid Claim",
                        "evidence": [
                            {"note_id": "101", "support_text": "Confirmed."}
                        ],
                        "uncertainty": "low"
                    }
                ]
            }
        }
        is_valid, _, err = self.adapter.validate_and_repair_json(json.dumps(payload), valid_ids)
        self.assertTrue(is_valid, f"Should be valid: {err}")

    def test_hallucinated_id_rejection(self):
        """Test rejection of IDs not in the evidence bundle."""
        valid_ids = {"101"}
        payload = {
            "dataset_findings": {
                "claims": [
                    {
                        "claim_text": "Hallucination",
                        "evidence": [
                            {"note_id": "999", "support_text": "Fake"} # 999 missing
                        ],
                        "uncertainty": "high"
                    }
                ]
            }
        }
        is_valid, _, err = self.adapter.validate_and_repair_json(json.dumps(payload), valid_ids)
        self.assertFalse(is_valid)
        self.assertIn("does not exist", err)

    def test_uncertainty_enum_strictness(self):
        """Test that uncertainty must be low/medium/high."""
        valid_ids = {"101"}
        payload = {
            "dataset_findings": {
                "claims": [
                    {
                        "claim_text": "Fuzzy",
                        "evidence": [{"note_id": "101", "support_text": "ok"}],
                        "uncertainty": "maybe" # Invalid
                    }
                ]
            }
        }
        is_valid, _, err = self.adapter.validate_and_repair_json(json.dumps(payload), valid_ids)
        self.assertFalse(is_valid)
        self.assertIn("Uncertainty", err)

    def test_markdown_stripping(self):
        """Test that we correctly strip markdown code blocks from the LLM."""
        valid_ids = {"101"}
        raw_llm_output = """
        Here is the JSON:
        ```json
        {
            "dataset_findings": {
                "claims": []
            }
        }
        ```
        """
        is_valid, _, err = self.adapter.validate_and_repair_json(raw_llm_output, valid_ids)
        self.assertTrue(is_valid, f"Should strip markdown: {err}")

if __name__ == '__main__':
    unittest.main()
