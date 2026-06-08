.PHONY: install dev test lint format clean

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

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	rm -f backend/homics_lab.db
