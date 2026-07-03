.PHONY: install dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend format format-backend format-frontend clean

install:
	pip install -e ".[dev,test]"
	cd frontend && npm install

dev-backend:
	uvicorn homomics_lab.main:app --reload --port 8080

dev-frontend:
	cd frontend && npm run dev

test:
	pytest backend/tests --import-mode=importlib -q

test-backend:
	pytest backend/tests --import-mode=importlib -q

test-frontend:
	cd frontend && npm test -- --run

lint:
	ruff check backend/homomics_lab backend/tests
	mypy backend/homomics_lab
	cd frontend && npx tsc --noEmit

lint-backend:
	ruff check backend/homomics_lab backend/tests
	mypy backend/homomics_lab

lint-frontend:
	cd frontend && npx tsc --noEmit

format:
	ruff format backend/homomics_lab backend/tests
	cd frontend && npx prettier --write "src/**/*.{ts,tsx}"

format-backend:
	ruff format backend/homomics_lab backend/tests

format-frontend:
	cd frontend && npx prettier --write "src/**/*.{ts,tsx}"

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist
	rm -f backend/homomics_lab.db
