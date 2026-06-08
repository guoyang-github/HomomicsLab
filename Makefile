.PHONY: install dev test lint format clean lint-frontend format-frontend

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn homics_lab.main:app --reload --port 8080

dev-frontend:
	cd frontend && npm run dev

test-backend:
	cd backend && pytest -v

test-frontend:
	cd frontend && npm test -- --run

lint-backend:
	cd backend && ruff check .
	cd backend && mypy homics_lab

format:
	cd backend && black .
	cd backend && ruff check . --fix

lint-frontend:
	cd frontend && npx tsc --noEmit

format-frontend:
	cd frontend && npx prettier --write "src/**/*.{ts,tsx}"

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist
	rm -f backend/homics_lab.db
