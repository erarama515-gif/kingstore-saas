# Kingstore SaaS

Multi-tenant SaaS ERP platform for mobile shops. Built on top of the original Codely POS / King Store accounting logic, restructured as a production-grade modular monolith.

> **Status:** Foundation scaffold (Phase F1). Business modules are not yet implemented. See `docs/ARCHITECTURE.md` and the project roadmap.

## Layout

```
kingstore-saas/
├── backend/      Flask modular monolith, SQLAlchemy, Alembic, Celery
├── frontend/     Next.js (deferred, Phase F14)
├── infra/        docker-compose, nginx, postgres init
└── docs/         architecture, accounting flows, ERD, migration notes
```

## Quick start (development)

Requires Docker and Docker Compose.

```bash
# 1. Copy env template and edit
cp backend/.env.example backend/.env

# 2. Boot the stack (postgres + redis + flask + nginx)
docker compose -f infra/docker-compose.yml up --build

# 3. In another shell, initialize the database
docker compose -f infra/docker-compose.yml exec app flask db upgrade

# 4. Hit the health endpoint
curl http://localhost/api/v1/health
```

## Local (non-Docker) dev

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
export FLASK_APP=app.wsgi:app                       # PowerShell: $env:FLASK_APP="app.wsgi:app"
flask db upgrade
flask run
```

## Reference

The original system this replaces lives at `E:\kingstore system Final` and remains untouched. It is the source of truth for accounting behavior and will be the source of the SQLite-to-PostgreSQL ETL in phase F10.
