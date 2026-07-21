#!/usr/bin/env bash
# Bonita 本地开发一键启动脚本 (Git Bash / WSL / macOS / Linux 通用)
#
# 用法:
#   ./dev.sh              # 检查依赖 + 启动三服务
#   ./dev.sh --skip-install  # 跳过依赖检查，直接启动
#
# 启动后:
#   后端 API:  http://localhost:8000
#   API 文档:   http://localhost:8000/docs
#   前端页面:  http://localhost:3000

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
FRONTEND="$SCRIPT_DIR/frontend"

# Windows Git Bash 下 venv python 路径不同
if [[ -f "$BACKEND/.venv/Scripts/python.exe" ]]; then
  VENV_PYTHON="$BACKEND/.venv/Scripts/python.exe"
elif [[ -f "$BACKEND/.venv/bin/python" ]]; then
  VENV_PYTHON="$BACKEND/.venv/bin/python"
else
  VENV_PYTHON=""
fi

SKIP_INSTALL=false
[[ "${1:-}" == "--skip-install" ]] && SKIP_INSTALL=true

# ── 颜色输出 ────────────────────────────────────────────────────
info()  { echo -e "\n\033[36m[dev]\033[0m $*"; }
ok()    { echo -e "\033[32m[dev]\033[0m $*"; }
warn()  { echo -e "\033[33m[dev]\033[0m $*"; }

# ── 1. 依赖检查 & 安装 ──────────────────────────────────────────
if [[ "$SKIP_INSTALL" == "false" ]]; then

  # ── Python 检查 ──
  if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
    echo "错误: 未找到 python，请先安装 Python 3.10+"; exit 1
  fi

  # ── 后端 venv ──
  if [[ -z "$VENV_PYTHON" ]]; then
    info "创建 Python 虚拟环境..."
    cd "$BACKEND"
    python -m venv .venv
    # 重新检测路径
    if [[ -f ".venv/Scripts/python.exe" ]]; then
      VENV_PYTHON="$BACKEND/.venv/Scripts/python.exe"
    else
      VENV_PYTHON="$BACKEND/.venv/bin/python"
    fi
    cd "$SCRIPT_DIR"
  fi

  # ── 后端依赖 ──
  info "检查后端依赖..."
  if "$VENV_PYTHON" -c "import fastapi, uvicorn, celery, sqlalchemy, alembic" 2>/dev/null; then
    ok "后端依赖已就绪"
  else
    info "安装后端依赖 (requirements.txt)..."
    "$VENV_PYTHON" -m pip install -r "$BACKEND/requirements.txt"
    ok "后端依赖安装完成"
  fi

  # ── Node 检查 ──
  if ! command -v node &>/dev/null; then
    echo "错误: 未找到 node，请先安装 Node.js 18+"; exit 1
  fi

  # ── 前端依赖 ──
  info "检查前端依赖..."
  if [[ -f "$FRONTEND/node_modules/.bin/vite" ]] || [[ -f "$FRONTEND/node_modules/.bin/vite.cmd" ]]; then
    ok "前端依赖已就绪"
  else
    info "安装前端依赖 (npm install)..."
    cd "$FRONTEND"
    npm install
    cd "$SCRIPT_DIR"
    ok "前端依赖安装完成"
  fi
fi

# ── 1b. 生成 iconify icons.css（Vite 启动时需要此文件存在）─────
if [[ ! -f "$FRONTEND/src/plugins/iconify/icons.css" ]]; then
  info "生成 iconify icons.css..."
  cd "$FRONTEND"
  npx tsx src/plugins/iconify/build-icons.ts
  cd "$SCRIPT_DIR"
  ok "icons.css 生成完成"
fi

# ── 2. data 目录 ────────────────────────────────────────────────
mkdir -p "$BACKEND/data"
ok "data 目录就绪"

# ── 2a. 确保超级用户存在 ────────────────────────────────────────
info "检查管理员账号..."
"$VENV_PYTHON" -c "
import os, sys
os.chdir('$BACKEND')
sys.path.insert(0, '.')
from bonita.core.security import get_password_hash
from bonita.db import SessionFactory
from bonita.db.models.user import User
with SessionFactory() as session:
    if User.get_user_by_email(session=session, email='admin@example.com'):
        print('admin 已存在')
    else:
        u = User(name='admin', email='admin@example.com', hashed_password=get_password_hash('changepwd'), is_active=True, is_superuser=True)
        u.create(session)
        print('已创建管理员: admin@example.com / changepwd')
" 2>/dev/null && ok "管理员账号就绪" || warn "管理员检查跳过（数据库可能未初始化，首次启动后端时会自动创建）"

# ── 2b. 前端 .env ───────────────────────────────────────────────
if [[ ! -f "$FRONTEND/.env.development" ]]; then
  echo 'VITE_API_URL="http://localhost:8000"' > "$FRONTEND/.env.development"
  ok "创建 frontend/.env.development"
fi

# ── 3. 启动服务 ─────────────────────────────────────────────────
info "启动服务..."

cleanup() {
  echo ""
  warn "正在停止所有子进程..."
  kill $(jobs -p) 2>/dev/null || true
  wait 2>/dev/null || true
  ok "已停止"
}
trap cleanup EXIT INT TERM

# 后端 API
echo -e "\033[36m[dev]\033[0m 启动后端 FastAPI (:8000)..."
cd "$BACKEND"
BONITA_DEV_MODE=true FIRST_SUPERUSER_PASSWORD=changepwd "$VENV_PYTHON" -m uvicorn bonita.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Celery Worker
echo -e "\033[36m[dev]\033[0m 启动 Celery Worker..."
BONITA_DEV_MODE=true FIRST_SUPERUSER_PASSWORD=changepwd "$VENV_PYTHON" -m celery --app bonita.worker.celery worker --pool threads --concurrency 5 --events --loglevel INFO &
CELERY_PID=$!

# 前端 Vite
echo -e "\033[36m[dev]\033[0m 启动前端 Vite (:3000)..."
cd "$FRONTEND"
npx vite --port 3000 &
FRONTEND_PID=$!

cd "$SCRIPT_DIR"

# ── 状态汇总 ────────────────────────────────────────────────────
sleep 2
echo ""
ok "所有服务已启动:"
echo -e "  \033[90m后端 API:  http://localhost:8000\033[0m"
echo -e "  \033[90mAPI 文档:   http://localhost:8000/docs\033[0m"
echo -e "  \033[90m前端页面:  http://localhost:3000\033[0m"
echo ""
echo -e "  \033[90m默认登录: admin@example.com / changepwd\033[0m"
echo -e "  \033[90m按 Ctrl+C 停止所有服务\033[0m"
echo ""

# 等待任一进程退出
wait
