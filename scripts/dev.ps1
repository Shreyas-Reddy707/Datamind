<#
.SYNOPSIS
    DataMind v2 1-Command Windows Dev Launcher
.DESCRIPTION
    Ensures Docker PostgreSQL & Redis are running, then starts both the
    FastAPI backend (http://127.0.0.1:8000) and Next.js frontend (http://localhost:3000).
    Press Ctrl+C to stop both servers cleanly.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython) -or -not (Test-Path (Join-Path $RepoRoot ".env"))) {
    throw "Environment not initialized yet. Run '.\scripts\setup.ps1' first."
}

Write-Host "==> Ensuring Docker Postgres & Redis containers are running..." -ForegroundColor Cyan
docker compose up -d

$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

Write-Host "==> Starting FastAPI Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
$BackendProc = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -NoNewWindow

Write-Host "==> Starting Next.js Frontend on http://localhost:3000 ..." -ForegroundColor Green
$FrontendProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "-p", "3000" `
    -WorkingDirectory $FrontendDir `
    -PassThru `
    -NoNewWindow

Write-Host ""
Write-Host "DataMind v2 is launching:" -ForegroundColor Cyan
Write-Host "  Workspace UI : http://localhost:3000" -ForegroundColor White
Write-Host "  Backend API  : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Press Ctrl+C to stop both services." -ForegroundColor DarkGray
Write-Host ""

try {
    while (-not $BackendProc.HasExited -and -not $FrontendProc.HasExited) {
        Start-Sleep -Milliseconds 500
    }
}
finally {
    if ($BackendProc -and -not $BackendProc.HasExited) {
        Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($FrontendProc -and -not $FrontendProc.HasExited) {
        Stop-Process -Id $FrontendProc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "==> Stopped DataMind v2 dev servers." -ForegroundColor Yellow
}

