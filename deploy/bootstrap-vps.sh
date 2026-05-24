#!/usr/bin/env bash
# =============================================================================
# Kingstore SaaS — VPS bootstrap (one-time setup)
# Run as root on a fresh Ubuntu 22.04 / 24.04 host.
# Idempotent — re-running is safe.
# =============================================================================
set -euo pipefail

DOMAIN="${KINGSTORE_DOMAIN:?KINGSTORE_DOMAIN env var is required (e.g. demo.kingstore.example.com)}"
DB_PASSWORD="${KINGSTORE_DB_PASSWORD:-$(openssl rand -hex 16)}"
SECRET_KEY="${KINGSTORE_SECRET:-$(openssl rand -hex 32)}"
JWT_SECRET="${KINGSTORE_JWT_SECRET:-$(openssl rand -hex 32)}"

echo "==> [1/8] Installing system packages..."
apt-get update -y
apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev \
    build-essential libpq-dev \
    postgresql postgresql-contrib \
    nginx certbot python3-certbot-nginx \
    git curl ca-certificates gnupg

echo "==> [2/8] Installing Node.js 20 LTS..."
if ! command -v node >/dev/null 2>&1; then
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list
    apt-get update -y
    apt-get install -y nodejs
fi
echo "Node: $(node --version)"

echo "==> [3/8] Creating kingstore system user..."
id -u kingstore >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash kingstore
install -d -o kingstore -g kingstore /srv/kingstore /srv/kingstore/backend /srv/kingstore/frontend

echo "==> [4/8] Provisioning PostgreSQL database..."
sudo -u postgres psql <<SQL
DO \$\$ BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='kingstore') THEN
      CREATE ROLE kingstore LOGIN PASSWORD '$DB_PASSWORD';
   END IF;
END \$\$;
SQL
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='kingstore'" | grep -q 1 \
    || sudo -u postgres createdb -O kingstore kingstore
sudo -u postgres psql -d kingstore -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
sudo -u postgres psql -d kingstore -c "CREATE EXTENSION IF NOT EXISTS citext;"

echo "==> [5/8] Writing backend .env..."
cat > /srv/kingstore/backend/.env <<ENV
FLASK_ENV=production
KINGSTORE_CONFIG=production
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
DATABASE_URL=postgresql+psycopg2://kingstore:$DB_PASSWORD@localhost:5432/kingstore
REDIS_URL=
CORS_ORIGINS=https://$DOMAIN
LOG_LEVEL=INFO
LOG_FORMAT=json
APP_TIMEZONE=Africa/Cairo
ENV
chown kingstore:kingstore /srv/kingstore/backend/.env
chmod 600 /srv/kingstore/backend/.env

echo "==> [6/8] Installing systemd units..."
install -m 644 /srv/kingstore/deploy/kingstore-api.service /etc/systemd/system/
install -m 644 /srv/kingstore/deploy/kingstore-web.service /etc/systemd/system/
systemctl daemon-reload

echo "==> [7/8] Configuring nginx..."
sed "s|DOMAIN_PLACEHOLDER|$DOMAIN|g" /srv/kingstore/deploy/nginx-kingstore.conf \
    > /etc/nginx/sites-available/kingstore-saas.conf
ln -sf /etc/nginx/sites-available/kingstore-saas.conf /etc/nginx/sites-enabled/
nginx -t

echo "==> [8/8] Obtaining Let's Encrypt cert..."
mkdir -p /var/www/certbot
systemctl reload nginx || systemctl start nginx
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" \
    || echo "WARN: certbot failed — re-run manually once DNS is propagated."

echo ""
echo "================================================================"
echo "  Kingstore SaaS VPS bootstrap done."
echo "  Domain : https://$DOMAIN"
echo "  DB pwd : $DB_PASSWORD"
echo ""
echo "  Next:"
echo "    1. Push code to /srv/kingstore (or rsync from your machine)"
echo "    2. Run /srv/kingstore/deploy/deploy.sh (see file)"
echo "================================================================"
