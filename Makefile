# =============================================================================
# Kingstore SaaS — developer ergonomics
# Run from repo root. Targets wrap docker compose for the common workflows.
# =============================================================================

COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: help up down logs ps shell migrate revision seed test lint typecheck fmt rebuild clean

help:
	@echo "Targets:"
	@echo "  up         Boot the stack (app, db, redis, nginx)"
	@echo "  down       Stop the stack"
	@echo "  logs       Tail app logs"
	@echo "  ps         Show running services"
	@echo "  shell      Open a shell in the app container"
	@echo "  migrate    Apply Alembic migrations"
	@echo "  revision m=\"msg\"  Generate a new Alembic revision (autogenerate)"
	@echo "  seed       Run dev seed script"
	@echo "  test       Run pytest in the app container"
	@echo "  lint       ruff check"
	@echo "  typecheck  mypy"
	@echo "  fmt        ruff format"
	@echo "  rebuild    Rebuild images without cache"
	@echo "  clean      Stop + remove volumes (destroys local data)"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f app worker

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec app /bin/bash

migrate:
	$(COMPOSE) exec app flask db upgrade

revision:
	@if [ -z "$(m)" ]; then echo "Usage: make revision m=\"message\""; exit 1; fi
	$(COMPOSE) exec app flask db migrate -m "$(m)"

seed:
	$(COMPOSE) exec app python scripts/seed_dev.py

test:
	$(COMPOSE) exec app pytest

lint:
	$(COMPOSE) exec app ruff check .

typecheck:
	$(COMPOSE) exec app mypy app

fmt:
	$(COMPOSE) exec app ruff format .

rebuild:
	$(COMPOSE) build --no-cache

clean:
	$(COMPOSE) down -v
