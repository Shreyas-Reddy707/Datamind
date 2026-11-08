# DataMind v2 — Architecture Decision Record (ADR-001)

## 1. System Philosophy & Monorepo Layout
DataMind v2 transitions from a v1 Streamlit prototype to a decoupled, production multi-agent data intelligence platform:
- `backend/`: FastAPI (Async), SQLAlchemy 2.0 (Async), PostgreSQL 16 + `pgvector`, DuckDB OLAP engine, Redis 7 cache/broker, Taskiq background workers, LangGraph multi-agent brain.
- `frontend/`: Next.js 15 (App Router, React 19, TypeScript), Tailwind CSS, shadcn/ui, Zustand, Plotly.js.
- `docs/`: Technical specifications, architectural blueprints, schema contracts, and task roadmaps.
- `bruno/`: Version-controlled API and security test collection.

```
datamind/
├── .github/                  # CI/CD Workflows
├── docs/                     # Spec-driven Architecture, Schema, Security docs
├── bruno/                    # Bruno OpenAPI & Security abuse test collection
├── docker-compose.yml        # Zero-config PostgreSQL 16 (pgvector) + Redis 7
├── _legacy_v1/               # Preserved reference v1 logic & assets
├── backend/                  # FastAPI + SQLAlchemy 2.0 + DuckDB + LangGraph
│   ├── alembic/              # Alembic environment and version migration scripts
│   ├── app/
│   │   ├── api/              # Modular API routers and dependencies (deps.py)
│   │   ├── security/         # Argon2id, UploadGuard, RateLimiter, PromptGuard
│   │   ├── memory/           # Pattern learner, pgvector context, query cache
│   │   ├── llm/              # LiteLLM client & deterministic 768-d embeddings
│   │   ├── db/               # SQLAlchemy Base and async session management
│   │   ├── engine/           # DuckDB Parquet engine, Instant Responder, ML runner
│   │   ├── models/           # Declarative SQLAlchemy 2.0 models
│   │   ├── schemas/          # Pydantic v2 Create/Update/Response schemas
│   │   ├── agents/           # LangGraph graph, nodes, SchemaFirewallNode
│   │   └── workers/          # Taskiq asynchronous tasks and broker
│   └── tests/                # Pytest suites
└── frontend/                 # Next.js 15 (App Router) Anti-Vibecode UI
```

---

## 2. Container & Local Windows Host Topology
To minimize RAM usage and avoid slow WSL2 bind-mount file watchers on Windows:
- **Docker Compose Services (`docker-compose.yml`)**:
  - `postgres`: `pgvector/pgvector:pg16` bound to `5432:5432` (`POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=postgres`, named volume `datamind_pgdata`, `pg_isready -U postgres -d postgres` healthcheck).
  - `redis`: `redis:7-alpine` bound to `6379:6379` (named volume `datamind_redisdata`, `redis-cli ping` healthcheck).
- **Native Windows Host Processes**:
  - `ollama`: Native Windows GPU service at `http://localhost:11434` running `qwen2.5-coder:7b`.
  - `backend`: FastAPI (`uvicorn app.main:app --reload --port 8000`) + Taskiq worker.
  - `frontend`: Next.js 15 (`npm run dev -- --turbo` on `http://localhost:3000`).

---

## 3. Analytical OLAP Engine (DuckDB + Content-Addressed Parquet)
1. **Upload Guard & Validation**: Uploaded files (`.csv`, `.xlsx`, `.xls`, `.json`, `.parquet`) pass `UploadGuard` (magic bytes verification, 50MB size limit, 500,000 row cap, 500 column cap, 100,000 row limit for Excel).
2. **Content-Addressed Deduplication**: Computes SHA-256 digest of the payload. Inside an atomic `SELECT ... FOR UPDATE` transaction on `global_files`, the file is converted once to `data/uploads/<sha256>.parquet`. Multiple users uploading the identical dataset share one on-disk Parquet file with isolated user references in `user_files`.
3. **DuckDB Vectorized Execution**: DuckDB executes zero-copy queries directly over `<sha256>.parquet` and performs cross-file SQL joins across multiple authorized user files under 500MB RAM.

---

## 4. Cost-First AI Routing & Bounded LangGraph Brain
The system routes analytical queries through a cost-effective, deterministic 3-tier pipeline:
- **Tier 0 (Instant Responder — <25ms, $0)**:
  - Regex classifier matches exact query patterns (row counts, column listings, null rates, summary statistics, quartiles).
  - Translates queries directly to parameterized DuckDB SQL. Bypasses LLMs entirely.
- **Tier 1 (Quick Stream — <3s, $0 Local SLM)**:
  - LiteLLM streams focused responses from `ollama/qwen2.5-coder:7b` over Server-Sent Events (SSE) with minimal schema context.
- **Tier 2 & 3 (Deep Lab Pipeline — 5–15s, Bounded LangGraph)**:
  - Directed acyclic graph bounded by `max_steps=8`, `token_budget=6000`, and a `15s` timeout per node.
  - Nodes: `OrchestratorNode` -> (`SummaryAgent` | `AnalystAgent` | `VizAgent` | `DiagnosticAgent` -> `PredictAgent` | `CleaningAgent`) -> **`SchemaFirewallNode`**.
  - **`SchemaFirewallNode`**: Deterministically inspects generated SQL and analytical column references against DuckDB's live parquet schema. If an agent hallucinates a column name or invalid type, it routes back with the exact schema for self-correction.
  - **Self-Learning Memory Loop**: Post-response background worker extracts high correlations (>0.7), outliers (>3σ), and LLM insights, embeds them into `learned_patterns` (`Vector(768)`), and applies confidence decay on semantic retrieval.

---

## 5. Security & Isolation Invariants
- **BOLA / Multi-Tenant Isolation**: Every file, lab artifact, and chat message query enforces strict ownership: `WHERE id = :id AND user_id = :current_user.id`.
- **Argon2id & Rotating Session Tokens**: Passwords hashed with `pwdlib[argon2]`. 15-minute JWT access tokens paired with rotating `HttpOnly`, `Secure`, `SameSite=Lax` refresh token cookies.
- **Prompt Injection Defense**: Untrusted dataset metadata and sample rows are wrapped in cryptographic nonce delimiters: `<untrusted_dataset_sample nonce="...">...</untrusted_dataset_sample>`.
