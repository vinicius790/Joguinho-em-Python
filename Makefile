.PHONY: install test lint format typecheck check run api

install:
	python -m pip install -e ".[api,dev]"

test:
	python -m pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

typecheck:
	mypy

check: lint typecheck test

run:
	python app.py

api:
	joguinho-api
