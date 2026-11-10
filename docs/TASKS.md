# DataMind v2 — Phased Implementation & Verification Checklist

> **Execution Rule**: Complete ONE phase at a time. Run the Phase Verification Gate and stop for confirmation before starting the next phase.

- [x] **Phase 0: Git Branching, `_legacy_v1` Archive & Spec Creation**
  - [x] Check `git status` and `git branch -a`. Create/checkout clean branch `feat/v2-architecture` from `main`.
  - [x] Create `_legacy_v1/` and use `git mv` to archive v1 legacy files (`app.py`, `config.py`, `database.py`, `requirements.txt`, `datamind/`).
  - [x] Inspect `_legacy_v1/database.py` and `_legacy_v1/config.py` to preserve 100% of schema and domain configuration.
  - [x] Create and refine 5 foundational specification files:
    - [x] `AGENTS.md` (Operating rules, Windows PowerShell hygiene, OWASP invariants, and Zinc/Slate `#09090B`/`#18181B`/`#10B981` + `Geist Sans`/`Geist Mono` Anti-Vibecode tokens).
    - [x] `docs/ARCHITECTURE.md` (Hybrid Windows architecture: Docker Postgres pg16 + Redis 7, native Ollama, DuckDB Parquet OLAP engine, bounded LangGraph `max_steps=8` with `SchemaFirewallNode`).
    - [x] `docs/SCHEMA.md` (All 10+ tables with UUID PKs, FK cascades, and B-tree/HNSW indexes).
    - [x] `docs/API_AND_SECURITY.md` (FastAPI `/api/v1/*` contracts, Argon2id, BOLA dependencies, UploadGuard, PromptGuard, and `/bruno` test plan).
    - [x] `docs/TASKS.md` (Phased roadmap from Phase 0 to Phase 5).

- [x] **Phase 1: Zero-Config Docker Compose, SQLAlchemy 2.0 & Alembic Migration**
  - [x] Create `docker-compose.yml` (`postgres` `pgvector:pg16` on `5432:5432` with `datamind_pgdata` + `redis:7-alpine` on `6379:6379` with `datamind_redisdata`).
  - [x] Create `.env.example`, `.gitignore`, and `.pre-commit-config.yaml` (`ruff`, `pyright`, `gitleaks`, `bandit`).
  - [x] Scaffold `backend/`:
    - [x] `backend/pyproject.toml` with dependencies.
    - [x] `backend/app/config.py` using `pydantic-settings` with fail-fast secret validation.
    - [x] `backend/app/db/base.py` and `backend/app/db/session.py` (AsyncEngine + `async_sessionmaker`).
    - [x] `backend/app/models/` implementing all 10+ tables from `docs/SCHEMA.md` with explicit indexes and foreign keys.
  - [x] Start Docker containers (`docker compose up -d`), enable vector extension (`CREATE EXTENSION IF NOT EXISTS vector;`), generate initial Alembic migration (`0001_initial_schema.py`), and run `alembic upgrade head`.
  - [x] **Gate 1**: Verify all live tables using `postgres` MCP server, explain 2 senior engineering trade-offs, and STOP for DBeaver inspection.

- [x] **Phase 2: OWASP Security Core, Auth, DuckDB Parquet Engine & Bruno Tests**
  - [x] Port and upgrade `backend/app/security/` (`auth.py` with Argon2id + rotating cookies, `upload_guard.py`, `sanitizer.py`, `rate_limiter.py`, `prompt_guard.py`, `error_handler.py`).
  - [x] Build `backend/app/engine/parquet_ingestor.py`, `duckdb_manager.py` (single + multi-file SQL joins), and `instant_responder.py` (<25ms Tier 0 stats).
  - [x] Implement `/health/*`, `/api/v1/auth/*`, and `/api/v1/files/*` routers + `/bruno` Auth & Files security tests.
  - [x] **Gate 2**: Run `pytest backend/tests/test_phase2_security_and_engine.py` and execute Bruno happy/abuse tests.

- [x] **Phase 3: Bounded LangGraph Multi-Agent Brain, ML Worker & Self-Learning Memory**
  - [x] Port `app/llm/client.py` (LiteLLM + Ollama `qwen2.5-coder:7b`), `app/memory/*` (`learner.py`, `context_builder.py`, `query_cache.py`, `feedback.py` with `pgvector`).
  - [x] Port `app/engine/ml_runner.py`, `chart_builder.py`, and Taskiq background workers (`app/workers/tasks.py`).
  - [x] Implement `app/agents/graph.py` (3-Tier Classifier, Orchestrator, Summary, Analyst, Viz, Diagnostic, Predict, Cleaning, and `SchemaFirewallNode`).
  - [x] Implement `/api/v1/chat/*`, `/api/v1/lab/*`, and `/api/v1/predict/*` SSE & REST routes + Bruno tests.
  - [x] **Gate 3**: Run `pytest` on Schema Firewall, Tier 1-3 chat streaming, and ML benchmarking.

- [x] **Phase 4: Next.js 15 Anti-Vibecode Workspace UI & Technical SEO**
  - [x] Scaffold `frontend/` with Zinc/Slate CSS variables (`globals.css`), `Geist Sans`/`Geist Mono`, and Zustand `useWorkspaceStore`.
  - [x] Build Public Landing Page, `/terms`, `/privacy`, `sitemap.xml`, `robots.txt`, `/llms.txt`, Auth pages, and `/dashboard` (`My Files` + deduplication metrics).
  - [x] Build 3-Pane IDE (`/workspace/[fileId]`): `LeftPanel` (file controls + multi-file join selector), `CenterLab` (Overview/Cleaning, Forensic Cards, Plotly.js Canvas, Prediction Leaderboard, PDF Export), and `RightChat` (SSE stream + 1-click **"Inject to Lab"**).
  - [x] **Gate 4**: Run `npm run typecheck` (0 errors), `npm run build` (13/13 static/dynamic routes compiled cleanly), and verified backend pytest suite (20 passed).

- [x] **Phase 5: Plain-English Polish, `_legacy_v1` Removal & Final Verification**
  - [x] Synchronize plain-English UX copy across landing page, SEO docs (`llms.txt`, `layout.tsx`), auth pages, dashboard, sidebar, 4 workspace tabs, and AI Assistant chat drawer.
  - [x] Replace raw SQL sandbox with no-code **Smart Tables & Pivot** (`SmartPivotStudio`) supporting plain-English queries, 1-click presets, visual group/filter/metric builder, multi-file visual join, CSV export, and 1-click chart conversion.
  - [x] Run `ruff`, `pytest`, `npm run typecheck`, `npm run build`, and Playwright end-to-end verification.
  - [x] Remove `_legacy_v1/` archive and update `README.md` for DataMind v2.
