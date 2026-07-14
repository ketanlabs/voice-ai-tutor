# Convenience targets for the Lingua pronunciation trainer.
# `make test` is fully offline (no API keys or running services required).

.PHONY: help up down logs clean clean-stale seed test test-backend test-frontend functional-test lint check-env

help:
	@echo "Targets:"
	@echo "  make up              - build + start the full stack (needs .env)"
	@echo "  make down            - stop the stack"
	@echo "  make logs            - tail logs from all services"
	@echo "  make clean           - stop and wipe volumes (clears learner memory)"
	@echo "  make clean-stale     - delete Redis keys not namespaced by language (old schema)"
	@echo "  make seed            - rebuild+restart backend to reload the exercise YAML"
	@echo "  make test            - run backend + frontend UNIT tests in-container (offline)"
	@echo "  make functional-test - drive the running backend end-to-end (start it first)"
	@echo "  make lint            - typecheck frontend + byte-compile backend"

check-env:
	@test -f .env || { echo "No .env found. Run: cp .env.example .env"; exit 1; }

up: check-env
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v

# Delete legacy Redis keys not namespaced by language (from earlier schema
# versions). Current keys look like learner:{handle}:{es|fr|it}:{suffix}.
clean-stale:
	@docker compose exec -T redis redis-cli KEYS 'learner:*' \
		| tr -d '\r' | awk -F: '$$3!="es" && $$3!="fr" && $$3!="it"' \
		| xargs -r docker compose exec -T redis redis-cli DEL \
		&& echo "stale keys removed"

seed: check-env
	docker compose up -d --build backend

# ---- tests (no .env, no live services; fakeredis + Vitest) ----------------
test: test-backend test-frontend

test-backend:
	docker build -t voice-tutor-backend-test ./backend
	docker run --rm voice-tutor-backend-test pytest -q

test-frontend:
	docker build --target builder -t voice-tutor-frontend-test ./frontend
	docker run --rm voice-tutor-frontend-test npm run test

# End-to-end check against a RUNNING backend + real Redis.
# Start it first with:  docker compose up --build backend
functional-test:
	python3 scripts/functional_test.py

lint:
	docker build --target builder -t voice-tutor-frontend-test ./frontend
	docker run --rm voice-tutor-frontend-test npx tsc --noEmit
	docker build -t voice-tutor-backend-test ./backend
	docker run --rm voice-tutor-backend-test python -m compileall src
