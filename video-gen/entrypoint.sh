#!/bin/bash
# Entrypoint: build CUDA extensions on first startup (needs GPU),
# then start the FastAPI server.
set -e

# TurboDiffusion CUDA extensions
TURBO_MARKER="/opt/TurboDiffusion/.cuda_ops_built"
if [ ! -f "$TURBO_MARKER" ] && [ -d "/opt/TurboDiffusion" ]; then
    echo "==> Building TurboDiffusion CUDA extensions (first startup, requires GPU)..."
    cd /opt/TurboDiffusion
    if pip install --no-cache-dir --no-build-isolation -e . 2>&1; then
        touch "$TURBO_MARKER"
        echo "==> TurboDiffusion CUDA extensions built successfully"
    else
        echo "==> WARNING: TurboDiffusion CUDA extensions build failed. TurboWan will use fallback."
    fi
    cd /app
fi

# LTX-2: verify installation (already installed in Dockerfile, just check)
if [ -d "/opt/LTX-2" ]; then
    python3 -c "import ltx_pipelines" 2>/dev/null \
        && echo "==> LTX-2 pipelines available" \
        || echo "==> WARNING: ltx_pipelines import failed. LTX models will not be available."
fi

exec uvicorn server:app --host 0.0.0.0 --port 8000 --log-level info
