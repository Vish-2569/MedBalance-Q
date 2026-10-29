.PHONY: up down logs ps build test fmt lint seed eval eval-ai demo warm-cache evidence check-env

up:
	docker compose --profile full up -d

down:
	docker compose --profile full down

logs:
	docker compose --profile full logs -f

ps:
	docker compose --profile full ps

build:
	docker compose build py-base
	docker compose --profile full build

test:
	cd libs/medbal_common && uv run pytest

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

seed:
	python -I data/seed/generate.py --seed 42

eval:
	cd services/optimizer && uv run python -m app.eval.replay --seeds 20 --days 28 --policies A,B,C,D,E --solver local

demo:
	@echo "not implemented yet (P04)"

eval-ai:
	python -I evals/run_evals.py

eval-ai-live:
	python -I evals/run_evals.py --live

warm-cache:
	python -I scripts/warm_cache.py

evidence:
	@echo "not implemented yet (P03)"

check-env:
	@expected=$$(grep -E '^[A-Z_]+=' .env.example | cut -d= -f1); \
	for key in $$expected; do \
		if grep -qE "^$$key=" .env 2>/dev/null; then \
			val=$$(grep -E "^$$key=" .env | cut -d= -f2); \
			case "$$val" in \
				"<"*">") echo "$$key: MISSING (placeholder)" ;; \
				"")       echo "$$key: MISSING (empty)" ;; \
				*)        echo "$$key: set" ;; \
			esac; \
		else \
			echo "$$key: MISSING (not in .env)"; \
		fi; \
	done
