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
- `POST /api/v1/predict/{file_id}/run`: Enqueues Taskiq background AutoML training job.
- `GET /api/v1/predict/{file_id}/jobs/{job_id}`: Polls training progress and returns leaderboard, metrics, and feature importance.

---

## 3. Bruno Security Test Collection (`/bruno`)
The `/bruno` folder holds end-to-end tests for every endpoint group:
1. `01_happy_path.bru`: Standard 200/201 creation and query workflows.
2. `02_unauthenticated.bru`: Rejects requests missing `Authorization: Bearer <token>` with `401 Unauthorized`.
3. `03_bola_cross_user_idor.bru`: User B attempts to view, query, or delete User A's `file_id` -> returns `404 Not Found` (or `403 Forbidden`).
4. `04_invalid_schema_and_file_bomb.bru`: Tests fake `.csv` with `.exe` binary headers, nested payloads > 1MB, and negative pagination values -> returns `422 Unprocessable Entity` or `413 Payload Too Large`.
5. `05_rate_limit_exceeded.bru`: Bursts 60 requests in 5 seconds to test rate limiter -> returns `429 Too Many Requests`.
