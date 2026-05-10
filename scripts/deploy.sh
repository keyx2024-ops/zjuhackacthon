#!/bin/bash
# 一键部署脚本：本地开发模式
# Usage: ./scripts/deploy.sh [dev|prod]

set -e

MODE="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=========================================="
echo "  学科知识整合智能体 - 部署脚本"
echo "  模式: $MODE"
echo "  目录: $ROOT_DIR"
echo "=========================================="

if [ ! -f .env ]; then
  echo "[!] 未找到 .env 文件，从 .env.example 复制"
  if [ -f src/backend/.env.example ]; then
    cp src/backend/.env.example .env
  else
    cat > .env <<EOF
ASSISTANT_API_KEY=your_api_key_here
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=True
EOF
  fi
  echo "[!] 请编辑 .env 填入你的 API Key 后重新执行"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[X] 未检测到 Docker，请先安装 Docker"
  exit 1
fi

if [ "$MODE" = "dev" ]; then
  echo "[*] 启动开发模式（热重载）"
  docker compose -f docker-compose.dev.yml up --build
elif [ "$MODE" = "prod" ]; then
  echo "[*] 启动生产模式"
  docker compose -f docker-compose.yml up -d --build
  echo ""
  echo "[OK] 服务已启动："
  echo "  - 前端: http://localhost:3000"
  echo "  - 后端: http://localhost:8000"
  echo "  - API 文档: http://localhost:8000/docs"
  echo "  - Neo4j: http://localhost:7474"
else
  echo "[X] 未知模式: $MODE，可选 dev 或 prod"
  exit 1
fi
