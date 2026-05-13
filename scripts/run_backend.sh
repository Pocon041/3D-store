#!/usr/bin/env bash
set -e

# 启动 FastAPI 后端
# 默认端口 8000，可通过环境变量 BACKEND_HOST / BACKEND_PORT 覆盖

cd "$(dirname "$0")/.."

uvicorn backend.main:app \
  --host "${BACKEND_HOST:-0.0.0.0}" \
  --port "${BACKEND_PORT:-8000}" \
  --reload
