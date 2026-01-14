
import os
import requests
import json
import uuid

# --- CONFIGURATION ---
MODELS_TO_TEST = [
    "grok-4-1-fast-non-reasoning", # The problematic model
    "grok-beta",                   # The known stable model
]
ENDPOINT = "https://api.x.ai/v1/responses"

def get_api_key():
    key = os.environ.get("XAI_API_KEY")
    if not key:
        print("❌ XAI_API_KEY environment variable not set.")
        key = input("👉 Please enter your xAI API Key (or Ctrl+C to exit): ").strip()
    return key

def test_model_validity(api_key, model_id):
    """TEST 1: Send a tiny payload to verify Model ID is valid for this key."""
    print(f"\n--- TEST 1: Validity Check [{model_id}] ---")
    
    payload = {
        "model": model_id,
        "input": [
            {"role": "system", "content": "You are a test bot."},
            {"role": "user", "content": "Hello world."}
        ],
        "stream": False,
        "temperature": 0.1
    }
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    try:
        r = requests.post(ENDPOINT, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ PASS: Model '{model_id}' accepted the request.")
            return True
        else:
            print(f"❌ FAIL: Status {r.status_code}")
            print(f"   Body: {r.text}")
            return False
    except Exception as e:
        print(f"❌ ERROR: Connection failed: {e}")
        return False

def test_context_limit(api_key, model_id):
    """TEST 2: Send a large payload (simulating 50 notes) to check context handling."""
    print(f"\n--- TEST 2: Context Stress Test [{model_id}] ---")
    
    # 50k chars of dummy text ~ 50 notes
    dummy_text = "This is a dummy test context sentence. " * 2000 
    print(f"   Payload Size: {len(dummy_text)} chars")

    payload = {
        "model": model_id,
        "input": [
            {"role": "system", "content": "Analyze this data."},
            {"role": "user", "content": f"Context: {dummy_text}\n\nQuestion: Test?"}
        ],
        "stream": False
    }
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    try:
        r = requests.post(ENDPOINT, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            print(f"✅ PASS: Model processed large context successfully.")
            return True
        else:
            print(f"❌ FAIL: Status {r.status_code}")
            print(f"   Body: {r.text}")
            return False
    except Exception as e:
        print(f"❌ ERROR: Connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🔬 xAI DIAGNOSTIC TOOL")
    print("=======================")
    
    key = get_api_key()
    
    for model in MODELS_TO_TEST:
        print(f"\n[ Testing Model: {model} ]")
        is_valid = test_model_validity(key, model)
        
        if is_valid:
            test_context_limit(key, model)
        else:
            print(f"⚠️ Skipping context test for {model} due to validity failure.")
            
    print("\n🏁 Diagnostic Complete.")
