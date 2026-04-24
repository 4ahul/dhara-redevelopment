# Dhara AI Monorepo Management
.PHONY: help up down sync migrate doc test clean run-all

# --- Docker Commands ---
up:
	docker-compose up -d --build

down:
	docker-compose down

ps:
	docker-compose ps

logs:
	docker-compose logs -f

# --- Workspace Commands ---
init:
	@powershell -Command "Get-ChildItem -Recurse -Filter '.env.example' | ForEach-Object { `$dest = Join-Path `$_.Directory.FullName '.env'; if (!(Test-Path `$dest)) { Copy-Item `$_.FullName `$dest; Write-Host 'Created: '`$dest } }"
	@echo "Project initialized. Please update .env files with your secrets."

sync:
	uv sync --all-packages

migrate:
	@echo "Migrating Orchestrator..."
	cd services/orchestrator && uv run alembic upgrade head
	@echo "Migrating RAG Service..."
	cd services/rag_service && uv run alembic upgrade head
	@echo "Migrating MCGM Property Lookup..."
	cd services/mcgm_property_lookup && uv run alembic upgrade head
	@echo "Migrating PR Card Scraper..."
	cd services/pr_card_scraper && uv run alembic upgrade head


doc:
	uv run scripts/export_openapi.py

test:
	uv run pytest

lint:
	uv run ruff check . --fix

clean:
	@powershell -Command "Get-ChildItem -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force"
	@powershell -Command "Get-ChildItem -Recurse -Filter '*.pyc' | Remove-Item -Force"

# --- Local Execution (No Docker) ---

run-orchestrator:
	uv run python -m services.orchestrator.main

run-site:
	cd services/site_analysis && uv run python main.py

run-height:
	cd services/aviation_height && uv run python main.py

run-ready-reckoner:
	cd services/ready_reckoner && uv run python main.py

run-report:
	cd services/report_generator && uv run python main.py

run-pr:
	cd services/pr_card_scraper && uv run python main.py

run-mcgm:
	cd services/mcgm_property_lookup && uv run python main.py

run-dp:
	cd services/dp_remarks_report && uv run python main.py

run-rag:
	cd services/rag_service && uv run python main.py

# Run all microservices locally in background (Windows PowerShell)
run-all:
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', '-m', 'services.orchestrator.main' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/site_analysis/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/aviation_height/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/ready_reckoner/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/report_generator/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/pr_card_scraper/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/mcgm_property_lookup/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/dp_remarks_report/main.py' -NoNewWindow"
	@powershell -Command "Start-Process uv -ArgumentList 'run', 'python', 'services/rag_service/main.py' -NoNewWindow"
	@echo "All services started in background."

help:
	@echo "Dhara AI Monorepo Management Commands:"
	@echo "  make up               - Start stack in Docker"
	@echo "  make run-all          - Start ALL services locally (background)"
	@echo "  make run-orchestrator - Run Orchestrator locally"
	@echo "  make run-site         - Run Site Analysis locally"
	@echo "  make run-rag          - Run RAG Service locally"
	@echo "  make run-mcgm         - Run MCGM Lookup locally"
	@echo "  make sync             - Sync all dependencies"
	@echo "  make migrate          - Run DB migrations"
