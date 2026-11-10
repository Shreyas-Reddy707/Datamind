# DataMind v2

**No-Code Spreadsheet Insights, Interactive 2D/3D Charts, Smart Pivot Tables & What-If Predictions**

*Upload CSV, Excel (`.xlsx`/`.xls`), JSON, or Parquet files and get plain-English insights, custom summary tables, interactive charts, and predictive simulations — without writing a single line of code.*

---

## Key Capabilities

### 4-Tab Interactive Workspace (`/workspace/[fileId]`)
1. **Overview & Data**: Automatic **Data Quality Score** (completeness, missing cells, duplicate checks), suggested cleanup actions, multi-sheet Excel switcher, and instant row search & browsing.
2. **Insights & Charts**: Automated anomaly and correlation discoveries structured cleanly (*Background -> What We Found -> Data Proof -> What It Means / Next Step*), paired with an embedded **Interactive Chart Studio** supporting 2D & 3D Plotly charts.
3. **Predict & Simulate**: Pick any target column to predict. Automatically excludes post-outcome leakage columns, benchmarks multiple Scikit-Learn models (`classification`, `regression`, `clustering`, `timeseries`), ranks top driving factors, and lets you adjust real-time sliders in the **What-If Outcome Simulator**.
4. **Smart Tables & Pivot**: Ask for summary tables in plain English, build custom groupings/calculations/filters visually, combine multiple files via Visual Join, download CSVs, or convert any table directly into a chart (with an optional collapsed SQL view for power users).

### Ask DataMind AI Assistant
- **Dual-Engine Transparency**: Automatically streams generative answers via local **Ollama (`qwen2.5-coder:7b`)** when running, and falls back in milliseconds to the built-in **Minimal Mode (DuckDB)** deterministic engine when offline.
- **Agentic Workspace Control**: Understands navigation and action commands directly from chat (`switch_tab`, `switch_file`, `switch_sheet`, `update_chart`, `run_automl`).
- **Schema Verification & Persistent Memory**: Grounded strictly against verified dataset columns with `pgvector` pattern recall and per-user/per-file chat history.

---

## Architecture & Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend** | Next.js 15 (App Router, TypeScript), React 19, Tailwind CSS, Zustand, Plotly.js, Three.js / R3F |
| **Backend API** | Python 3.11+, FastAPI (Async), SQLAlchemy 2.0 (Async), Alembic, Pydantic Settings |
| **Analytics & ML** | DuckDB (in-process read-only Parquet OLAP), Pandas, NumPy, Scikit-Learn, Taskiq |
| **Database & Cache** | PostgreSQL 16 (`pgvector` 768-D embeddings), Redis 7 |
| **AI Engine** | Direct `httpx` local Ollama (`/api/chat`, `/api/embeddings`, `/api/tags`) + deterministic DuckDB fallback |
| **Security** | Argon2id password hashing, 5-attempt lockout, 15-min JWT + rotating `HttpOnly` refresh cookies, BOLA ownership checks, magic-byte `UploadGuard`, `PromptGuard` |

---

## Project Structure

```text
Datamind/
├── backend/
│   ├── alembic/                  # PostgreSQL schema migrations
│   ├── app/
│   │   ├── agents/               # 3-Tier Classifier & bounded LangGraph reasoning graph
│   │   ├── api/v1/               # FastAPI routers (auth, files, lab, predict, chat, memory)
│   │   ├── db/                   # Async SQLAlchemy engine & session management
│   │   ├── engine/               # DuckDBManager, InstantResponder, ParquetIngestor, ChartBuilder, MLRunner
│   │   ├── llm/                  # Direct Ollama HTTP client + offline circuit breaker
│   │   ├── memory/               # pgvector semantic pattern learner, context builder, Redis query cache
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── schemas/              # Pydantic Create/Update/Response schemas
│   │   ├── security/             # Argon2id auth, rate limiter, upload guard, prompt guard
│   │   └── workers/              # Taskiq background workers
│   ├── tests/                    # Backend pytest integration & security suite
│   └── pyproject.toml
├── frontend/
│   ├── public/                   # llms.txt & static assets
│   └── src/
│       ├── app/                  # Next.js App Router pages (/, /login, /register, /dashboard, /workspace/[fileId], /settings, /account, /terms, /privacy)
│       ├── components/           # Workspace tabs (CenterLab, SmartPivotStudio, PredictionLab, LeftPanel, RightChat, EmbeddedPlotlyStudio, PlotlyCanvas) & 3D visuals
│       ├── lib/                  # Typed API client with JWT auto-refresh & types
│       └── store/                # Zustand workspace store
├── bruno/                        # API test collection
├── docs/                         # Architecture, Schema, Security, and Task specifications
├── docker-compose.yml            # PostgreSQL 16 (pgvector) + Redis 7
└── .env.example                  # Environment variable template
```

---

## Quickstart (Windows + Docker)

### 1. Prerequisites
- **Docker Desktop** (for PostgreSQL 16 `pgvector` on `5432` and Redis 7 on `6379`)
- **Python 3.11+**
- **Node.js 20+**
- **Ollama** *(optional for generative AI responses; built-in DuckDB engine works even when offline)*:
  ```powershell
  ollama pull qwen2.5-coder:7b
  ollama serve
  ```

### 2. Start Infrastructure & Configure Environment
```powershell
copy .env.example .env
docker compose up -d
```

### 3. Backend Setup & Migrations
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

*(Optional background worker for async jobs)*:
```powershell
cd backend
.venv\Scripts\taskiq.exe worker app.workers.broker:broker
```

### 4. Frontend Setup
```powershell
cd frontend
npm install
npm run dev -- -p 3000
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Verification & Testing

### Backend Lint & Pytest
```powershell
backend\.venv\Scripts\ruff check backend/app backend/tests
backend\.venv\Scripts\pytest.exe backend/tests/ -v
```

### Frontend Typecheck & Production Build
```powershell
cd frontend
npm run typecheck
npm run build
```

---

## Supported File Limits
- **Formats**: `.csv`, `.xlsx`, `.xls`, `.json`, `.parquet` (multi-sheet Excel workbooks supported with live sheet switching)
- **Limits**: 50 MB max upload size · 500,000 rows (`100,000` rows/sheet for Excel) · 500 columns · 512 MB DuckDB memory limit with `enable_external_access = false`
