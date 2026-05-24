# Kingstore SaaS — VPS Deploy

Three pieces: `bootstrap-vps.sh` (one-time), `deploy.sh` (on every update),
and `maintenance-toggle.sh` (start/stop the demo).

## One-time setup on the VPS (root)

```bash
# 1) Push the repo to GitHub first, then on the VPS:
cd /srv
git clone https://github.com/erarama515-gif/kingstore-saas.git kingstore
chown -R kingstore:kingstore /srv/kingstore || true

# 2) Bootstrap (creates DB, user, services, nginx, TLS)
export KINGSTORE_DOMAIN="demo.kingstore.example.com"   # must point to this VPS via A record
bash /srv/kingstore/deploy/bootstrap-vps.sh
```

## Every update

```bash
sudo bash /srv/kingstore/deploy/deploy.sh
```

`deploy.sh` does:
1. `git pull --ff-only`
2. Python venv install + `flask db upgrade`
3. `npm ci && npm run build` (Next.js standalone)
4. `systemctl restart kingstore-api kingstore-web`
5. Healthchecks

## Take the demo offline / online (sales control)

```bash
sudo bash /srv/kingstore/deploy/maintenance-toggle.sh stop   # client can't reach demo
sudo bash /srv/kingstore/deploy/maintenance-toggle.sh start  # bring back
```

## Files

| File | Role |
|---|---|
| `bootstrap-vps.sh` | One-time install — packages, DB, services, nginx, TLS |
| `deploy.sh` | Pull + build + migrate + restart |
| `maintenance-toggle.sh` | Quick stop/start |
| `nginx-kingstore.conf` | Nginx vhost template (`DOMAIN_PLACEHOLDER` is substituted) |
| `kingstore-api.service` | systemd unit for the gunicorn Flask API |
| `kingstore-web.service` | systemd unit for the Next.js standalone server |

## Notes

* The Hostinger VPS already runs `portfolio_v2_nginx` in Docker on ports 80/443.
  The system nginx installed here will conflict. Two options:
  - **Recommended for the demo:** stop the Docker nginx
    (`docker stop portfolio_v2_nginx`) while the kingstore demo is live, OR
  - Add a server block to the existing Dockerized nginx instead of using the
    system nginx (drop `nginx-kingstore.conf` into `portfolio_v2_nginx`'s
    `conf.d/`, and proxy to host ports `8000` / `3001`).
* The backend runs without Redis (`REDIS_URL=""`) per the simplified MVP
  strategy; in-memory rate-limit is fine for a demo serving one customer.
