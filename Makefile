# Usage: make build | test | lint | run | clean   (no venv; deps live in ./libs, see env.sh)
SHELL := /bin/bash
ENV := source env.sh &&

.PHONY: build test lint run clean
build:
	$(ENV) rm -rf dist build && uv build --wheel --out-dir dist
test:
	$(ENV) python -m pytest -q tests
lint:
	$(ENV) ruff check src tests
run:
	$(ENV) python -m me3 serve --port 8765
clean:
	rm -rf dist build src/*.egg-info
