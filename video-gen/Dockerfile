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

# LTX Video 2.3: clone official repo and install ltx-pipelines
ARG LTX_COMMIT=1799988521d5e9725a4fbd4533d0cc12f07c07ed
RUN git clone https://github.com/Lightricks/LTX-2.git /opt/LTX-2 \
    && cd /opt/LTX-2 && git checkout $LTX_COMMIT
# torchaudio: install matching version (--no-deps to keep NVIDIA torch intact)
RUN pip install --no-cache-dir --no-deps torchaudio==2.9.0
RUN pip install --no-cache-dir \
    av tqdm openimageio soundfile
# Pin transformers to version tested by LTX team (NGC 5.2 breaks Gemma3 APIs)
RUN pip install --no-cache-dir transformers==4.57.6
# NGC torchao 0.14+git is missing prototype.safetensors module that transformers 4.57 expects
RUN python3 -c "import torchao, pathlib; stub = pathlib.Path(torchao.__file__).parent / 'prototype' / 'safetensors'; stub.mkdir(parents=True, exist_ok=True); (stub / '__init__.py').write_text(''); (stub / 'safetensors_utils.py').write_text('def load_model_as_uint4(*a, **kw): raise NotImplementedError\ndef is_metadata_torchao(*a, **kw): return False\ndef get_torchao_quantization_type(*a, **kw): return None\n')"
RUN cd /opt/LTX-2 && pip install --no-cache-dir --no-deps \
    -e packages/ltx-core \
    -e packages/ltx-pipelines
# multigpu module is referenced by blocks.py but not yet committed upstream.
# Create a stub for single-GPU operation.
RUN mkdir -p /opt/LTX-2/packages/ltx-pipelines/src/ltx_pipelines/multigpu \
    && printf 'class DelegatingBuilder:\n    pass\n' \
       > /opt/LTX-2/packages/ltx-pipelines/src/ltx_pipelines/multigpu/delegating_builder.py \
    && touch /opt/LTX-2/packages/ltx-pipelines/src/ltx_pipelines/multigpu/__init__.py

ENV PYTORCH_ALLOC_CONF=expandable_segments:True

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
