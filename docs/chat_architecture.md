# Architecture: The "Chat with Data" Engine

## Executive Summary
The **Chat with Data** feature is a high-precision **Retrieval Augmented Generation (RAG)** system designed for forensic analysis. Unlike generic chatbots, it provides answers grounded strictly in the underlying Community Notes dataset.

---

## ⚡ The Forensic Pipeline (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as 🕵️ Analyst
    participant UI as Streamlit UI
    participant DB as ⚡ Data Engine (DuckDB)
    participant Cloud as ☁️ AI Cloud (Grok/GPT)

    Note over UI, Cloud: 1. THE HUNT (Retrieval)
    Analyst->>UI: "Trace the 'fraud' narrative evolution"
    UI->>DB: SEARCH (keyword="fraud")
    DB->>DB: Scan 2.2M Rows (NVMe Speed)
    DB->>UI: Return TOP 50 Relevant Notes
    
    Note over UI, Cloud: 2. THE REASONING (Generative)
    UI->>UI: Package Evidence (JSON Payload)
    UI->>Cloud: SEND {Prompt + Evidence + Query}
    
    Note right of Cloud: SYSTEM PROMPT:<br/>"You are a Senior<br/>Forensic Investigator..."
    
    Cloud->>Cloud: Analyze Patterns & Timeline
    
    Note over UI, Cloud: 3. THE LINK (Streaming)
    Cloud-->>UI: Stream Response (Token-by-Token)
    UI-->>Analyst: Render Forensic Report
```

---

## ⚙️ Technical Mechanics

### 1. Retrieval Strategy (The "Hunt")
*   **Engine**: DuckDB running on ephemeral NVMe storage (`/tmp`).
*   **Latency**: Sub-10ms search time.
*   **Logic**:
    *   Filters notes by keyword matching (Summary + Tweet ID).
    *   Sorts by `createdAtMillis` (descending) to prioritize recent activity.
    *   Selects the top **50** entries to fit comfortably within the model's context window.

### 2. The Persona (The "Brain")
We do not ask the AI to "chat". We ask it to **investigate**.
*   **System Role**: "Senior Forensic Investigator".
*   **Instruction**: "Analyze the provided JSON mission data. Identify coordination, timeline evolution, and key actors. Be objective and concise."
*   **Constraint**: The model is strictly forbidden from using outside knowledge for the core facts—it must cite the provided notes.

### 3. Stateless Intelligence
To ensure forensic integrity:
*   **The UI is Stateful**: It remembers your conversation history so you can scroll back.
*   **The AI is Stateless**: Every query is treated as a fresh investigation. It sees the *current* query and the *current* evidence. It does not "remember" the previous turn's hallucination. This reduces "drift" and keeps answers grounded in data.
