# NEUROISE Video Generation Service
#
# Base: NGC PyTorch container (CUDA + PyTorch pre-installed)
# Adds: ffmpeg, diffusers, FastAPI, TurboWan support
#
# Build:
#   docker build -t neuroise-video-gen video-gen/
#
# Run:
#   docker run --gpus all -p 8000:8000 \
#     -v ./data/outputs/videos:/outputs/videos \
#     -v ./models/video:/models \
#     neuroise-video-gen

FROM nvcr.io/nvidia/pytorch:25.10-py3

# System deps (ffmpeg for video encoding)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# TurboWan from git (optional, skip if not available)
RUN pip install --no-cache-dir \
    git+https://github.com/turbodiffusion/turbodiffusion.git \
    || echo "TurboWan not available, skipping"

# Application code
COPY models.py pipelines.py server.py ./

# Output and model cache directories
RUN mkdir -p /outputs/videos /models

ENV OUTPUT_DIR=/outputs/videos
ENV MODEL_CACHE=/models
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
