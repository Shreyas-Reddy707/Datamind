# DataMind v2

**No-Code Spreadsheet Insights, Interactive 3D Charts, Smart Pivot Tables & What-If Predictions**

*Upload CSV, Excel (`.xlsx`/`.xls`), JSON, or Parquet files and get plain-English insights, custom summary tables, interactive 2D/3D charts, and predictive simulations — without writing a single line of code.*

Built by **Shreyas Reddy**.

---

## What is DataMind v2?

DataMind v2 is a private, local-first analytical workspace designed for non-technical operators and data teams alike. Instead of juggling spreadsheets, BI tools, and SQL consoles, every uploaded dataset opens into a unified **4-Tab No-Code Workspace** paired with an **AI Assistant Drawer**:

1. **Overview & Data**: Instant **Data Quality Score** (completeness, empty cells, duplicate detection), suggested cleanup actions, multi-sheet Excel switching, and fast row search & browsing.
2. **Insights & Charts**: Automatically discovers key patterns, outliers, and relationships explained clearly (*Background → What We Found → Data Proof → What It Means / Next Step*), linked directly to an interactive 2D & 3D Plotly chart studio.
3. **Predict & "What-If" Simulator**: Pick any column to predict (such as cancellations, price, or sales). DataMind automatically blocks post-outcome data leakage, compares multiple Scikit-Learn models, explains top driving factors, and lets you adjust real-time sliders to simulate future outcomes.
4. **Smart Tables & Pivot**: Ask for summary tables in plain English, pick visual groupings, metrics, and filters, combine multiple uploaded files visually, download CSVs, or convert any table directly into a chart with one click.
5. **Ask DataMind AI Assistant**: Chat naturally about your file—answers come with verified numbers even offline (**Minimal Mode via DuckDB**), or stream generative explanations when local **Ollama (`qwen2.5-coder:7b`)** is running—plus executes workspace commands (`switch tabs`, `plot charts`, `run predictions`).

---

## 2-Minute Quickstart (One Command)

### Prerequisites
- **Docker Desktop** (for PostgreSQL 16 `pgvector` and Redis 7)
- **Python 3.11+**
- **Node.js 20+**
- **Ollama** *(optional for generative chat explanations; DataMind's DuckDB engine works fully offline)*:
  ```powershell
  ollama pull qwen2.5-coder:7b
  ollama serve
  ```

### Windows (PowerShell)
```powershell
git clone https://github.com/Shreyas-Reddy707/Datamind.git
cd Datamind
.\scripts\setup.ps1
.\scripts\dev.ps1     # Opens http://localhost:3000
```

### macOS / Linux
```bash
git clone https://github.com/Shreyas-Reddy707/Datamind.git
cd Datamind
bash scripts/setup.sh
```
Then start the backend and frontend in separate terminals:
```bash
cd backend && ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- -p 3000
```

Visit **[http://localhost:3000](http://localhost:3000)** (API docs at `http://127.0.0.1:8000/docs`).

---

## Architecture & Tech Stack

| Layer | Technology |
| --- | --- |
| **Frontend** | Next.js 15 (App Router, TypeScript), React 19, Tailwind CSS, Zustand, Plotly.js, Three.js / R3F |
| **Backend API** | Python 3.11+, FastAPI (Async), SQLAlchemy 2.0 (Async), Alembic, Pydantic Settings |
| **OLAP & AutoML** | DuckDB (read-only Parquet engine), Pandas, NumPy, Scikit-Learn, Taskiq |
| **Database & Cache** | PostgreSQL 16 (`pgvector` 768-D embeddings), Redis 7 |
| **AI Engine** | Direct `httpx` local Ollama (`/api/chat`, `/api/embeddings`, `/api/tags`) + deterministic DuckDB fallback |
| **Security** | Argon2id password hashing, 5-attempt lockout, 15-min JWT + rotating `HttpOnly` refresh cookies, BOLA ownership checks, magic-byte `UploadGuard`, `PromptGuard` |

---

## Repository Structure

```text
Datamind/
├── backend/                # FastAPI + LangGraph + DuckDB + Taskiq
│   ├── alembic/            # PostgreSQL schema migrations
│   ├── app/                # Routers, security core, DuckDB/ML engines, LLM client
│   └── tests/              # Pytest unit, security & API integration suite
├── frontend/               # Next.js 15 Spatial 3D Workspace UI
│   ├── public/             # llms.txt & static metadata
│   └── src/                # App Router pages, Workspace tabs & Zustand store
├── bruno/                  # API & OWASP security test collection
├── docs/                   # Architecture, Schema, Security & Roadmap specs
├── assets/                 # Branding assets
├── scripts/                # setup.ps1, setup.sh, dev.ps1 quickstart launchers
├── .env.example            # Safe configuration template (no real secrets)
├── .gitignore              # Excludes .env, uploads/, *.parquet, caches & logs
├── .pre-commit-config.yaml # Ruff, Pyright, Gitleaks, Bandit hooks
├── AGENTS.md               # Engineering & security invariants
├── docker-compose.yml      # Zero-config PostgreSQL 16 (pgvector) + Redis 7
├── LICENSE                 # MIT License
└── README.md
```

---

## Verification & Testing

```powershell
# Backend lint & test suite
backend\.venv\Scripts\ruff check backend/app backend/tests
backend\.venv\Scripts\pytest.exe backend/tests/ -v

# Frontend typecheck & production build
cd frontend
npm run typecheck
npm run build
```

---

## Supported File Formats & Safety Limits
- **Formats**: `.csv`, `.xlsx`, `.xls`, `.json`, `.parquet` (multi-sheet Excel workbooks supported with live sheet switching)
- **Limits**: 50 MB max upload size · 500,000 rows (`100,000` rows/sheet for Excel) · 500 columns · 512 MB DuckDB memory limit with `enable_external_access = false`

---

## License
Released under the [MIT License](LICENSE). Built by **Shreyas Reddy**.
