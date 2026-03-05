#!/bin/bash
# Download TurboDiffusion checkpoints for TurboWan T2V models.
#
# Usage (inside the video-gen container):
#   bash /app/scripts/download_turbo_checkpoints.sh
#
# Or from the host:
#   docker exec neuroise-video-gen bash /app/scripts/download_turbo_checkpoints.sh
set -e

MODEL_DIR="${MODEL_CACHE:-/models}/turbo"
mkdir -p "$MODEL_DIR"

HF="python3 -m huggingface_hub.commands.huggingface_cli"

echo "==> Downloading shared components (VAE + UMT5 text encoder + tokenizer)..."
$HF download Wan-AI/Wan2.1-T2V-1.3B \
    Wan2.1_VAE.pth models_t5_umt5-xxl-enc-bf16.pth \
    google/umt5-xxl/spiece.model google/umt5-xxl/tokenizer.json \
    google/umt5-xxl/tokenizer_config.json google/umt5-xxl/special_tokens_map.json \
    --local-dir "$MODEL_DIR"

echo "==> Downloading T2V 1.3B DiT checkpoint..."
$HF download TurboDiffusion/TurboWan2.1-T2V-1.3B-480P \
    TurboWan2.1-T2V-1.3B-480P.pth --local-dir "$MODEL_DIR"

echo "==> Downloading T2V 14B DiT checkpoint..."
$HF download TurboDiffusion/TurboWan2.1-T2V-14B-480P \
    TurboWan2.1-T2V-14B-480P.pth --local-dir "$MODEL_DIR"

echo "Done. Checkpoints saved to $MODEL_DIR"
