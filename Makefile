PY=backend/.venv/Scripts/python.exe

setup:
	python -m venv backend/.venv
	$(PY) -m pip install -r backend/requirements.txt
	cd frontend && npm install
	docker compose up -d db

seed:
	$(PY) -m app.seed

dev:
	cd backend && .venv/Scripts/python.exe -m uvicorn app.api:app --port 8002 --reload

dev-web:
	cd frontend && npm run dev

test:
	cd backend && .venv/Scripts/python.exe -m pytest

verify:
	cd backend && .venv/Scripts/python.exe scripts/verify.py

lint:
	cd backend && .venv/Scripts/python.exe -m ruff check app tests

aa-study:
	cd backend && .venv/Scripts/python.exe scripts/aa_experiment.py

.PHONY: setup seed dev dev-web test verify lint aa-study
