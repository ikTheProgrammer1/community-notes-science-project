# 🛡️ Community Notes Analytics
> **Advanced Forensics & Counter-Misinformation System for Community Notes**

The **Community Notes Analytics** is a military-grade analytical suite designed to protect high-profile individuals from coordinated misinformation campaigns ("Astroturfing") on the X platform. By leveraging the open **Community Notes** dataset, it reconstructs truth through forensic data analysis and hybrid AI agents.

---

## 🚀 Key Capabilities

### 🧠 Hybrid AI Core
*   **Local Intelligence (WebGPU)**: Runs **Llama-3.2-3B** entirely in your browser (`private_intel.py`) for zero-leakage analysis of sensitive data.
*   **Global Intelligence (xAI)**: Integrates **Grok Agentic Tools** (`cloud_intel.py`) to cross-reference claims against real-time internet data and X posts.

### 📊 Strategic Modules
*   **Narrative Clustering**: Uses **TF-IDF & K-Means** to automatically group thousands of isolated tweets into coherent "Attack Narratives" and visualize their lifecycles.
*   **The "Winning Formula"**: Analyzes successful notes to determine the optimal semantic structure for debunking specific types of lies.
*   **Attack Signature**: Fingerprints the tactics of attackers (e.g., manipulated media vs. missing context).

---

## 🏗️ Architecture

| Component | Tech Stack | Description |
| :--- | :--- | :--- |
| **Data Engine** | **DuckDB** | In-memory OLAP SQL analysis of massive `.tsv` datasets. |
| **Frontend** | **Streamlit** | Rapid "War Room" dashboard for real-time monitoring. |
| **Visualization** | **Altair / PyDeck** | Interactive charts and geospatial rendering. |
| **AI Agents** | **Custom Universal Adapter / xAI SDK** | Multi-agent orchestration for forensic reporting. |

---

## 📚 Documentation

*   [**Strategic Architecture**](docs/misinformation_dashboard_strategy.md): Deep dive into the "Privacy-First, Cloud-Augmented" design.
*   [**Counter-Strategy Doctrine**](docs/misinformation-counter-strategy.md): The operational playbook for neutralizing threats.
*   [**Dataset Overview**](docs/dataset_overview.md): Understanding the structure of Community Notes data.
*   [**Analysis Guide**](docs/community_notes_analysis_guide.md): Recipes for extracting patterns from the raw data.

---

## ⚡ Quick Start

### Prerequisite: Install `uv`
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Start the Platform
```bash
# 1. Install Dependencies
uv sync

# 2. Run the War Room
bash run.sh
```

*Status: Active Development*
