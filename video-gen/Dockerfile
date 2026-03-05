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

# TurboDiffusion: clone full repo (serve/pipeline.py needs inference/ and rcm/)
ARG TURBO_COMMIT=4ce6a6fc25138c745bf42dfadbbc12fabbe1add6
RUN git clone https://github.com/thu-ml/TurboDiffusion.git /opt/TurboDiffusion \
    && cd /opt/TurboDiffusion && git checkout $TURBO_COMMIT \
    && git submodule update --init --recursive
# Runtime deps (editable install fails without GPU for CUDA extensions, so install deps separately)
RUN pip install --no-cache-dir \
    loguru einops omegaconf fvcore ftfy attrs regex rich prompt-toolkit pandas nvidia-ml-py

# PYTHONPATH: turbodiffusion/ for bare imports (rcm, imaginaire, ops, SLA)
#             turbodiffusion/inference/ for modify_model
ENV PYTHONPATH="/opt/TurboDiffusion/turbodiffusion:/opt/TurboDiffusion/turbodiffusion/inference:${PYTHONPATH}"

# Application code
COPY models.py pipelines.py server.py entrypoint.sh ./
COPY scripts/ scripts/

# Output and model cache directories
RUN mkdir -p /outputs/videos /models

ENV OUTPUT_DIR=/outputs/videos
ENV MODEL_CACHE=/models
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["bash", "entrypoint.sh"]
