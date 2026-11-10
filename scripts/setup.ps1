<#
.SYNOPSIS
    DataMind v2 One-Command Windows Setup Script
.DESCRIPTION
    Creates .env from .env.example with freshly generated 64-char hex secrets,
    starts PostgreSQL 16 (pgvector) and Redis 7 via Docker Compose, enables pgvector,
    creates backend\.venv, installs Python dependencies, runs Alembic migrations,
    and installs Next.js frontend dependencies.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "==> DataMind v2 Setup (Windows PowerShell)" -ForegroundColor Cyan

# 1. Verify required tooling
foreach ($cmd in @("python", "node", "npm", "docker")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Required command '$cmd' was not found in PATH. Please install it first."
    }
}

# 2. Provision .env from .env.example with high-entropy secrets
$EnvExample = Join-Path $RepoRoot ".env.example"
$RootEnv = Join-Path $RepoRoot ".env"

if (-not (Test-Path $RootEnv)) {
    Copy-Item $EnvExample $RootEnv
    Write-Host "Created .env from .env.example" -ForegroundColor Green
}

$EnvInitScript = @"
from pathlib import Path
import secrets

env_path = Path(r"$RootEnv")
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
"@
python -c $EnvInitScript

# 3. Start PostgreSQL (pgvector) & Redis containers
Write-Host "==> Starting Docker PostgreSQL 16 (pgvector) & Redis 7..." -ForegroundColor Cyan
docker compose up -d

Write-Host "==> Waiting for PostgreSQL healthcheck..." -ForegroundColor Cyan
$pgReady = $false
for ($i = 0; $i -lt 30; $i++) {
    docker exec datamind_postgres pg_isready -U postgres -d postgres *> $null
    if ($LASTEXITCODE -eq 0) {
        $pgReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $pgReady) {
    throw "PostgreSQL container did not become ready in time. Check 'docker compose logs postgres'."
}

docker exec datamind_postgres psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;" *> $null

# 4. Create backend virtual environment & install dependencies
$VenvDir = Join-Path $RepoRoot "backend\.venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "==> Creating Python virtual environment in backend\.venv..." -ForegroundColor Cyan
    python -m venv $VenvDir
}

Write-Host "==> Installing backend Python dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
Push-Location (Join-Path $RepoRoot "backend")
try {
    & $VenvPython -m pip install -e ".[dev]"
    Write-Host "==> Running Alembic database migrations..." -ForegroundColor Cyan
    & (Join-Path $VenvDir "Scripts\alembic.exe") upgrade head
}
finally {
    Pop-Location
}

# 5. Ensure uploads directory exists
$UploadsDir = Join-Path $RepoRoot "backend\data\uploads"
if (-not (Test-Path $UploadsDir)) {
    New-Item -ItemType Directory -Path $UploadsDir -Force | Out-Null
}

# 6. Install frontend dependencies strictly inside frontend/
Write-Host "==> Installing frontend Node.js dependencies inside frontend\..." -ForegroundColor Cyan
Push-Location (Join-Path $RepoRoot "frontend")
try {
    npm install --legacy-peer-deps
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete! Launch DataMind v2 anytime with:" -ForegroundColor Green
Write-Host "  .\scripts\dev.ps1" -ForegroundColor Yellow

