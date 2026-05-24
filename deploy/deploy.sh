#!/usr/bin/env bash
# =============================================================================
# Kingstore SaaS — deploy / update (run on the VPS after bootstrap)
# Pulls latest code, installs deps, runs migrations, rebuilds frontend,
# restarts both services. Idempotent.
# =============================================================================
set -euo pipefail

cd /srv/kingstore

echo "==> Updating code (git pull)..."
sudo -u kingstore git pull --ff-only

echo "==> Backend: venv + deps + migrations..."
cd /srv/kingstore/backend
sudo -u kingstore python3.12 -m venv .venv 2>/dev/null || true
sudo -u kingstore ./.venv/bin/pip install --upgrade pip wheel
sudo -u kingstore ./.venv/bin/pip install -r requirements.txt
sudo -u kingstore env $(cat /srv/kingstore/backend/.env | xargs) \
    ./.venv/bin/flask --app app.wsgi:app db upgrade

echo "==> Frontend: install + build standalone..."
cd /srv/kingstore/frontend
sudo -u kingstore npm ci --no-audit --no-fund
sudo -u kingstore BUILD_STANDALONE=1 npm run build
# Copy standalone artifacts where systemd expects them
sudo -u kingstore mkdir -p .next/standalone/.next
sudo -u kingstore cp -r .next/static .next/standalone/.next/static
sudo -u kingstore cp -r public .next/standalone/public 2>/dev/null || true

echo "==> Restarting services..."
systemctl restart kingstore-api.service
systemctl restart kingstore-web.service

sleep 3
echo "==> Healthcheck:"
curl -fsS "http://127.0.0.1:8000/api/v1/health" && echo "  API: OK"
curl -fsS "http://127.0.0.1:3001" -o /dev/null && echo "  Web: OK"

echo ""
echo "Deploy complete."
systemctl --no-pager status kingstore-api kingstore-web | head -30
