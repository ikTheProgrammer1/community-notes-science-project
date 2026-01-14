import requests
import json
import streamlit as st

class UniversalCloudAdapter:
    """
    Unified client for xAI (Grok), OpenAI, and Anthropic.
    Designed for deep forensic analysis with large context windows.
    Zero-dependency implementation (uses standard requests).
    """
    
    
    # Curated Model List (Forensic Analysis Only)
    MODEL_OPTIONS = {
        "xAI": {
            "Grok 4.1 Fast (Reasoning)": "grok-4-1-fast-reasoning", 
            "Grok 4.1 Fast (Standard)": "grok-4-1-fast-non-reasoning",
            "Grok 3 (Standard)": "grok-3",
            "Grok 2 (Vision)": "grok-2-1212"
        },
        "OpenAI": {
            "GPT-5.2 (Flagship)": "gpt-5.2",
            "GPT-5 Mini": "gpt-5-mini",
            "GPT-4o (Legacy)": "gpt-4o"
        },
        "Anthropic": {
            "Claude Opus 4.5": "claude-3-opus-20240229",
            "Claude Sonnet 4.5": "claude-3-5-sonnet-latest"
        }
    }
    
    # Provider Connection Config
    PROVIDERS = {
        "xAI": {
            "url": "https://api.x.ai/v1/responses",
            "style": "xai"
        },
        "OpenAI": {
            "url": "https://api.openai.com/v1/chat/completions",
            "style": "openai"
        },
        "Anthropic": {
            "url": "https://api.anthropic.com/v1/messages",
            "style": "anthropic"
        }
    }

    def __init__(self, provider_name, api_key):
        if provider_name not in self.PROVIDERS:
            # Fallback for old session state keys
            mapped_name = provider_name.split(" ")[0]
            if mapped_name in self.PROVIDERS:
                provider_name = mapped_name
            else:
                raise ValueError(f"Unknown provider: {provider_name}")
        
        self.config = self.PROVIDERS[provider_name]
        self.api_key = api_key
        self.provider_name = provider_name

    def validate_and_repair_json(self, json_str, valid_note_ids, salvage=False):
        """
        Implements the 'Validate -> Repair -> Fail' strategy.
        If salvage=True: Strips invalid IDs instead of failing, returning a valid object with warnings.
        """
        import re
        try:
            # 1. Parse
            json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if json_match:
                clean_str = json_match.group(0)
            else:
                clean_str = json_str.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(clean_str)
            
            findings = data.get("dataset_findings", {})
            claims = findings.get("claims", [])
            
            # 2. Validate Evidence
            salvage_log = []
            
            for i, claim in enumerate(claims):
                evidence = claim.get("evidence", [])
                
                # Enum Check
                uncertainty = claim.get("uncertainty", "").lower()
                if uncertainty not in ["low", "medium", "high"]:
                     return False, None, f"Claim {i+1}: Uncertainty '{uncertainty}' is invalid. Must be low/medium/high."

                # ID Existence Check
                valid_evidence = []
                for item in evidence:
                    nid = str(item.get("note_id", "")).strip()
                    if nid in valid_note_ids:
                        valid_evidence.append(item)
                    elif nid != "":
                         msg = f"Claim {i+1}: Cited note_id '{nid}' does not exist."
                         if salvage:
                             print(f"[EvidenceContract] ⚠️ SALVAGE: Stripping invalid ID '{nid}'")
                             salvage_log.append(nid)
                         else:
                             print(f"[EvidenceContract] ❌ REJECT: Cited '{nid}' not found in {len(valid_note_ids)} valid IDs.")
                             return False, None, msg
                
                # If salvaging, update the evidence list
                if salvage:
                    claim['evidence'] = valid_evidence
                
                # Check for empty evidence AFTER stripping
                # If empty, we can mistakenly leave a claim with no support.
                # In salvage mode, we might want to downgrade it to 'high' uncertainty or remove it?
                # Contract Rule #1: "Every claim MUST have at least one supporting note_id".
                if not claim.get('evidence'): # Check current state
                     if salvage:
                         # If we stripped all evidence, we technically should remove the claim or move to cannot_conclude.
                         # For now, let's just mark it as highly uncertain or leave it (soft fail).
                         # Better: Return False if extensive stripping left a claim naked.
                         return False, None, f"Claim {i+1} lost all evidence after salvage."
                     else:
                         return False, None, f"Claim {i+1}: Evidence list is empty."

            if salvage and salvage_log:
                print(f"[EvidenceContract] ✅ Validation Passed via SALVAGE (Stripped {len(salvage_log)} IDs).")
                return True, data, f"Warning: Stripped {len(salvage_log)} invalid citations."
            
            print(f"[EvidenceContract] ✅ Validation Passed.")
            return True, data, None
            
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON syntax: {str(e)}"
        except Exception as e:
            return False, None, f"Validation error: {str(e)}"

    def generate_forensic_report_v2(self, system_prompt, user_context, task_query, model_id):
        """
        Buffered Generator for Evidence Contract.
        Yields status strings, then final JSON object.
        """
        full_user_message = f"CONTEXT DATA:\n{json.dumps(user_context, indent=2)}\n\nUSER QUERY:\n{task_query}"
        
        # 1. Extract Valid IDs for Validation (Normalize to String)
        valid_ids = set()
        
        # Handle wrappped {"notes": [...]} or raw list [...]
        notes_list = []
        if isinstance(user_context, dict) and "notes" in user_context:
            notes_list = user_context["notes"]
        elif isinstance(user_context, list):
            notes_list = user_context
            
        for note in notes_list:
             if 'noteId' in note:
                 # FORCE STRING NORMALIZATION
                 nid = str(note['noteId']).strip()
                 valid_ids.add(nid)
                 
        # INVARIANT: If bundle > 0 but valid_ids == 0 -> SYSTEM FAULT
        if len(notes_list) > 0 and len(valid_ids) == 0:
             yield f"❌ **System Error**: Evidence Bundle Corruption. Sent {len(notes_list)} notes but extracted 0 IDs. Check key names."
             return
        
        # DEBUG: Instrument ID Validation
        sample_ids = list(valid_ids)[:5]
        print(f"[EvidenceContract] Valid Note IDs (Waitlist): {len(valid_ids)}")
        print(f"[EvidenceContract] Sample IDs: {sample_ids}")
        print(f"[EvidenceContract] Sample Type: {type(sample_ids[0]) if sample_ids else 'N/A'}")

        yield "🔄 **Status**: Initializing Forensic Engine..."
        
        # 2. Fetch Raw Stream (Buffer it)
        raw_response = ""
        try:
            if self.config["style"] == "openai":
                stream = self._stream_openai_style(system_prompt, full_user_message, model_id)
            elif self.config["style"] == "anthropic":
                stream = self._stream_anthropic_style(system_prompt, full_user_message, model_id)
            elif self.config["style"] == "xai":
                stream = self._stream_xai_style(system_prompt, full_user_message, model_id)
            
            yield "🧠 **Status**: Generating Analysis..."
            
            for chunk in stream:
                # If chunk is a status message (from xAI tools), pass it through
                if chunk.startswith("\n\n*"): 
                    yield chunk
                elif chunk.startswith("\n\n["): # Error
                    yield chunk
                    return
                else:
                    raw_response += chunk
                    
            yield "🛡️ **Status**: Validating Evidence Contract..."
            
            # 3. Validate
            is_valid, validated_json, error_msg = self.validate_and_repair_json(raw_response, valid_ids)
            
            if is_valid:
                yield validated_json
                return
            
            # 4. Repair (Single Shot)
            yield f"⚠️ **Status**: Contract Violation Detected ({error_msg}). Attempting Repair..."
            
            repair_prompt = f"""
            SYSTEM: Your previous response failed validation. 
            ERROR: {error_msg}
            
            INSTRUCTION: 
            1. Fix the JSON. 
            2. Remove any `note_id` that is not in the valid list. 
            3. If a claim loses its evidence, MOVE IT to `cannot_conclude`. DO NOT invent an ID.
            4. If the error is "Evidence list is empty", DELETE the claim entirely from `claims`. Ensure the missing info is captured in `cannot_conclude`.
            
            Output ONLY valid JSON.
            PREVIOUS_RESPONSE:
            {raw_response}
            """
            
            # Simple non-streaming repair call (simulated by specialized short stream)
            # reusing the same provider/model for repair
            # We assume the provider handles a simple text-in/text-out for repair
            # For simplicity, we reuse the stream method and buffer it again
            
            repair_stream = self._stream_openai_style(system_prompt="You are a JSON repair bot.", user_message=repair_prompt, model_id=model_id) # Using simple prompt for repair
            if self.config["style"] == "xai":
                 repair_stream = self._stream_xai_style("You are a JSON repair bot.", repair_prompt, model_id)
            elif self.config["style"] == "anthropic":
                 repair_stream = self._stream_anthropic_style("You are a JSON repair bot.", repair_prompt, model_id)

            repaired_response = ""
            for chunk in repair_stream:
                repaired_response += chunk
                
            # 5. Re-Validate with SILENT SALVAGE (Last Ditch Effort)
            # If repair failed to remove invalid IDs, we force-strip them now.
            is_valid, validated_json, final_error = self.validate_and_repair_json(repaired_response, valid_ids, salvage=True)
            
            if is_valid:
                if final_error: # Warning from salvage
                     yield f"⚠️ **Status**: Partial Repair Success. {final_error}"
                yield validated_json
            else:
                yield f"❌ **Hard Fail**: Answer rejected. Validation failed after repair.\nError: {final_error}"

        except Exception as e:
            yield f"❌ **System Error**: {str(e)}"

    def generate_forensic_report(self, system_prompt, user_context, task_query, model_id):
        """
        Generates a streaming forensic report using the specified model.
        """
        full_user_message = f"CONTEXT DATA:\n{json.dumps(user_context, indent=2)}\n\nUSER QUERY:\n{task_query}"

        if self.config["style"] == "openai":
            return self._stream_openai_style(system_prompt, full_user_message, model_id)
        elif self.config["style"] == "anthropic":
            return self._stream_anthropic_style(system_prompt, full_user_message, model_id)
        elif self.config["style"] == "xai":
             return self._stream_xai_style(system_prompt, full_user_message, model_id)

    def _stream_openai_style(self, system_prompt, user_message, model_id):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": True,
            "temperature": 0.3 
        }

        try:
            with requests.post(self.config["url"], headers=headers, json=payload, stream=True) as r:
                if r.status_code != 200:
                    try:
                        error_details = r.json()
                        yield f"\n\n[API_ERROR]: {json.dumps(error_details, indent=2)}"
                    except:
                        yield f"\n\n[API_ERROR]: Status {r.status_code} - {r.text}"
                    return

                for line in r.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            if line.strip() == "data: [DONE]":
                                break
                            try:
                                json_str = line[6:] 
                                data = json.loads(json_str)
                                content = data['choices'][0]['delta'].get('content', '')
                                if content:
                                    yield content
                            except Exception:
                                continue
        except Exception as e:
            yield f"\n\n[CONNECTION_ERROR]: {str(e)}"

    def _stream_xai_style(self, system_prompt, user_message, model_id):
        """
        Specialized handler for xAI Agentic Flow (v1/responses).
        Uses 'input' instead of 'messages' and supports tool definitions.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # xAI 'input' structure
        payload = {
            "model": model_id,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": True,
            "temperature": 0.3
        }

        # Conditional Tool Usage: Only Grok-4 supports server-side tools
        if "grok-4" in model_id:
             payload["tools"] = [
                {"type": "web_search", "enable_image_understanding": False},
                {"type": "x_search"},
                {"type": "code_interpreter"} 
            ]

        try:
            # DEBUG: Log Payload
            print(f"[xAI Prompt] Model: {model_id}")
            print(f"[xAI Payload] Input Length: {len(str(payload['input']))}")
            # print(f"[xAI Payload] Full: {json.dumps(payload, indent=2)}") # Uncomment for full dump

            with requests.post(self.config["url"], headers=headers, json=payload, stream=True) as r:
                if r.status_code != 200:
                    print(f"[xAI Error] Status: {r.status_code}")
                    print(f"[xAI Error] Headers: {r.headers}")
                    try:
                        error_details = r.json()
                        print(f"[xAI Error] JSON: {json.dumps(error_details, indent=2)}")
                        yield f"\n\n[xAI_API_ERROR]: {json.dumps(error_details, indent=2)}"
                    except:
                        print(f"[xAI Error] Raw: {r.text}")
                        yield f"\n\n[xAI_API_ERROR]: Status {r.status_code} - {r.text}"
                    return

                for line in r.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            try:
                                json_str = line[6:] 
                                data = json.loads(json_str)
                                
                                # xAI v1/responses Stream Handler
                                # Event Types: response.output_text.delta, response.tool_call..., etc.
                                event_type = data.get('type', '')
                                
                                # 1. Content Handling
                                if event_type == 'response.output_text.delta':
                                    delta = data.get('delta', '')
                                    if delta:
                                        yield delta
                                        
                                # 2. Tool Usage Visualization
                                elif 'tool' in event_type or event_type == 'response.tool_call':
                                    # Try to identify tool type if available in payload, else generic
                                    tool_name = data.get('tool_name', '').lower()
                                    
                                    if 'web' in tool_name:
                                        yield "\n\n*🌐 Scanning Global Network...*\n\n"
                                    elif 'x_search' in tool_name or 'twitter' in tool_name:
                                        yield "\n\n*🐦 Intercepting X Signals...*\n\n" 
                                    elif 'code' in tool_name:
                                        yield "\n\n*💻 Executing Neural Code...*\n\n"
                                    # REMOVED: Generic "Analyzing" message to prevent spam on every chunk
                                    
                            except Exception:
                                continue
        except Exception as e:
            yield f"\n\n[CONNECTION_ERROR]: {str(e)}"

    def _stream_anthropic_style(self, system_prompt, user_message, model_id):
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_id,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "stream": True,
            "max_tokens": 4096,
            "temperature": 0.3
        }

        try:
            with requests.post(self.config["url"], headers=headers, json=payload, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            try:
                                json_str = line[6:]
                                data = json.loads(json_str)
                                if data['type'] == 'content_block_delta':
                                    content = data['delta'].get('text', '')
                                    if content:
                                        yield content
                            except Exception:
                                continue
        except Exception as e:
            yield f"\n\n[CONNECTION_ERROR]: {str(e)}"

def get_investigator_system_prompt():
    return """You are the Senior Forensic Investigator for the VIP Intelligence Platform. 
Your clearance level is TOP SECRET.

ROLE:
Analyze the provided 'Community Notes' data and the specific User Query to reconstruct the truth. 
You are looking for coordination patterns, narrative shifts, and contradictions.

STRICT OUTPUT CONTRACT:
You must output **ONLY** valid JSON. No Markdown formatting. No preamble.
Your JSON must strictly adhere to this schema:

{
  "dataset_findings": {
    "claims": [
      {
        "claim_text": "Detailed assertion about the narrative.",
        "evidence": [
            { "note_id": "123", "support_text": "Exact quote or logic from note 123 supporting this claim." }
        ],
        "uncertainty": "low" | "medium" | "high" 
      }
    ],
    "cannot_conclude": [
      {
        "question_part": "sub-question you cannot answer",
        "reason": "Specific reason why evidence is missing."
      }
    ]
  }
}

RULES:
1. **EVIDENCE OR SILENCE**: Every claim in `claims` MUST typically have at least one supporting `note_id`.
2. **NO HALLUCINATION**: `note_ids` must be exact matches from the provided Context Data.
3. **ID PRECISION**: **DO NOT** cite `tweetId` or `postId`. You MUST use the `noteId` field (e.g., "17293847...").
4. **UNCERTAINTY**:
   - "Low": Direct quote support.
   - "High": Inference required.
5. **CANNOT CONCLUDE**: 
   - If evidence is missing for any part of the question, DO NOT GUESS. moved that part to `cannot_conclude`.
   - If the user asks for a specific `note_id` (e.g. "99999") and it is NOT in the Context Data, you MUST put this in `cannot_conclude` with reason "ID not found". DO NOT create a Claim.
6. **NO NEGATIVE CLAIMS**: Valid Claims must have evidence. Do not create a Claim just to say "No note found". Use `cannot_conclude` instead.
7. **REFRAME CONSENSUS**: If user asks for "consensus" or "sentiment", interpret this strictly as "What patterns of correction/misinformation appear in Community Notes". Explicitly state this scope in your answer if necessary.
8. **AGENTIC PROTOCOL**: You are an objective forensic analyst. No "vibes". Only data.
"""
