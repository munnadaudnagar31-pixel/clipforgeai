#!/usr/bin/env pwsh
# ─────────────────────────────────────────────────────────────────
# ClipForge AI — Dev Environment Setup Script (Windows PowerShell)
# Run from:  C:\myexp\clipforge\backend\
# ─────────────────────────────────────────────────────────────────

Set-Location $PSScriptRoot

Write-Host "`n🚀 ClipForge AI — Setting up virtual environment..." -ForegroundColor Cyan

# ── Step 1: Create .venv ──────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "📦 Creating .venv..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "✅ .venv already exists" -ForegroundColor Green
}

# ── Step 2: Activate ──────────────────────────────────────────────
$activate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "❌ Could not find .venv\Scripts\Activate.ps1 — is Python installed?" -ForegroundColor Red
    exit 1
}

# ── Step 3: Upgrade pip ───────────────────────────────────────────
Write-Host "`n📦 Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel

# ── Step 4: Install CORE packages (required to start server) ──────
Write-Host "`n📦 Installing core dependencies..." -ForegroundColor Yellow
pip install `
    fastapi==0.111.0 `
    "uvicorn[standard]==0.30.1" `
    python-multipart==0.0.9 `
    "python-jose[cryptography]==3.3.0" `
    "passlib[bcrypt]==1.7.4" `
    bcrypt==4.1.3 `
    sqlalchemy==2.0.30 `
    aiosqlite==0.20.0 `
    pydantic==2.7.4 `
    pydantic-settings==2.3.4 `
    email-validator==2.1.1 `
    httpx==0.27.0 `
    aiofiles==23.2.1 `
    python-dotenv==1.0.1

# ── Step 5: Install ALL packages (full install) ───────────────────
Write-Host "`n📦 Installing all packages from requirements.txt..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host "`n✅ Installation complete!" -ForegroundColor Green

# ── Step 6: Verify the server boots ──────────────────────────────
Write-Host "`n🔍 Verifying imports..." -ForegroundColor Yellow
python -c "import fastapi, sqlalchemy, aiosqlite, jose, passlib, pydantic; print('✅ All core imports OK')"

# ── Done ──────────────────────────────────────────────────────────
Write-Host @"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅  Setup complete!

To activate the environment in future terminal sessions:
  .\.venv\Scripts\Activate.ps1

To start the API server:
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API docs (Swagger UI):
  http://localhost:8000/api/docs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"@ -ForegroundColor Cyan
