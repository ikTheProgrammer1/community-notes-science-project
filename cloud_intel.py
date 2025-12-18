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
            "Grok 4 (Standard)": "grok-4-0709"
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
            "temperature": 0.3,
            "tools": [
                {"type": "web_search", "enable_image_understanding": False},
                {"type": "x_search"},
                {"type": "code_interpreter"} 
            ]
        }

        try:
            with requests.post(self.config["url"], headers=headers, json=payload, stream=True) as r:
                if r.status_code != 200:
                    try:
                        error_details = r.json()
                        yield f"\n\n[xAI_API_ERROR]: {json.dumps(error_details, indent=2)}"
                    except:
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
You are looking for:
1. Coordination patterns (Astroturfing).
2. Shifts in narrative timing.
3. Contradictions in the source material.

OUTPUT FORMAT:
- Use strict Markdown.
- Start with an 'EXECUTIVE SUMMARY'.
- Use '### TIMELINE RECONSTRUCTION' for chronological events.
  - **FORMATTING RULE**: Dates must be Bold Headers (e.g., **Mid-Oct 2025:**) at the start of the line.
- Use '### EVIDENCE LOCKER' to cite specific note IDs.
  - **FORMATTING RULE**: Use a Bulleted List format. Add a blank line between each evidence item to ensure they render as separate blocks.
- Be concise, objective, and military-grade precise.
- NO fluff. NO polite introductions.

AGENTIC PROTOCOL:
You have access to 'tweetId' in the context data.
If you need more information about a specific tweet (e.g., who wrote it, what the text says, or its engagement), YOU MUST:
1. Use 'x_search' or 'web_search' with the tweetId (e.g., "site:twitter.com 123456789") to find the original post and author.
2. Synthesize this external knowledge with the internal note data.
DO NOT hallucinate tweet content. If you don't know, SEARCH FOR IT."""
