#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-api}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/health}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-20}"
HEALTHCHECK_INTERVAL_SECONDS="${HEALTHCHECK_INTERVAL_SECONDS:-2}"

cd "$APP_DIR"

if [[ ! -f ".env.production" ]]; then
  echo "Erro: .env.production nao encontrado em $APP_DIR" >&2
  echo "Crie esse arquivo antes de rodar o deploy." >&2
  exit 1
fi

if [[ ! -f "docker-compose.prod.yml" ]]; then
  echo "Erro: docker-compose.prod.yml nao encontrado em $APP_DIR" >&2
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "Erro: este diretorio nao parece ser um repositorio Git." >&2
  exit 1
fi

case "$MODE" in
  api)
    TARGET_LABEL="somente a API"
    COMPOSE_UP_ARGS=(up -d --build api)
    ;;
  full)
    TARGET_LABEL="a stack inteira"
    COMPOSE_UP_ARGS=(up -d --build)
    ;;
  *)
    echo "Uso: bash deploy.sh [api|full]" >&2
    echo "  api  -> atualiza apenas o servico da API" >&2
    echo "  full -> atualiza a API e recria toda a stack" >&2
    exit 1
    ;;
esac

echo
echo "==> Diretorio do projeto"
echo "$APP_DIR"

echo
echo "==> Atualizando codigo do GitHub"
git pull --ff-only

echo
echo "==> Recriando $TARGET_LABEL"
docker compose --env-file .env.production -f docker-compose.prod.yml "${COMPOSE_UP_ARGS[@]}"

echo
echo "==> Status dos containers"
docker compose --env-file .env.production -f docker-compose.prod.yml ps

echo
echo "==> Aguardando healthcheck"
HEALTHCHECK_OK=0
HEALTHCHECK_RESPONSE=""

for ((attempt = 1; attempt <= HEALTHCHECK_RETRIES; attempt++)); do
  if HEALTHCHECK_RESPONSE="$(curl --fail --silent --show-error "$HEALTHCHECK_URL" 2>/dev/null)"; then
    HEALTHCHECK_OK=1
    echo "Healthcheck respondeu com sucesso na tentativa $attempt/$HEALTHCHECK_RETRIES."
    echo "$HEALTHCHECK_RESPONSE"
    break
  fi

  echo "Tentativa $attempt/$HEALTHCHECK_RETRIES: API ainda inicializando. Aguardando ${HEALTHCHECK_INTERVAL_SECONDS}s..."
  sleep "$HEALTHCHECK_INTERVAL_SECONDS"
done

if [[ "$HEALTHCHECK_OK" -ne 1 ]]; then
  echo "Erro: a API nao respondeu ao healthcheck apos $HEALTHCHECK_RETRIES tentativas." >&2
  echo "Verifique os logs com:" >&2
  echo "docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 api" >&2
  exit 1
fi
echo
echo
echo "Deploy concluido com sucesso."
