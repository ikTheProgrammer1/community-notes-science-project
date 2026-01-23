import json
import os
import uuid
import shutil
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any

# Directories
ARTIFACTS_DIR = "artifacts"
CASES_DIR = os.path.join(ARTIFACTS_DIR, "cases")
BUNDLES_DIR = os.path.join(ARTIFACTS_DIR, "bundles")

class CaseManager:
    """
    Manages persistence for Forensic Cases and Evidence Bundles.
    Enforces atomic writes and strict schema separation.
    """
    
    def __init__(self):
        os.makedirs(CASES_DIR, exist_ok=True)
        os.makedirs(BUNDLES_DIR, exist_ok=True)

    def _save_json_atomic(self, path: str, data: Any):
        """
        Saves JSON data atomically: Write to temp -> Rename to target.
        Prevents file corruption if the process crashes mid-write.
        """
        dir_name = os.path.dirname(path)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding='utf-8') as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            temp_path = tmp_file.name
        
        try:
            shutil.move(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise IOError(f"Failed to save atomic JSON to {path}: {e}")

    def create_case(self, name: str) -> str:
        """Creates a new Case File and returns the case_id."""
        case_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        case_data = {
            "schema_version": "1.0",
            "case_id": case_id,
            "name": name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "turns": []
        }
        
        path = os.path.join(CASES_DIR, f"{case_id}.json")
        self._save_json_atomic(path, case_data)
        return case_id

    def load_case(self, case_id: str) -> Optional[Dict]:
        """Loads a full Case File by ID."""
        path = os.path.join(CASES_DIR, f"{case_id}.json")
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, "r", encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[CaseManager] Corrupt case file: {case_id}")
            return None

    def save_turn(self, case_id: str, turn_data: Dict):
        """
        Appends a new turn to the Case File.
        Validates basic metadata requirements.
        """
        case = self.load_case(case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found.")

        # Validation: Ensure identifiers are present
        meta = turn_data.get("query_meta", {})
        if not meta.get("query_id"):
             print(f"[CaseManager] Warning: Turn missing 'query_id'. Audit trail validation may fail.")

        # Append Turn
        turn_data["turn_id"] = len(case["turns"]) + 1
        turn_data["timestamp"] = datetime.now().isoformat()
        case["turns"].append(turn_data)
        case["updated_at"] = datetime.now().isoformat()
        
        # Atomic Save
        path = os.path.join(CASES_DIR, f"{case_id}.json")
        self._save_json_atomic(path, case)

    def save_bundle(self, query_id: str, bundle: List[Dict]):
        """
        Persists an Evidence Bundle keyed by the canonical Query ID.
        This allows the Inspector to look up evidence by the query hash.
        """
        if not query_id:
            raise ValueError("Cannot save bundle without a valid query_id.")
            
        data = {
            "schema_version": "1.0",
            "query_id": query_id,
            "evidence_count": len(bundle),
            "bundle_data": bundle
        }
        
        path = os.path.join(BUNDLES_DIR, f"{query_id}.json")
        self._save_json_atomic(path, data)

    def load_bundle(self, query_id: str) -> Optional[List[Dict]]:
        """
        Loads an Evidence Bundle by canonical Query ID.
        Used by the Evidence Inspector.
        """
        path = os.path.join(BUNDLES_DIR, f"{query_id}.json")
        if not os.path.exists(path):
            return None
            
        try:
            with open(path, "r", encoding='utf-8') as f:
                data = json.load(f)
                return data.get("bundle_data", [])
        except Exception as e:
            print(f"[CaseManager] Error loading bundle {query_id}: {e}")
            return None

    def list_cases(self, include_empty: bool = False) -> List[Dict]:
        """
        Returns a list of available cases sorted by update time.
        By default, excludes 0-turn cases to prevent showing abandoned drafts.
        """
        cases = []
        if not os.path.exists(CASES_DIR):
            return []
            
        for filename in os.listdir(CASES_DIR):
            if filename.endswith(".json"):
                path = os.path.join(CASES_DIR, filename)
                try:
                    with open(path, "r", encoding='utf-8') as f:
                        data = json.load(f)
                        turn_count = len(data.get("turns", []))
                        
                        # Skip 0-turn cases unless explicitly requested
                        if turn_count == 0 and not include_empty:
                            continue
                            
                        cases.append({
                            "case_id": data.get("case_id"),
                            "name": data.get("name", "Untitled Case"),
                            "updated_at": data.get("updated_at", ""),
                            "created_at": data.get("created_at", ""),
                            "turn_count": turn_count
                        })
                except:
                    continue
        
        return sorted(cases, key=lambda x: x["updated_at"], reverse=True)

    def cleanup_empty_cases(self, max_age_hours: float = 1.0) -> int:
        """
        Deletes 0-turn cases older than max_age_hours.
        Returns the count of deleted cases.
        Prevents accidental deletion of cases created moments ago.
        """
        deleted_count = 0
        if not os.path.exists(CASES_DIR):
            return 0
            
        now = datetime.now()
        
        for filename in os.listdir(CASES_DIR):
            if filename.endswith(".json"):
                path = os.path.join(CASES_DIR, filename)
                try:
                    with open(path, "r", encoding='utf-8') as f:
                        data = json.load(f)
                        
                    turn_count = len(data.get("turns", []))
                    
                    # Only delete if 0 turns
                    if turn_count > 0:
                        continue
                    
                    # Check age
                    created_str = data.get("created_at", "")
                    if created_str:
                        try:
                            created_at = datetime.fromisoformat(created_str)
                            age_hours = (now - created_at).total_seconds() / 3600
                            
                            if age_hours >= max_age_hours:
                                os.remove(path)
                                deleted_count += 1
                                print(f"[CaseManager] Cleaned up empty case: {data.get('case_id', filename)[:8]} (age: {age_hours:.1f}h)")
                        except ValueError:
                            # Invalid timestamp, skip
                            continue
                except Exception as e:
                    print(f"[CaseManager] Error checking case {filename}: {e}")
                    continue
        
        if deleted_count > 0:
            print(f"[CaseManager] Cleanup complete: {deleted_count} empty case(s) removed.")
        
        return deleted_count

    def delete_case(self, case_id: str) -> bool:
        """Deletes a case file by ID. Returns True if deleted."""
        path = os.path.join(CASES_DIR, f"{case_id}.json")
        if os.path.exists(path):
            os.remove(path)
            print(f"[CaseManager] Deleted case: {case_id[:8]}")
            return True
        return False
