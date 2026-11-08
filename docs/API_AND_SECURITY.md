# DataMind v2 — API Contracts, OWASP Hardening & Bruno Test Spec

## 1. Global Security Middleware & Dependencies
- **Fail-Fast Configuration (`app/config.py`)**: `pydantic-settings` validates `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` (minimum 32 bytes), `SESSION_SECRET`, and `OLLAMA_BASE_URL` on boot. The application refuses to start if any secret is missing or insecure.
- **Strict CORS & Defensive Headers**:
  - Explicit origin whitelist (`http://localhost:3000`). Never `allow_origins=["*"]` when `allow_credentials=True`.
  - Headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Referrer-Policy: strict-origin-when-cross-origin`.
  - File downloads are served with `Content-Security-Policy: sandbox; default-src 'none'`.
- **Payload Limits & Pagination Guard**:
  - Global JSON request body capped at `1MB` (`413 Payload Too Large`).
  - All paginated endpoints enforce `limit: int = Query(20, ge=1, le=100)` and `offset: int = Query(0, ge=0)`.
- **BOLA Ownership Dependency (`get_authorized_user_file`)**:
  - Every file/chat/lab endpoint depends on `get_authorized_user_file(file_id, current_user, db)`.
  - Executes `SELECT * FROM user_files WHERE id = :file_id AND user_id = :current_user.id`.
  - Throws `404 Not Found` (or `403 Forbidden`) and logs a security violation to `audit_log` if an unauthorized file access is attempted.
- **UploadGuard**:
  - Validates file magic bytes (rejects fake extensions).
  - Maximum file size: 50MB. Max rows: 500,000 (100,000 for `.xlsx`/`.xls`). Max columns: 500.
  - Rejects executable files, scripts, and active HTML/SVG content.
- **PromptGuard**:
  - Wraps all raw user data and dataset previews inside high-entropy delimiter tags:
    `<untrusted_dataset_sample nonce="...">...</untrusted_dataset_sample>`.
  - Blocks prompt injection overrides, system prompt leak attempts, and privilege escalation patterns.
- **Error Sanitization**:
  - Uniform JSON error envelope: `{"error_code": "RESOURCE_NOT_FOUND", "message": "File not found", "request_id": "req_xyz"}`.
  - Zero internal stack traces or database driver exceptions leaked to the client.

---

## 2. API Endpoints (`/api/v1`)

### Health & Observability
- `GET /health/live`: Container liveness check.
- `GET /health/ready`: Deep readiness probe verifying Postgres (`SELECT 1`), Redis (`PING`), and Ollama connection.

### Authentication (`/api/v1/auth`)
- `POST /api/v1/auth/register`: Creates organization + user with Argon2id password hash.
- `POST /api/v1/auth/login`: Authenticates credentials, checks failed attempts / lockouts, issues 15-min JWT access token, and sets rotating `HttpOnly` refresh cookie.
- `POST /api/v1/auth/refresh`: Rotates refresh token (detects reuse/tampering) and issues fresh access token.
- `POST /api/v1/auth/logout`: Revokes active refresh token in database.
- `POST /api/v1/auth/guest`: Spawns temporary guest user with isolated workspace and 24-hour TTL.
- `POST /api/v1/auth/password-reset/request`: Generates 128-bit reset token and logs to `audit_log`.
- `POST /api/v1/auth/password-reset/confirm`: Validates token hash and resets password.

### Datasets & OLAP Engine (`/api/v1/files`)
- `POST /api/v1/files/upload`: Multipart upload with `Idempotency-Key` header. Validates magic bytes, computes SHA-256, converts to Parquet under `SELECT ... FOR UPDATE`, and returns `user_file` record.
- `GET /api/v1/files`: Returns paginated list of user's files with deduplication metrics.
- `GET /api/v1/files/{file_id}`: Fetches file schema, preview rows, summary metrics, and data health score.
- `DELETE /api/v1/files/{file_id}`: Removes user reference. Atomically decrements `global_files.ref_count` and cleans on-disk Parquet if `ref_count == 0`.
- `POST /api/v1/files/join-preview`: Executes multi-file DuckDB SQL JOIN across 2+ authorized user files.

### Multi-Agent Chat & SSE Stream (`/api/v1/chat`)
- `POST /api/v1/chat/{file_id}/stream`: Server-Sent Events (SSE) streaming analytical responses.
  - Event types: `tier_detected`, `agent_status`, `token`, `lab_artifact`, `done`.
- `GET /api/v1/chat/{file_id}/history`: Returns message history capped at 500 messages.
- `POST /api/v1/chat/patterns/{pattern_id}/feedback`: Records user helpful/unhelpful votes and adjusts pattern confidence score.

### Forensic Lab (`/api/v1/lab`)
- `GET /api/v1/lab/{file_id}/overview`: Returns dataset overview, missing value analysis, and health indicators.
- `POST /api/v1/lab/{file_id}/analyze`: Triggers Forensic Briefing (Finding, Evidence, Implication).
- `POST /api/v1/lab/{file_id}/visualize`: Generates interactive Plotly.js chart specification.
- `GET /api/v1/lab/{file_id}/export-pdf`: Exports executive analytical briefing report.

### Predictive Modeling (`/api/v1/predict`)
- `POST /api/v1/predict/{file_id}/diagnose`: Evaluates dataset feasibility for ML missions (`PredictDiagnoseRequest` body with optional `target_col`). Returns data readiness diagnostics (`can_proceed`, `blockers`, `warnings`, `suggested_target`, `target_info`, `row_count`, `column_count`).
- `POST /api/v1/predict/{file_id}/run`: Enqueues Taskiq background AutoML training job (`PredictRunRequest` body with optional `target_col` and `task_type`). Includes smart cache deduplication.
- `GET /api/v1/predict/{file_id}/jobs/{job_id}`: Polls training progress and returns leaderboard, metrics, and feature importance.
- `GET /api/v1/predict/{file_id}/history`: Returns historical prediction benchmark runs for this dataset.

---

## 3. Bruno Security Test Collection (`/bruno`)
The `/bruno` folder holds functional HTTP request definitions and manual API smoke-test probes organized by endpoint groups (dynamic multi-request rate-limiting bursts and cross-tenant BOLA isolation guarantees are proven in the automated pytest suite):

### Auth & Rate Limiting (`bruno/auth/`)
- `01_register_login.bru`: User registration, login, JWT access token issuance, and rotating refresh cookie validation.
- `02_unauthenticated.bru`: Verifies that requests missing `Authorization: Bearer <token>` return `401 Unauthorized`.
- `03_rate_limit.bru`: Probes login with failed credentials and asserts response status in `[401, 403, 429]`. (Full sliding-window rate limiting bursts are verified in pytest).

### Dataset Storage & BOLA Security (`bruno/files/`)
- `01_upload_and_list.bru`: Multipart upload, content-addressed Parquet conversion, deduplication, and listing.
- `02_bola_idor.bru`: Probes file retrieval with a non-existent or foreign UUID and asserts rejection with `404 Not Found` (`RESOURCE_NOT_FOUND`). (Cross-user BOLA isolation between real distinct accounts is verified in pytest).
- `03_malicious_upload.bru`: UploadGuard validation rejecting active executables and invalid magic bytes (`400 Bad Request`).

### Multi-Agent Chat (`bruno/chat/`)
- `01_chat_stream_tier1.bru`: Validates Server-Sent Events (SSE) streaming and event envelope types.
- `02_chat_history.bru`: Validates conversation history retrieval capped at 500 messages.
- `03_pattern_feedback.bru`: Submits thumbs-up/down user feedback adjusting pattern confidence scores.
- `04_chat_bola_unauthorized.bru`: Ensures cross-tenant chat attempts are rejected with `404 Not Found`.

### Forensic Lab (`bruno/lab/`)
- `01_lab_overview.bru`: Verifies dataset overview dossier, schema, and DuckDB data profile generation.
- `02_lab_visualize.bru`: Validates dark-mode Plotly specification generation with 2,000-row sampling.
- `03_lab_analyze.bru`: Generates forensic briefing finding and persists into `analysis_memory`.
- `04_lab_export_pdf.bru`: Exports executive analytical briefing report in structured markdown.

### Predictive Modeling & AutoML (`bruno/predict/`)
- `01_predict_diagnose.bru`: Tests dataset ML viability diagnosis with blockers and target detection.
- `02_predict_run.bru`: Validates ML mission triggering and atomic smart cache deduplication.
- `03_predict_invalid_target.bru`: Validates 422 error rejection on unviable or invalid target columns.
- `04_predict_job_status.bru`: Polls training status, model leaderboard, and feature importances.
