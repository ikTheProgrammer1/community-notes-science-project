# System Architecture: Community Notes Analytics

## Executive Overview
The **Community Notes Analytics** platform utilizes a **Hybrid AI Architecture** combined with high-performance **Ephemeral Data Processing**. This design ensures distinct advantages:
1.  **Speed**: In-memory OLAP (DuckDB) running on local NVMe ephemeral storage.
2.  **Security**: "Privacy-First" local AI (WebGPU) for sensitive data.
3.  **Power**: Cloud-gated access to frontier models (Grok/GPT-4) for deep forensic tasks.

---

## 🏗️ Architecture Diagram

```mermaid
graph TB
    %% Nodes
    User([User / Analyst])
    
    subgraph "Client-Side (Browser)"
        UI[Streamlit Chat Interface]
        WebGPU[🧠 WebLLM (Secondary Insights)]
        ChartEngine[Altair Visualization]
    end
    
    subgraph "Cloud Infrastructure (Google Cloud Run)"
        LB[Load Balancer]
        
        subgraph "Application Instance (Container)"
            App[dashboard.py]
            Logic[Business Logic Layer]
            
            subgraph "Compute Engine"
                Pandas[Pandas / NumPy]
                Sklearn[Scikit-Learn Clustering]
            end
            
            subgraph "Data Engine (OLAP)"
                DuckDB[(DuckDB 0.9.2)]
                Cache[Ephemeral /tmp Storage]
            end
        end
    end
    
    subgraph "Storage & Source"
        GCS[Google Cloud Storage]
        RawData[[Community Notes Dump .tsv]]
    end
    
    subgraph "Intelligence Providers"
        xAI[xAI (Grok)]
        OpenAI[OpenAI (GPT-4)]
        Anthropic[Anthropic (Claude)]
    end

    %% Flows
    User ==>|HTTPS| LB
    LB -->|Traffic Routing| App
    
    %% Application Logic
    App -->|Render| UI
    App -->|Query| DuckDB
    App -->|Cluster/Analyze| Sklearn
    
    %% Data Flow (Optimization)
    GCS -.->|1. Mount| App
    App -->|2. Atomic Copy (Startup)| Cache
    Cache ==>|3. Zero-Latency Read| DuckDB
    
    %% Intelligence Flow
    UI -.->|Private Memos| WebGPU
    
    %% CHAT PIPELINE (RAG)
    UI -.->|Forensic Query| App
    App -->|4. Fetch Context| DuckDB
    DuckDB --o|5. JSON Payload| App
    App ==>|6. Context + Prompt| xAI
    App ==>|6. Context + Prompt| OpenAI
    
    %% External
    xAI -.->|Real-Time Search| Internet((Live Web))
    
    %% Styling
    classDef cloud fill:#4285F4,stroke:#fff,stroke-width:2px,color:white;
    classDef db fill:#FFF100,stroke:#333,stroke-width:2px,color:black;
    classDef ai fill:#000,stroke:#fff,stroke-width:2px,color:white;
    classDef local fill:#FF4B4B,stroke:#fff,stroke-width:2px,color:white;
    
    class LB,App,GCS cloud;
    class DuckDB,Cache db;
    class xAI,OpenAI,Anthropic ai;
    class WebGPU local;
```

---

## 🧩 Key Component Breakdown

### 1. The Data Engine (DuckDB + Ephemeral Optimization)
- **Challenge:** Creating a dashboard that queries 2.2M+ rows without latency.
- **Solution:** We do NOT query the remote bucket directly. On startup, the container performs an **Atomic Localization** of the database to the instance's RAM-disk (`/tmp`).
- **Result:** Queries run at **NVMe speeds**, enabling instant filtering and aggregation.

### 2. The Intelligence Layer (Hybrid AI)
- **Local (WebGPU)**: Runs **Llama-3.2-3B** directly in the user's browser. Used for rapid summarization without data ever leaving the device (GDPR/Security compliant).
- **Cloud (API)**: Tunnels complex forensic requests to top-tier models (Grok). Used for "connecting dots" across the internet and verifying claims against real-time news usage agentic tools.

### 3. The Deployment Pipeline
- **CD**: GitHub push ➔ Cloud Build ➔ Cloud Run Revision.
- **Scaling**: Service scales to 0 (cost-effective) or keeps min instances warm (performance) based on traffic.

### 4. The "Chat with Data" Engine (Primary Feature)
The new forensic chat interface acts as the central command center for analysts.
- **Workflow (RAG)**:
    1.  **Hunt**: User query triggers a keyword search in DuckDB.
    2.  **Gather**: Top 50 relevant notes are extracted as structured JSON.
    3.  **Reason**: Evidence is sent to **Grok/GPT-4** with a "Senior Forensic Investigator" persona.
    4.  **Respond**: Analysis is streamed back to the user token-by-token.
- **State Management**: Chat history is maintained in the UI state (`st.session_state`), while the model interaction remains **stateless** to ensure each answer relies purely on the retrieved evidence (minimizing hallucination).
