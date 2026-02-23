# NEUROISE Playground - Makefile
#
# Quick commands for development and production

.PHONY: dev prod stop logs clean status pull-models

# Development (no GPU required)
dev:
	docker compose up -d --build

# Production (requires NVIDIA GPU)
prod:
	docker compose -f docker-compose.prod.yml up -d --build

# Stop all services
stop:
	docker compose down 2>/dev/null; \
	docker compose -f docker-compose.prod.yml down 2>/dev/null; \
	true

# Follow logs
logs:
	@if docker compose -f docker-compose.prod.yml ps -q 2>/dev/null | grep -q .; then \
		docker compose -f docker-compose.prod.yml logs -f; \
	else \
		docker compose logs -f; \
	fi

# Show service status
status:
	@echo "=== Development ===" && docker compose ps 2>/dev/null || true
	@echo ""
	@echo "=== Production ===" && docker compose -f docker-compose.prod.yml ps 2>/dev/null || true

# Pull LLM models into Ollama
pull-models:
	@echo "Pulling llama3.3:70b..."
	docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.3:70b

# Remove all containers and volumes
clean:
	docker compose down -v 2>/dev/null; \
	docker compose -f docker-compose.prod.yml down -v 2>/dev/null; \
	true
