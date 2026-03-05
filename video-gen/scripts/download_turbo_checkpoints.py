#!/usr/bin/env python3
"""Download TurboDiffusion checkpoints for TurboWan T2V models.

Usage (inside the video-gen container):
    python3 /app/scripts/download_turbo_checkpoints.py

Or from the host:
    docker exec neuroise-video-gen python3 /app/scripts/download_turbo_checkpoints.py
"""
import os
from huggingface_hub import hf_hub_download

MODEL_DIR = os.path.join(os.environ.get("MODEL_CACHE", "/models"), "turbo")
os.makedirs(MODEL_DIR, exist_ok=True)

# Files to download: (repo_id, filename)
DOWNLOADS = [
    # Shared: VAE + UMT5 text encoder
    ("Wan-AI/Wan2.1-T2V-1.3B", "Wan2.1_VAE.pth"),
    ("Wan-AI/Wan2.1-T2V-1.3B", "models_t5_umt5-xxl-enc-bf16.pth"),
    # Shared: UMT5 tokenizer files
    ("Wan-AI/Wan2.1-T2V-1.3B", "google/umt5-xxl/spiece.model"),
    ("Wan-AI/Wan2.1-T2V-1.3B", "google/umt5-xxl/tokenizer.json"),
    ("Wan-AI/Wan2.1-T2V-1.3B", "google/umt5-xxl/tokenizer_config.json"),
    ("Wan-AI/Wan2.1-T2V-1.3B", "google/umt5-xxl/special_tokens_map.json"),
    # T2V 1.3B DiT
    ("TurboDiffusion/TurboWan2.1-T2V-1.3B-480P", "TurboWan2.1-T2V-1.3B-480P.pth"),
    # T2V 14B DiT
    ("TurboDiffusion/TurboWan2.1-T2V-14B-480P", "TurboWan2.1-T2V-14B-480P.pth"),
]


def main():
    for repo_id, filename in DOWNLOADS:
        dest = os.path.join(MODEL_DIR, filename)
        if os.path.exists(dest):
            print(f"  [skip] {filename} already exists")
            continue
        print(f"  [download] {repo_id} / {filename} ...")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=MODEL_DIR,
        )
        print(f"  [done] {filename}")

    print(f"\nAll checkpoints saved to {MODEL_DIR}")


if __name__ == "__main__":
    main()
