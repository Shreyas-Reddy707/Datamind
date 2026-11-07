# DataMind v2 — PostgreSQL 16 + pgvector Schema Specification

All tables use `UUID` primary keys (`gen_random_uuid()`), `TIMESTAMPTZ` audit timestamps (`created_at`, `updated_at`), strict foreign keys with cascading where appropriate, and explicit B-tree / HNSW indexes managed exclusively via **Alembic**.

---

## 1. Organizations (`organizations`)
Multi-tenant root organization entity for RBAC and billing boundaries.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `name`: `VARCHAR(128)` (NOT NULL)
- `slug`: `VARCHAR(128)` (UNIQUE, NOT NULL, INDEX)
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- `updated_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`, `onupdate=func.now()`)

---

## 2. Users (`users`)
User identity and authentication records.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `org_id`: `UUID` (ForeignKey `organizations.id`, ON DELETE RESTRICT, NOT NULL, INDEX)
- `email`: `VARCHAR(255)` (UNIQUE, NOT NULL, INDEX)
- `password_hash`: `VARCHAR(255)` (NOT NULL) — Hashed with Argon2id
- `role`: `VARCHAR(32)` (NOT NULL, `default='member'`) — Enum: `owner`, `admin`, `member`, `guest`
- `failed_login_attempts`: `INT` (NOT NULL, `default=0`)
- `locked_until`: `TIMESTAMPTZ` (NULL) — 15-minute temporary lockout
- `is_active`: `BOOLEAN` (NOT NULL, `default=True`)
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- `updated_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`, `onupdate=func.now()`)
- Indexes: `ix_users_email` (UNIQUE), `ix_users_org_id`

---

## 3. User Sessions (`user_sessions`)
Rotating refresh tokens and session tracking for security.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `refresh_token_hash`: `CHAR(64)` (UNIQUE, NOT NULL, INDEX) — SHA256 hash of random token
- `ip_address_hash`: `VARCHAR(64)` (NULL) — Truncated/hashed IP for anti-tamper
- `user_agent`: `VARCHAR(512)` (NULL)
- `expires_at`: `TIMESTAMPTZ` (NOT NULL)
- `revoked_at`: `TIMESTAMPTZ` (NULL)
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes: `ix_user_sessions_refresh_token_hash` (UNIQUE), `ix_user_sessions_user_id`

---

## 4. Password Reset Tokens (`password_reset_tokens`)
High-entropy cryptographic tokens for secure password recovery.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `token_hash`: `CHAR(64)` (UNIQUE, NOT NULL, INDEX) — SHA256 of `secrets.token_urlsafe(32)`
- `expires_at`: `TIMESTAMPTZ` (NOT NULL)
- `used_at`: `TIMESTAMPTZ` (NULL)
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes: `ix_password_reset_tokens_token_hash` (UNIQUE), `ix_password_reset_tokens_user_id`

---

## 5. Global Files (`global_files`)
Content-addressed deduplicated storage layer for raw/parquet dataset storage.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `sha256_hash`: `CHAR(64)` (UNIQUE, NOT NULL, INDEX)
- `parquet_path`: `TEXT` (NOT NULL) — Local path: `data/uploads/<sha256>.parquet`
- `original_format`: `VARCHAR(16)` (NOT NULL) — `csv`, `xlsx`, `xls`, `json`, `parquet`
- `file_size_bytes`: `BIGINT` (NOT NULL)
- `row_count`: `INTEGER` (NOT NULL)
- `col_count`: `INTEGER` (NOT NULL)
- `schema_json`: `JSONB` (NOT NULL) — Column names, inferred DuckDB types, null counts
- `detected_domain`: `VARCHAR(64)` (NOT NULL, `default='generic'`) — e.g. `finance`, `healthcare`, `ecommerce`
- `ref_count`: `INTEGER` (NOT NULL, `default=1`) — Atomic counter for garbage collection
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes: `ix_global_files_sha256_hash` (UNIQUE)

---

## 6. User Files (`user_files`)
User-specific file reference and scoped metadata (BOLA security root).
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `org_id`: `UUID` (ForeignKey `organizations.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `global_file_id`: `UUID` (ForeignKey `global_files.id`, ON DELETE RESTRICT, NOT NULL, INDEX)
- `display_name`: `VARCHAR(255)` (NOT NULL)
- `cleaning_report_json`: `JSONB` (NULL) — Cleaned rows, imputed nulls, deduplicated keys
- `summary_profile_json`: `JSONB` (NULL) — Data health score, column stats, skewness
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- `updated_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`, `onupdate=func.now()`)
- Indexes:
  - `idx_user_files_user_created`: `(user_id, created_at DESC)`
  - `uq_user_files_user_global_display`: UNIQUE `(user_id, global_file_id, display_name)`

---

## 7. Analysis Memory (`analysis_memory`)
Agent forensic findings, evidence, implications, and interactive visualizations.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `user_file_id`: `UUID` (ForeignKey `user_files.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `agent_type`: `VARCHAR(32)` (NOT NULL) — `analyst`, `summary`, `diagnostic`, `cleaning`, `viz`
- `query_text`: `TEXT` (NOT NULL)
- `context_text`: `TEXT` (NULL)
- `finding_text`: `TEXT` (NOT NULL)
- `evidence_json`: `JSONB` (NULL) — Query stats, metrics, column correlations
- `implication_text`: `TEXT` (NULL)
- `plotly_spec_json`: `JSONB` (NULL) — Renderable Plotly.js chart configuration
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes:
  - `idx_analysis_memory_user_file`: `(user_id, user_file_id, created_at DESC)`

---

## 8. Learned Patterns (`learned_patterns`)
Self-learning pattern bank with vector embeddings and decay weighting.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `user_file_id`: `UUID` (ForeignKey `user_files.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `pattern_type`: `VARCHAR(32)` (NOT NULL) — `correlation`, `outlier`, `llm_insight`
- `insight_text`: `TEXT` (NOT NULL)
- `stat_metadata`: `JSONB` (NULL) — Involved columns, Pearson r, p-value, IQR
- `embedding`: `Vector(768)` (NULL) — pgvector representation for semantic retrieval
- `confidence_score`: `FLOAT` (NOT NULL, `default=1.0`)
- `helpful_votes`: `INTEGER` (NOT NULL, `default=0`)
- `unhelpful_votes`: `INTEGER` (NOT NULL, `default=0`)
- `last_accessed_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes:
  - `idx_learned_patterns_user_file`: `(user_id, user_file_id)`
  - `idx_learned_patterns_embedding_hnsw`: HNSW index on `embedding vector_cosine_ops`

---

## 9. Prediction History (`prediction_history`)
AutoML benchmark jobs, models, hyperparameters, and evaluation metrics.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `user_file_id`: `UUID` (ForeignKey `user_files.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `task_type`: `VARCHAR(32)` (NOT NULL) — `classification`, `regression`, `clustering`, `timeseries`
- `target_column`: `VARCHAR(128)` (NULL)
- `feature_columns`: `JSONB` (NOT NULL)
- `best_model_name`: `VARCHAR(64)` (NULL) — e.g. `RandomForestClassifier`, `XGBoost`
- `leaderboard_json`: `JSONB` (NULL) — Model comparison rankings and scores
- `feature_importance_json`: `JSONB` (NULL) — Feature weight rankings
- `diagnostics_json`: `JSONB` (NULL) — Confusion matrix, ROC-AUC, residuals
- `status`: `VARCHAR(32)` (NOT NULL, `default='queued'`) — `queued`, `running`, `completed`, `failed`
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes:
  - `idx_prediction_history_user_file`: `(user_id, user_file_id, created_at DESC)`

---

## 10. Chat History (`chat_history`)
Multi-tier conversational logs, agent telemetry, and lab artifact injection.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `user_file_id`: `UUID` (ForeignKey `user_files.id`, ON DELETE CASCADE, NOT NULL, INDEX)
- `role`: `VARCHAR(16)` (NOT NULL) — `user`, `assistant`, `system`
- `tier`: `SMALLINT` (NULL) — Tier 0 (Instant), Tier 1 (Quick SLM), Tier 2/3 (LangGraph)
- `message_text`: `TEXT` (NOT NULL)
- `latency_ms`: `INTEGER` (NULL)
- `lab_artifact_json`: `JSONB` (NULL) — Artifact payload for 1-click Inject to Lab
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`)
- Indexes:
  - `idx_chat_history_file_created`: `(user_file_id, created_at ASC)`

---

## 11. Audit Log (`audit_log`)
Immutable security and compliance event ledger.
- `id`: `UUID` (Primary Key, `default=uuid.uuid4`)
- `user_id`: `UUID` (ForeignKey `users.id`, ON DELETE SET NULL, NULL, INDEX)
- `event_type`: `VARCHAR(64)` (NOT NULL) — e.g. `auth.login`, `file.upload`, `bola.blocked`
- `resource_type`: `VARCHAR(64)` (NULL) — e.g. `user_file`, `chat`
- `resource_id`: `VARCHAR(64)` (NULL)
- `status_code`: `INTEGER` (NULL)
- `request_id`: `VARCHAR(64)` (NOT NULL)
- `ip_address`: `VARCHAR(64)` (NULL)
- `created_at`: `TIMESTAMPTZ` (NOT NULL, `server_default=func.now()`, INDEX)
- Indexes:
  - `idx_audit_log_user_created`: `(user_id, created_at DESC)`
  - `idx_audit_log_created_at`: `(created_at DESC)`
