<#
.SYNOPSIS
    Bonita 本地开发一键启动脚本
.DESCRIPTION
    启动三个服务（各开一个独立终端窗口）：
      1. FastAPI 后端 (端口 8000)
      2. Celery Worker (后台任务)
      3. Vite 前端 (端口 3000)
    如果缺少依赖会自动安装。按 Ctrl+C 分别关闭各窗口即可停止。
.PARAMETER SkipInstall
    跳过依赖检查和安装步骤，直接启动
.EXAMPLE
    .\dev.ps1
    .\dev.ps1 -SkipInstall
#>

param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend  = Join-Path $RepoRoot "backend"
$Frontend = Join-Path $RepoRoot "frontend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

function Write-Step($msg) { Write-Host "`n[dev] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[dev] $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "[dev] $msg" -ForegroundColor Yellow }

# ── 1. 依赖检查 & 安装 ──────────────────────────────────────────
if (-not $SkipInstall) {

    # ── 后端 venv ──
    if (-not (Test-Path $VenvPython)) {
        Write-Step "创建 Python 虚拟环境..."
        Push-Location $Backend
        python -m venv .venv
        Pop-Location
    }

    Write-Step "检查后端依赖..."
    $needInstall = $false
    try {
        & $VenvPython -c "import fastapi, uvicorn, celery, sqlalchemy, alembic" 2>$null
        if ($LASTEXITCODE -ne 0) { $needInstall = $true }
    } catch { $needInstall = $true }

    if ($needInstall) {
        Write-Step "安装后端依赖 (requirements.txt)..."
        & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")
        Write-Ok "后端依赖安装完成"
    } else {
        Write-Ok "后端依赖已就绪"
    }

    # ── 前端 node_modules ──
    Write-Step "检查前端依赖..."
    $ViteBin = Join-Path $Frontend "node_modules\.bin\vite.cmd"
    if (-not (Test-Path $ViteBin)) {
        Write-Step "安装前端依赖 (npm install)..."
        Push-Location $Frontend
        npm install
        Pop-Location
        if (-not (Test-Path $ViteBin)) {
            Write-Warn2 "npm install 完成，但 vite 仍未找到，请手动检查 frontend/node_modules"
        }
        Write-Ok "前端依赖安装完成"
    } else {
        Write-Ok "前端依赖已就绪"
    }
}

# ── 1b. 生成 iconify icons.css ─────────────────────────────────
$IconsCss = Join-Path $Frontend "src\plugins\iconify\icons.css"
if (-not (Test-Path $IconsCss)) {
    Write-Step "生成 iconify icons.css..."
    Push-Location $Frontend
    npx tsx src/plugins/iconify/build-icons.ts
    Pop-Location
    Write-Ok "icons.css 生成完成"
}

# ── 2. data 目录（SQLite + 日志存放处）──────────────────────────
$DataDir = Join-Path $Backend "data"
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Ok "创建 data 目录: $DataDir"
}

# ── 2a. 确保超级用户存在 ────────────────────────────────────────
Write-Step "检查管理员账号..."
$initScript = @"
import os, sys
os.chdir(r'$Backend')
sys.path.insert(0, '.')
from bonita.core.security import get_password_hash
from bonita.db import SessionFactory
from bonita.db.models.user import User
with SessionFactory() as session:
    if User.get_user_by_email(session=session, email='admin@example.com'):
        print('admin exists')
    else:
        u = User(name='admin', email='admin@example.com', hashed_password=get_password_hash('changepwd'), is_active=True, is_superuser=True)
        u.create(session)
        print('admin created')
"@
try {
    & $VenvPython -c $initScript 2>$null
    Write-Ok "管理员账号就绪 (admin@example.com / changepwd)"
} catch {
    Write-Warn2 "管理员检查跳过（数据库可能未初始化，首次启动后端时会自动创建）"
}

# ── 2b. 前端 .env（API 地址）─────────────────────────────────────
$EnvFile = Join-Path $Frontend ".env.development"
if (-not (Test-Path $EnvFile)) {
    'VITE_API_URL="http://localhost:8000"' | Set-Content -Path $EnvFile -Encoding utf8
    Write-Ok "创建 $EnvFile"
}

# ── 3. 启动三个服务（各开一个新窗口）────────────────────────────
Write-Step "启动服务..."

# 后端 API
Start-Process pwsh -ArgumentList @(
    "-NoExit", "-Command",
    "Write-Host '=== Bonita Backend (FastAPI :8000) ===' -ForegroundColor Cyan;",
    "Set-Location '$Backend';",
    "& '.venv\Scripts\python.exe' -m uvicorn bonita.main:app --host 0.0.0.0 --port 8000 --reload"
)
Write-Ok "后端已启动 → http://localhost:8000"

# Celery Worker
Start-Process pwsh -ArgumentList @(
    "-NoExit", "-Command",
    "Write-Host '=== Bonita Celery Worker ===' -ForegroundColor Cyan;",
    "Set-Location '$Backend';",
    "& '.venv\Scripts\python.exe' -m celery --app bonita.worker.celery worker --pool threads --concurrency 5 --events --loglevel INFO"
)
Write-Ok "Celery Worker 已启动"

# 前端 Vite
Start-Process pwsh -ArgumentList @(
    "-NoExit", "-Command",
    "Write-Host '=== Bonita Frontend (Vite :3000) ===' -ForegroundColor Cyan;",
    "Set-Location '$Frontend';",
    "npx vite --port 3000"
)
Write-Ok "前端已启动 → http://localhost:3000"

Write-Host "`n[dev] 所有服务已在新窗口中启动。" -ForegroundColor Green
Write-Host "[dev] 后端 API:  http://localhost:8000" -ForegroundColor Gray
Write-Host "[dev] API 文档:   http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "[dev] 前端页面:  http://localhost:3000" -ForegroundColor Gray
Write-Host "[dev] 关闭对应窗口即可停止各服务。`n" -ForegroundColor Gray
