.PHONY: install ingest dev build

install:
	pip install -e .
	cd frontend && npm install

ingest:
	python data/bootstrap_northwind.py
	noderag ingest

dev:
	cd frontend && npx concurrently \
	  "uvicorn api.main:app --reload --port 8000" \
	  "npm run dev"

build:
	cd frontend && npm run build
	uvicorn api.main:app --host 0.0.0.0 --port 8000
