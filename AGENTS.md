# DataMind v2 — Agent Operating Rules & Engineering Invariants

## 1. Project Identity & Scope
DataMind v2 is a decoupled, multi-agent analytical workspace and data intelligence platform:
- **Backend (`backend/`)**: Python 3.11+, FastAPI (Async), SQLAlchemy 2.0 (Async) + Alembic, PostgreSQL 16 (`pgvector`), DuckDB + Apache Parquet, Redis 7, Taskiq background workers, LangGraph + LiteLLM (`ollama/qwen2.5-coder:7b`).
- **Frontend (`frontend/`)**: Next.js 15 (App Router, TypeScript), Tailwind CSS, shadcn/ui, Zustand (`useWorkspaceStore`), Plotly.js (`react-plotly.js`).

## 2. Terminal & Environment Hygiene (Windows PowerShell)
- Active working directory: `C:\Users\shrey\Documents\Shreyas\Projects\DataMind`
- **Rule A (Global CLI/MCP Tools)**: NEVER run bare `npm install` in the repository root or `backend/`. Any global CLI/MCP package must use `npm install -g <pkg>` or `npx -y`. Node dependencies belong strictly inside `frontend/`.
- **Rule B (Python Dependencies)**: Install Python packages strictly inside `backend/.venv` (or active Conda env) using `pip` or `uv`.
- **Rule C (Zero-Config Docker Postgres)**: `docker-compose.yml` binds Postgres to `5432:5432` with `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=postgres`, and volume `datamind_pgdata` so the global `postgres` MCP and DBeaver inspect tables with zero config edits.

## 3. Non-Negotiable Coding & Migration Rules
1. **No Stubs or Loss of v1 Logic**: Before writing any v2 module, read the corresponding file in `_legacy_v1/` and port all domain prompts, regex rules, statistical thresholds, and ML logic. Never write `# TODO` or `pass`.
2. **Alembic Only**: Never use `Base.metadata.create_all()`. Every schema change requires an Alembic migration.
3. **OWASP Defaults**:
   - Passwords hashed with **Argon2id** (`pwdlib[argon2]`), 5-attempt lockout, 15-min JWT access tokens + rotating `HttpOnly`, `Secure`, `SameSite=Lax` refresh tokens.
   - Every dataset/chat/lab/prediction query MUST filter by ownership (`WHERE id = :id AND user_id = :current_user_id`).
   - Separate Pydantic `Create`, `Update`, and `Response` schemas (no mass assignment).
   - Standardized error envelope: `{"error_code": str, "message": str, "request_id": str}` with zero stack trace leaks.
4. **Anti-Vibecode Design System (No Figma Fallback)**:
   - Use Zinc/Slate surfaces (`#09090B` background, `#121215` panels, `#18181B` cards, `1px solid #27272A` borders, `#10B981` emerald semantic accent, `Geist Sans` UI font, `Geist Mono` data/SQL/metric font).
   - BANNED: `#000000` + neon purple gradients, glowing floating orbs, sparkle icons on headings, fake terminal windows, fake testimonials, em-dash spam, and "It's not X, it's Y" copy.