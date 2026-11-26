#!/bin/bash
# EC2에서 실행 (seed_demo_remote.sh가 복사해서 부름). 비밀번호는 표준 입력 첫 줄로 받음.
set -eo pipefail

read -r DEMO_PASSWORD
export DEMO_PASSWORD
cd ~/project

cleanup() {
  docker compose exec -T fastapi rm -rf /app/scripts || true
  rm -rf ~/project/seed
}
trap cleanup EXIT

docker compose cp seed/scripts fastapi:/app/scripts
docker compose exec -T -e DEMO_PASSWORD fastapi uv run --no-sync python -m scripts.seed_demo
