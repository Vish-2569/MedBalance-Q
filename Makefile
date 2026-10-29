.PHONY: up down logs ps build test fmt lint seed eval eval-ai demo demo-live warm-cache evidence load-sanity check-env

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
	docker compose --profile full down -v || true
	docker compose build py-base
	docker compose --profile full build
	python -I data/seed/generate.py --seed 42
	DEMO_MODE=replay docker compose --profile full up -d
	@echo "Waiting for services to be healthy..."
	@python -I scripts/wait_healthy.py
	@echo "Resetting simulation..."
	@python -I -c "import httpx; httpx.post('http://localhost:8080/api/sim/reset?seed=42', timeout=10)"
	@echo ""
	@echo "============================================"
	@echo "  MedBalance-Q demo ready (replay mode)"
	@echo "  http://localhost:8080"
	@echo "============================================"

demo-live:
	docker compose --profile full down -v || true
	docker compose build py-base
	docker compose --profile full build
	python -I data/seed/generate.py --seed 42
	DEMO_MODE=live docker compose --profile full up -d
	@echo "Waiting for services to be healthy..."
	@python -I scripts/wait_healthy.py
	@python -I -c "import httpx; httpx.post('http://localhost:8080/api/sim/reset?seed=42', timeout=10)"
	@echo ""
	@echo "============================================"
	@echo "  MedBalance-Q demo ready (live mode)"
	@echo "  http://localhost:8080"
	@echo "============================================"

eval-ai:
	python -I evals/run_evals.py

eval-ai-live:
	python -I evals/run_evals.py --live

warm-cache:
	python -I scripts/warm_cache.py

evidence:
	@python -I scripts/package_evidence.py

load-sanity:
	python -I scripts/load_sanity.py

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
