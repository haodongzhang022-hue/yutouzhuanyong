#!/bin/bash
# AP Physics 专项练习系统启动脚本
set -e

# 默认模式
MODE="${1:-api}"
PORT="${2:-8080}"

case "$MODE" in
  api)
    python3 -m src.main --mode api --port "$PORT"
    ;;
  scheduler)
    python3 -m src.main --mode scheduler
    ;;
  init)
    python3 scripts/fetch_once.py
    ;;
  test)
    python3 -m pytest tests/ -v
    ;;
  *)
    echo "Usage: $0 {api|scheduler|init|test} [port]"
    exit 1
    ;;
esac
