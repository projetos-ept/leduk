#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/leduk"
SERVICE="leduk"
HEALTH_URL="http://127.0.0.1:8091/health"

cd "$APP_DIR"

echo "==> git pull"
git pull origin main

echo "==> pip install"
.venv/bin/pip install -q -r requirements.txt

echo "==> corrigir ExecStart se necessário"
SERVICE_FILE="/etc/systemd/system/${SERVICE}.service"
CORRECT_EXEC="ExecStart=${APP_DIR}/.venv/bin/gunicorn -c ${APP_DIR}/gunicorn.conf.py app:create_app()"

if ! grep -qF "create_app()" "$SERVICE_FILE"; then
    sudo sed -i "s|^ExecStart=.*|${CORRECT_EXEC}|" "$SERVICE_FILE"
    echo "    ExecStart atualizado"
else
    echo "    ExecStart já correto, sem alteração"
fi

echo "==> systemctl daemon-reload + restart"
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE"

echo "==> aguardando serviço subir..."
sleep 2

echo "==> health check"
RESPONSE=$(curl -sf "$HEALTH_URL" || true)
if echo "$RESPONSE" | grep -q '"status".*"ok"'; then
    echo "OK: $RESPONSE"
    exit 0
else
    echo "ERRO: resposta inesperada — $RESPONSE"
    journalctl -u "$SERVICE" -n 20 --no-pager
    exit 1
fi
