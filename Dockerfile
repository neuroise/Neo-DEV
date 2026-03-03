# NEURØISE Playground - Dockerfile
#
# Multi-stage build per deployment su Mac (development) e DGX Spark (production)
#
# Build stages:
#   1. base: dipendenze Python comuni
#   2. dev: per sviluppo locale (include dev tools)
#   3. prod: per deployment (ottimizzato, CUDA-ready)
#
# Usage:
#   Development (Mac):
#     docker build --target dev -t neuroise-playground:dev .
#     docker-compose up
#
#   Production (DGX con NGC PyTorch):
#     docker build --target prod -t neuroise-playground:prod .
#     docker-compose -f docker-compose.prod.yml up

# ==============================================================================
# BASE STAGE - Common dependencies
# ==============================================================================
FROM python:3.11-slim as base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (requirements comuni)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# DEVELOPMENT STAGE - Per Mac/sviluppo locale
# ==============================================================================
FROM base as dev

# Dev tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    black \
    isort \
    mypy \
    ipython \
    jupyter

# Copy source
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Default command
CMD ["streamlit", "run", "app/main.py", "--server.address", "0.0.0.0"]

# ==============================================================================
# PRODUCTION STAGE - Per DGX Spark con CUDA
# ==============================================================================
# Usa NGC PyTorch come base per GPU support
# Nota: questo stage richiede nvidia-docker e NGC access
FROM nvcr.io/nvidia/pytorch:24.01-py3 as prod-base

WORKDIR /app

# Python dependencies
COPY requirements.txt requirements-gpu.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-gpu.txt || true

# ==============================================================================
# PRODUCTION FINAL
# ==============================================================================
FROM prod-base as prod

# Copy source
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Expose ports
EXPOSE 8501
EXPOSE 11434

# Default command
CMD ["streamlit", "run", "app/main.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
