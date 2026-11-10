#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> DataMind v2 Setup (macOS / Linux)"

# 1. Verify required tooling
for cmd in python3 node npm docker; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: Required command '$cmd' was not found in PATH." >&2
    exit 1
  fi
done

# 2. Provision .env from .env.example with fresh 64-char hex secrets
if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example"
fi

python3 - <<'PY'
from pathlib import Path
import secrets

env_path = Path(".env")
text = env_path.read_text(encoding="utf-8")
placeholder = "CHANGE_ME_GENERATE_WITH_SECRETS_TOKEN_HEX_32"

lines = []
changed = False
for line in text.splitlines():
    if line.startswith("JWT_SECRET=") and placeholder in line:
        lines.append(f"JWT_SECRET={secrets.token_hex(32)}")
        changed = True
    elif line.startswith("SESSION_SECRET=") and placeholder in line:
        lines.append(f"SESSION_SECRET={secrets.token_hex(32)}")
        changed = True
    else:
        lines.append(line)

if changed:
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Generated unique 64-char hex secrets in .env")
else:
    print("Using existing secrets in .env")
PY

# 3. Start PostgreSQL (pgvector) & Redis containers
echo "==> Starting Docker PostgreSQL 16 (pgvector) & Redis 7..."
docker compose up -d

echo "==> Waiting for PostgreSQL healthcheck..."
PG_READY=0
for _ in $(seq 1 30); do
  if docker exec datamind_postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; then
    PG_READY=1
    break
  fi
  sleep 2
done
if [ "$PG_READY" -ne 1 ]; then
  echo "Error: PostgreSQL container did not become ready in time." >&2
  exit 1
fi

docker exec datamind_postgres psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null

# 4. Create backend virtual environment & install dependencies
if [ ! -x "backend/.venv/bin/python" ]; then
  echo "==> Creating Python virtual environment in backend/.venv..."
  python3 -m venv "backend/.venv"
fi

echo "==> Installing backend Python dependencies..."
"backend/.venv/bin/python" -m pip install --upgrade pip
(
  cd backend
  "./.venv/bin/python" -m pip install -e ".[dev]"
  echo "==> Running Alembic database migrations..."
  "./.venv/bin/alembic" upgrade head
)

mkdir -p "backend/data/uploads"

# 5. Install frontend dependencies strictly inside frontend/
echo "==> Installing frontend Node.js dependencies inside frontend/..."
(
  cd frontend
  npm install --legacy-peer-deps
)

echo ""
echo "Setup complete! Start backend & frontend in separate terminals:"
echo "  cd backend && ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000"
echo "  cd frontend && npm run dev -- -p 3000"

