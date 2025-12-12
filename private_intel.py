import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json

def run_private_intel(dashboard_context=None):
    """
    The Private Intelligence Assistant.
    Runs a Local LLM (Llama-3.2-3B) via WebGPU to analyze data client-side.
    """
    st.title("🛡️ Private Intelligence Assistant")
    st.caption("Powered by Llama-3.2-3B (Local WebGPU)")
    
    # Context Area
    with st.expander("🔍 Intelligence Context", expanded=True):
        if dashboard_context:
            st.json(dashboard_context)
            context_str = json.dumps(dashboard_context)
        else:
            st.info("No specific dashboard context loaded. Running in General Chat mode.")
            context_str = "{}"
            
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        ### Mission Briefing
        This assistant runs **entirely on your device**. 
        *   **Zero Data Leakage**: No data is sent to the cloud.
        *   **Local Inference**: Uses your GPU to think.
        """)

    # --- WebLLM Bridge ---
    # We use a custom HTML component to load the WebLLM engine
    # and communicate via postMessage (conceptually, though Streamlit components handling is tricky).
    # For MVP, we will embed the full JS application in an iframe.
    
    # HTML/JS Code for WebLLM
    # Note: We use the CDN version for simplicity.
    webllm_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Local Intel</title>
        <script type="module">
            // Import WebLLM from CDN
            import {{ CreateMLCEngine }} from "https://esm.run/@mlc-ai/web-llm";

            // Configuration
            const SELECTED_MODEL = "Llama-3.2-3B-Instruct-q4f32_1-MLC";
            let engine = null;
            let messages = []; // Stateful conversation history
            
            // UI Elements
            const output = document.getElementById("chat-output");
            const input = document.getElementById("user-input");
            const btn = document.getElementById("send-btn");
            const status = document.getElementById("status");
            const loadBtn = document.getElementById("load-btn");

            // Logger
            function log(msg) {{
                status.innerText = msg;
                console.log(msg);
            }}
            
            // Append Message
            function appendMessage(role, text) {{
                const msgDiv = document.createElement("div");
                msgDiv.className = "message " + role;
                msgDiv.innerHTML = "<b>" + role + ":</b> " + text;
                output.appendChild(msgDiv);
                output.scrollTop = output.scrollHeight;
            }}

            // Load Engine
            loadBtn.onclick = async () => {{
                loadBtn.disabled = true;
                log("Initializing WebGPU...");
                
                try {{
                    engine = await CreateMLCEngine(
                        SELECTED_MODEL,
                        {{ initProgressCallback: (report) => log(report.text) }}
                    );
                    log("Ready. Model Loaded.");
                    btn.disabled = false;
                    
                    // Inject Context if available
                    const context = {context_str};
                    if (Object.keys(context).length > 0) {{
                        const contextPayload = JSON.stringify(context);
                        const contextMsg = `
=== MISSION DATA START ===
${{contextPayload}}
=== MISSION DATA END ===

INSTRUCTION: Summarize the Mission Data above. Do not lecture. Be brief and military-style.
`;
                        // Initialize History
                        messages = [
                            {{ role: "system", content: "You are a Forensic Intelligence Analyst working for a VIP client. Your job is to analyze the specific data provided in the Context below. Do NOT use outside knowledge or general definitions. If the Context is empty, state: 'No intelligence data loaded. Please click an Analyze button.'" }},
                            {{ role: "user", content: contextMsg }}
                        ];

                        log("Analyzing Mission Data...");
                        const completion = await engine.chat.completions.create({{
                            messages: messages
                        }});
                        
                        const summary = completion.choices[0].message.content;
                        messages.push({{ role: "assistant", content: summary }});
                        appendMessage("assistant", summary);
                        log("Ready.");
                    }} else {{
                        // No Context Mode
                        messages = [
                            {{ role: "system", content: "You are a Forensic Intelligence Analyst working for a VIP client. Your job is to analyze the specific data provided in the Context below. Do NOT use outside knowledge or general definitions. If the Context is empty, state: 'No intelligence data loaded. Please click an Analyze button.'" }}
                        ];
                        appendMessage("system", "No Mission Data loaded. Standing by.");
                    }}
                    
                }} catch (err) {{
                    log("Error: " + err.message);
                    loadBtn.disabled = false;
                }}
            }};

            // Send Message
            btn.onclick = async () => {{
                if (!engine) return;
                const text = input.value;
                if (!text) return;
                
                input.value = "";
                appendMessage("user", text);
                messages.push({{ role: "user", content: text }});
                
                // Stream response
                const replyDiv = document.createElement("div");
                replyDiv.className = "message assistant";
                replyDiv.innerHTML = "<b>AI:</b> ";
                output.appendChild(replyDiv);
                
                let fullReply = "";
                
                try {{
                    const chunks = await engine.chat.completions.create({{
                        messages: messages,
                        stream: true
                    }});

                    for await (const chunk of chunks) {{
                        const content = chunk.choices[0]?.delta?.content || "";
                        fullReply += content;
                        replyDiv.innerHTML = "<b>AI:</b> " + fullReply;
                        output.scrollTop = output.scrollHeight;
                    }}
                    
                    messages.push({{ role: "assistant", content: fullReply }});
                    
                }} catch (err) {{
                    replyDiv.innerHTML += "[Error: " + err.message + "]";
                }}
            }};
        </script>
        <style>
            body {{ font-family: sans-serif; background: #0e1117; color: #fafafa; padding: 10px; }}
            #chat-container {{ display: flex; flex-direction: column; height: 500px; }}
            #chat-output {{ flex: 1; overflow-y: auto; border: 1px solid #333; padding: 10px; margin-bottom: 10px; border-radius: 5px; background: #1a1c24; }}
            .message {{ margin-bottom: 8px; padding: 5px; border-radius: 4px; }}
            .user {{ background: #262730; }}
            .assistant {{ background: #004280; }}
            #controls {{ display: flex; gap: 10px; }}
            input {{ flex: 1; padding: 8px; border-radius: 4px; border: 1px solid #555; background: #333; color: white; }}
            button {{ padding: 8px 16px; cursor: pointer; background: #ff4b4b; color: white; border: none; border-radius: 4px; }}
            button:disabled {{ background: #555; cursor: not-allowed; }}
            #status {{ font-size: 0.8em; color: #888; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div id="status">Status: Waiting to Load Model...</div>
        <button id="load-btn">🚀 Load Llama-3.2-3B (Local)</button>
        <div id="chat-container">
            <div id="chat-output"></div>
            <div id="controls">
                <input type="text" id="user-input" placeholder="Ask about the intelligence data...">
                <button id="send-btn" disabled>Send</button>
            </div>
        </div>
    </body>
    </html>
    """
    
    components.html(webllm_html, height=600)

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    # Mock Context for standalone testing
    mock_context = {
        "top_cluster": "Cluster 0 (Gaza Conflict)",
        "severity": "High",
        "notes_count": 450,
        "key_terms": ["Hostages", "Ceasefire", "Propaganda"]
    }
    run_private_intel(mock_context)
