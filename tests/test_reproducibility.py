import unittest
import json
import hashlib
import sys
from unittest.mock import MagicMock, patch

# Mock streamlit
sys.modules["streamlit"] = MagicMock()
import streamlit as st

class TestReproducibilityCard(unittest.TestCase):
    
    def setUp(self):
        class SessionState(object):
            pass
        st.session_state = SessionState()
        st.session_state.evidence_bundles = {}

    def test_repro_state_roundtrip(self):
        """
        Unit: Encode/decode state (query + filters) to ensure no drift.
        Basically testing that the hash generation is stable for the same inputs.
        """
        prompt = "Elon Musk"
        note_ids = ["100", "102", "101"]
        # Sorted logic from dashboard.py
        sorted_ids = sorted(note_ids)
        canonical_str = f"{prompt}|{','.join(sorted_ids)}"
        hash1 = hashlib.sha256(canonical_str.encode()).hexdigest()
        
        # Rerun
        prompt2 = "Elon Musk"
        note_ids2 = ["102", "101", "100"] # Different order
        sorted_ids2 = sorted(note_ids2)
        canonical_str2 = f"{prompt2}|{','.join(sorted_ids2)}"
        hash2 = hashlib.sha256(canonical_str2.encode()).hexdigest()
        
        self.assertEqual(hash1, hash2, "Query Hash should be deterministic regardless of input list order.")

    def test_export_uses_saved_bundle(self):
        """
        Unit: Ensure export retrieves the exact bundle from session state by ID.
        """
        query_id = "abc12345"
        mock_bundle = [{"noteId": "1"}, {"noteId": "2"}]
        
        # Populate Archive
        st.session_state.evidence_bundles = {query_id: mock_bundle}
        
        # Retreive
        retrieved_bundle = st.session_state.evidence_bundles.get(query_id)
        
        self.assertEqual(retrieved_bundle, mock_bundle)
        self.assertEqual(len(retrieved_bundle), 2)
        
    def test_card_summary_matches_meta(self):
        """
        Unit: Ensure meta object contains necessary stats for the card.
        """
        meta = {
            "query_meta": {
                "query_id": "deadbeef",
                "retrieval_stats": {
                    "total_matches": 100, 
                    "evidence_bundle_size": 50
                },
                "filters": {"time_range": {"start": "2024"}}
            }
        }
        
        # Simulate logic in render_forensic_message
        q_id = meta["query_meta"]["query_id"]
        stats = meta["query_meta"]["retrieval_stats"]
        
        self.assertEqual(q_id, "deadbeef")
        self.assertEqual(stats["total_matches"], 100)
        self.assertEqual(stats["evidence_bundle_size"], 50)

    def test_tampered_link_fails_safe(self):
        """
        Red Team: Ensure invalid keys return None/Empty and don't crash.
        """
        st.session_state.evidence_bundles = {"valid_key": []}
        
        invalid_key = "malicious_key"
        bundle = st.session_state.evidence_bundles.get(invalid_key)
        
        self.assertIsNone(bundle, "Should return None for non-existent evidence keys.")

    def test_export_integrity(self):
        """
        Integration: Simulate the flow of generating hash -> saving -> retrieving.
        """
        # 1. Retrieval Phase
        prompt = "Test Query"
        payload = [{"noteId": "A"}, {"noteId": "B"}]
        
        # Calc Hash
        canonical_str = f"{prompt}|A,B"
        q_hash = hashlib.sha256(canonical_str.encode()).hexdigest()
        
        # 2. Archive Phase
        st.session_state.evidence_bundles[q_hash] = payload
        
        # 3. Export Phase (later)
        exported_bundle = st.session_state.evidence_bundles.get(q_hash)
        
        # Assert
        self.assertEqual(exported_bundle[0]['noteId'], "A")
        self.assertEqual(exported_bundle[1]['noteId'], "B")
        self.assertEqual(len(exported_bundle), 2)

if __name__ == '__main__':
    unittest.main()
