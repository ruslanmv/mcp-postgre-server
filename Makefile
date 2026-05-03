.PHONY: install test lint typecheck run docker-build docker-up

install:
	pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy src

run:
	mcp-postgre-server

docker-build:
	docker build -t mcp-postgre-server:local .

docker-up:
	docker compose up --build
