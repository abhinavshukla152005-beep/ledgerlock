#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "docker is required (see README)"; exit 1; }
docker compose version >/dev/null

[ -f .env ] || cp .env.example .env

set -a
# shellcheck disable=SC1091
. ./.env
set +a

SANDBOX_DIR="${SANDBOX_DIR:-/srv/ledgerlock/sandbox}"
sudo mkdir -p "$SANDBOX_DIR"
sudo chmod 755 "$SANDBOX_DIR"

docker pull "${SANDBOX_IMAGE:-python:3.11-slim}"
docker compose up -d --build --remove-orphans
docker compose ps
echo
echo "Serving on ${SITE_ADDRESS:-:80}. First request pulls nothing: the sandbox image is cached."
