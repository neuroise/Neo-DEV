#!/bin/bash
# Download LTX Video 2.3 checkpoints from HuggingFace.
# Run inside the video-gen container:
#   docker exec neuroise-video-gen bash /app/scripts/download_ltx_checkpoints.sh
set -e

LTX_DIR="${MODEL_CACHE:-/models}/ltx"
GEMMA_DIR="${MODEL_CACHE:-/models}/gemma"
mkdir -p "$LTX_DIR" "$GEMMA_DIR"

echo "==> Downloading LTX-2.3 checkpoints to $LTX_DIR"

# Distilled model (fast, 8 steps)
hf download Lightricks/LTX-2.3 \
    ltx-2.3-22b-distilled-1.1.safetensors \
    --local-dir "$LTX_DIR"

# Full dev model (highest quality)
hf download Lightricks/LTX-2.3 \
    ltx-2.3-22b-dev.safetensors \
    --local-dir "$LTX_DIR"

# Distilled LoRA (required for two-stage pipeline)
hf download Lightricks/LTX-2.3 \
    ltx-2.3-22b-distilled-lora-384-1.1.safetensors \
    --local-dir "$LTX_DIR"

# Spatial upscaler (required for two-stage pipeline)
hf download Lightricks/LTX-2.3 \
    ltx-2.3-spatial-upscaler-x2-1.1.safetensors \
    --local-dir "$LTX_DIR"

# FP8 quantized variants
hf download Lightricks/LTX-2.3-fp8 \
    ltx-2.3-22b-distilled-fp8.safetensors \
    --local-dir "$LTX_DIR"

hf download Lightricks/LTX-2.3-fp8 \
    ltx-2.3-22b-dev-fp8.safetensors \
    --local-dir "$LTX_DIR"

echo "==> Downloading Gemma 3 text encoder to $GEMMA_DIR"
hf download google/gemma-3-12b-it-qat-q4_0-unquantized \
    --local-dir "$GEMMA_DIR/gemma-3-12b"

echo "==> Done. Checkpoints:"
ls -lh "$LTX_DIR"/*.safetensors 2>/dev/null || echo "  (none found)"
echo "Gemma:"
ls "$GEMMA_DIR/gemma-3-12b/" 2>/dev/null | head -10 || echo "  (none found)"
