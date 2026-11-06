# DataMind


An Autonomous AI-Powered Data Intelligence Platform

*Transform raw data into forensic insights and strategic forecasts — without writing a single line of code.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-000000?style=flat)](https://ollama.ai)
[![SQLite](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=flat&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## What is DataMind?

DataMind is not a dashboard. It is an **autonomous analytical workspace** — a multi-agent AI system that investigates your data, understands its domain without human guidance, and delivers executive-grade insights through a premium dark-mode interface.

Upload any structured data file. DataMind reads it, learns from it, remembers patterns across sessions, and answers questions about it in plain language — from a single stat to a full forensic breakdown.

---

## Features

### Core Intelligence

- **Multi-Agent Architecture** — Specialized agents for analysis, prediction, visualization, summarization, and diagnostics work in coordination
- **Autonomous Domain Discovery** — Automatically identifies whether your data is financial, medical, e-commerce, HR, logistics, or general without any configuration
- **Self-Learning Memory** — Patterns discovered in your data are stored and injected into future analyses, making every session smarter than the last
- **Verified Reasoning** — A security firewall ensures agents only reference columns that actually exist — no hallucinated insights

### Analysis & Prediction

- **Forensic Analysis** — Structured executive briefings: Context → Finding → Evidence → Implication
- **Universal Prediction Engine** — Auto-detects task type (classification, regression, clustering, time-series) from your data
- **Multi-Model Benchmarking** — Runs Random Forest, Gradient Boosting, and Linear models in parallel, picks the best by cross-validation
- **Feature Intelligence** — Interactive feature importance charts explain *why* the model makes its predictions

### Chatbot Interface

- **Three-Tier Response System**:
  - ⚡ **Instant** (< 100ms) — Row counts, column stats, null checks via direct computation
  - 💬 **Quick** (< 3s) — Focused questions via lightweight LLM with streaming output
  - 🔬 **Deep Analysis** (5–15s) — Full agent pipeline for complex multi-column reasoning
- **Lab Injection** — Render any chat response directly into the Analysis or Prediction Laboratory
- **Conversation Memory** — Full chat history persisted per user per file, restored on re-login

### User & Data Management

- **Secure Authentication** — bcrypt password hashing, account lockout after 5 failed attempts, server-side session tokens
- **Global File Deduplication** — SHA256 hashing prevents duplicate storage; the same file uploaded by multiple users is stored once
- **Per-User Data Isolation** — Every analysis, pattern, prediction, and chat is strictly scoped to the authenticated user
- **My Files Dashboard** — Manage, reload, and delete previously analyzed datasets with full history restored

### Security

- **Prompt Injection Defense** — Uploaded data is wrapped in trust boundaries before reaching the LLM
- **File Bomb Protection** — Magic bytes verification, row/column caps, and memory estimation block malicious uploads
- **IDOR Prevention** — Every data fetch verifies ownership before returning results
- **Rate Limiting** — Per-user limits on login, uploads, chat, and LLM calls
- **Safe Error Handling** — No stack traces or internal paths ever reach the UI

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit (custom dark-mode CSS, glassmorphism UI) |
| AI Engine | Ollama — `qwen2.5-coder:7b` (runs fully local) |
| Backend | Python 3.10+ (async orchestration, multi-agent routing) |
| Database | SQLite with WAL mode (concurrent multi-user safe) |
| Analytics | Pandas, Scikit-Learn, SciPy, Statsmodels |
| Visualization | Plotly, Matplotlib |
| Auth | bcrypt, secrets (session tokens), python-dotenv |
| Security | Custom sanitization, rate limiting, prompt guard layers |

---

## Project Structure

```text
DataMind/
├── app.py                        # Entry point — auth routing + app startup
├── config.py                     # All constants loaded from .env
├── database.py                   # SQLite connection manager + all DB methods
├── requirements.txt
├── .env.example                  # Environment variable template
│
├── assets/
│   └── logo.jpg
│
├── data/                         # Gitignored — created at runtime
│   ├── datamind.db               # SQLite database
│   └── uploads/                  # User uploaded files
│
└── datamind/
    ├── agent/                    # Multi-agent AI brain
    │   ├── orchestrator.py       # Intent classifier + traffic router
    │   ├── analyst_agent.py      # Forensic deep-dive analysis
    │   ├── predict_agent.py      # ML task routing + result formatting
    │   ├── viz_agent.py          # Automated Plotly chart generation
    │   ├── summary_agent.py      # Dataset profiling + overview
    │   ├── diagnostic_agent.py   # Pre-prediction data validation
    │   ├── chat_classifier.py    # Three-tier chat intent engine
    │   ├── instant_responder.py  # Sub-100ms stat computation
    │   └── cleaning_agent.py     # Automated data quality reports
    │
    ├── auth/
    │   └── auth.py               # Register, login, sessions, reset tokens
    │
    ├── llm/
    │   └── ollama_client.py      # Centralized Ollama calls + retry logic
    │
    ├── memory/
    │   ├── session.py            # Per-user session state management
    │   ├── learner.py            # Pattern extraction + self-learning loop
    │   ├── query_cache.py        # LRU cache for repeat queries
    │   ├── context_builder.py    # Tiered context assembly for prompts
    │   └── feedback.py           # Helpfulness tracking + confidence decay
    │
    ├── security/
    │   ├── sanitizer.py          # Input sanitization (filenames, columns, auth)
    │   ├── upload_guard.py       # File validation + bomb detection
    │   ├── authorizer.py         # IDOR prevention + ownership checks
    │   ├── rate_limiter.py       # Per-user request throttling
    │   ├── prompt_guard.py       # LLM prompt injection defense
    │   └── error_handler.py      # Safe error logging + user messaging
    │
    ├── tools/
    │   ├── file_loader.py        # Universal file ingestion (CSV/Excel/JSON/Parquet)
    │   ├── ml_runner.py          # Universal ML pipeline (classify/regress/cluster/ts)
    │   ├── chart_builder.py      # Plotly chart factory
    │   └── stats.py              # Fast statistical computation
    │
    ├── ui/
    │   ├── layout.py             # Global CSS + dark theme
    │   ├── auth_page.py          # Login, register, guest flow
    │   ├── left_panel.py         # File controls + sidebar
    │   ├── right_panel.py        # Chatbot interface
    │   ├── prediction_lab.py     # Prediction Laboratory view
    │   ├── dashboard.py          # My Files + user stats
    │   ├── data_manager.py       # File management UI
    │   ├── account_page.py       # Account settings
    │   └── settings_page.py      # App preferences
    │
    └── utils/
        ├── chart_utils.py
        ├── data_utils.py
        ├── interactive_charts.py
        └── sample_data.py
```

---

## Getting Started

### Prerequisites

| Requirement | Version | Notes |
| --- | --- | --- |
| Python | 3.10+ | |
| Ollama | Latest | [Install from ollama.ai](https://ollama.ai) |
| Git | Any | |

### 1. Clone the Repository

```bash
git clone https://github.com/Shreyas-Reddy707/Datamind.git
cd Datamind
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Pull the AI Model

```bash
ollama pull qwen2.5-coder:7b
```

Make sure Ollama is running in the background:

```bash
ollama serve
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
SESSION_SECRET=your-secret-key-here
```

Generate a secure `SESSION_SECRET`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Run the App

```bash
streamlit run app.py
```

Visit `http://localhost:8501` in your browser.

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Model to use for analysis |
| `SESSION_SECRET` | *(required)* | Secret key for session signing |

> **Never commit `.env` to version control.** It is gitignored by default.

---

## Supported File Formats

| Format | Extension | Notes |
| --- | --- | --- |
| CSV | `.csv` | Auto-detects encoding and delimiter |
| Excel | `.xlsx`, `.xls` | Max 100,000 rows for safety |
| JSON | `.json` | Array or records format |
| Parquet | `.parquet` | Columnar format, fast loading |

**Limits:** 50MB file size · 500,000 rows · 500 columns · 500MB in-memory

---

## How It Works

### The Agent Pipeline

```text
User Query
    │
    ▼
Orchestrator (Intent Classification)
    │
    ├── "show/plot/chart"      → VizAgent       → Plotly Chart
    ├── "predict/forecast"     → DiagnosticAgent → PredictAgent → ML Report
    ├── "summarize/overview"   → SummaryAgent    → Dataset Profile
    └── "analyze/why/compare"  → AnalystAgent    → Forensic Briefing
```

### The Self-Learning Loop

```text
Analysis Complete
    │
    ▼
PatternLearner extracts findings
    │
    ├── Statistical: correlations > 0.7, outliers > 3σ
    └── LLM-based: 1-sentence key insight extraction
    │
    ▼
Stored in learned_patterns (scoped to user + file)
    │
    ▼
Injected as "Prior Intelligence" into next analysis prompt
    │
    ▼
Every session is smarter than the last
```

### The Three-Tier Chat

```text
User Message
    │
    ▼
TierClassifier (regex, no LLM)
    │
    ├── Tier 1 (Instant)   → InstantResponder   → < 100ms
    ├── Tier 2 (Quick)     → Ollama + minimal context → streamed output
    └── Tier 3 (Deep)      → Full agent pipeline → rendered to Lab
```

---

## Security Model

DataMind is built with defense-in-depth. Every external input passes through multiple independent validation layers:

```text
External Input
    │
    ▼
UploadGuard      → File size, magic bytes, row/col caps, memory estimate
    │
    ▼
InputSanitizer   → Filename, column names, auth fields, ReDoS-safe regex
    │
    ▼
RateLimiter      → Per-user throttling on login, upload, chat, LLM calls
    │
    ▼
Authorizer       → Ownership check before any data access (IDOR prevention)
    │
    ▼
PromptGuard      → Injection scan, trust boundary wrapping before LLM
    │
    ▼
SafeErrorHandler → Logs full details privately, shows only safe message to user
```

---

## Database Schema

The SQLite database uses WAL journal mode for concurrent multi-user access and enforces foreign key constraints on all connections.

**Key tables:**

| Table | Purpose |
| --- | --- |
| `users` | Accounts with lockout + activity tracking |
| `user_sessions` | Server-side session tokens with expiry |
| `global_files` | Deduplicated file registry (SHA256) |
| `user_files` | Per-user references to global files |
| `analysis_memory` | Full analysis history per user per file |
| `learned_patterns` | Self-learning pattern store with confidence decay |
| `prediction_history` | Model performance history for smart reuse |
| `chat_history` | Persistent chat per user per file (capped at 500) |
| `audit_log` | Security event log (login, uploads, access attempts) |
| `password_reset_tokens` | Hashed one-time reset tokens |

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

### Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Ollama details

# Run
streamlit run app.py
```

### Code Style

- Follow PEP 8
- All new modules must include a module-level docstring
- All database operations must use parameterized queries
- All new agent methods must return {"success": bool, "result": ...}

---

## Roadmap

- [ ] Multi-file cross-analysis (join datasets in a single query)
- [ ] PDF and report export from Lab artifacts
- [ ] Email-based password reset (SMTP integration)
- [ ] Admin dashboard for user management
- [ ] Docker deployment configuration
- [ ] Support for additional LLM backends (OpenAI, Anthropic API)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Ollama](https://ollama.ai) — Local LLM inference
- [Streamlit](https://streamlit.io) — App framework
- [Scikit-Learn](https://scikit-learn.org) — Machine learning
- [Plotly](https://plotly.com) — Interactive visualization

---

Built by **Shreyas Reddy**
