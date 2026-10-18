.PHONY: run install build test

run: install
	@echo "Backend  http://127.0.0.1:8790"
	@echo "Frontend http://127.0.0.1:5173  (Ctrl-C stops both)"
	@trap 'kill $$api $$web 2>/dev/null' EXIT; trap 'exit 130' INT TERM; \
	uv run --locked --extra ui nemotron-challenge ui --port 8790 & api=$$!; \
	(cd ui && exec node_modules/.bin/vite --port 5173 --strictPort) & web=$$!; \
	while kill -0 $$api 2>/dev/null && kill -0 $$web 2>/dev/null; do sleep 1; done

install: ui/node_modules
	uv sync --locked --inexact --extra ui

ui/node_modules: ui/package.json ui/package-lock.json
	npm --prefix ui ci
	@touch $@

build: install
	npm --prefix ui run build

test:
	uv run --locked pytest
