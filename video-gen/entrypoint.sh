#!/bin/bash
# Entrypoint: build TurboDiffusion CUDA extensions on first startup (needs GPU),
# then start the FastAPI server.
set -e

MARKER="/opt/TurboDiffusion/.cuda_ops_built"

if [ ! -f "$MARKER" ] && [ -d "/opt/TurboDiffusion" ]; then
    echo "==> Building TurboDiffusion CUDA extensions (first startup, requires GPU)..."
    cd /opt/TurboDiffusion
    if pip install --no-cache-dir --no-build-isolation -e . 2>&1; then
        touch "$MARKER"
        echo "==> CUDA extensions built successfully"
    else
        echo "==> WARNING: CUDA extensions build failed. TurboWan will use fallback (original attention)."
    fi
    cd /app
fi

exec uvicorn server:app --host 0.0.0.0 --port 8000 --log-level info
