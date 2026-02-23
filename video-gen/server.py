"""
NEUROISE Video Generation API Server.

FastAPI service that wraps video generation pipelines (Wan2.2, TurboWan)
with async job management.

Endpoints:
    GET  /health           - GPU & service health
    GET  /models           - List available models
    POST /generate         - Submit single video generation job
    POST /generate/triptych - Submit triptych (3 scenes) generation
    GET  /jobs/{job_id}    - Poll job status
    GET  /videos/{job_id}/{filename} - Download generated video

Usage:
    uvicorn server:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from models import (
    GenerateRequest,
    TriptychRequest,
    JobState,
    JobStatus,
    TriptychJobStatus,
    HealthResponse,
    ModelsResponse,
    VideoModel,
    MODEL_INFO,
)
from pipelines import PipelineManager

# -- Config -------------------------------------------------------------------

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/outputs/videos"))
MODEL_CACHE = os.environ.get("MODEL_CACHE", "/models")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("neuroise-video")

# -- App & State --------------------------------------------------------------

app = FastAPI(
    title="NEUROISE Video Generation API",
    version="0.1.0",
    description="Generate videos from text prompts using Wan2.2 and TurboWan models.",
)

pipeline_manager = PipelineManager(cache_dir=MODEL_CACHE)
jobs: Dict[str, JobStatus] = {}
triptych_jobs: Dict[str, TriptychJobStatus] = {}
executor = ThreadPoolExecutor(max_workers=1)  # GPU bound: 1 at a time

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -- Helpers -------------------------------------------------------------------

def _save_video(frames: list, output_path: Path, fps: int = 16):
    """Save frames to mp4. Handles both float32 [0,1] and uint8 [0,255] frames."""
    import numpy as np

    def to_uint8(frame):
        arr = np.array(frame)
        if arr.dtype in (np.float32, np.float64):
            arr = np.clip(arr * 255, 0, 255).astype(np.uint8)
        return arr

    try:
        from diffusers.utils import export_to_video
        # export_to_video expects list of PIL or numpy uint8
        uint8_frames = [to_uint8(f) for f in frames]
        export_to_video(uint8_frames, str(output_path), fps=fps)
    except (ImportError, Exception):
        import imageio
        writer = imageio.get_writer(str(output_path), fps=fps, codec="libx264")
        for frame in frames:
            writer.append_data(to_uint8(frame))
        writer.close()


def _run_generation(job_id: str, req: GenerateRequest):
    """Background worker for a single generation job."""
    job = jobs[job_id]
    job.state = JobState.RUNNING
    start = time.time()

    try:
        pipeline_manager.load(req.model)

        def on_progress(p: float):
            job.progress = round(p, 3)

        frames = pipeline_manager.generate(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            num_frames=req.num_frames,
            width=req.width,
            height=req.height,
            guidance_scale=req.guidance_scale,
            num_inference_steps=req.num_inference_steps,
            seed=req.seed,
            progress_callback=on_progress,
        )

        # Save video
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        out_path = job_dir / "output.mp4"
        _save_video(frames, out_path)

        job.state = JobState.COMPLETED
        job.progress = 1.0
        job.video_url = f"/videos/{job_id}/output.mp4"
        job.elapsed_seconds = round(time.time() - start, 1)
        logger.info(f"Job {job_id} completed in {job.elapsed_seconds}s")

    except Exception as e:
        job.state = JobState.FAILED
        job.error = str(e)
        job.elapsed_seconds = round(time.time() - start, 1)
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)


def _run_triptych(triptych_id: str, req: TriptychRequest):
    """Background worker for triptych generation (3 sequential scenes)."""
    tri = triptych_jobs[triptych_id]
    tri.state = JobState.RUNNING

    try:
        pipeline_manager.load(req.model)

        for i, scene in enumerate(req.scenes):
            sub_job = tri.scenes[i]
            sub_job.state = JobState.RUNNING

            def on_progress(p: float):
                sub_job.progress = round(p, 3)
                tri.progress = round((i + p) / 3, 3)

            start = time.time()
            frames = pipeline_manager.generate(
                prompt=scene.prompt,
                negative_prompt=req.negative_prompt,
                num_frames=req.num_frames,
                width=req.width,
                height=req.height,
                guidance_scale=req.guidance_scale,
                num_inference_steps=req.num_inference_steps,
                seed=req.seed,
                progress_callback=on_progress,
            )

            job_dir = OUTPUT_DIR / sub_job.job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            out_path = job_dir / "output.mp4"
            _save_video(frames, out_path)

            sub_job.state = JobState.COMPLETED
            sub_job.progress = 1.0
            sub_job.video_url = f"/videos/{sub_job.job_id}/output.mp4"
            sub_job.elapsed_seconds = round(time.time() - start, 1)

        tri.state = JobState.COMPLETED
        tri.progress = 1.0
        logger.info(f"Triptych {triptych_id} completed")

    except Exception as e:
        tri.state = JobState.FAILED
        # Mark remaining scenes as failed
        for scene_job in tri.scenes:
            if scene_job.state != JobState.COMPLETED:
                scene_job.state = JobState.FAILED
                scene_job.error = str(e)
        logger.error(f"Triptych {triptych_id} failed: {e}", exc_info=True)


# -- Endpoints -----------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    """Check service health and GPU status."""
    resp = HealthResponse(status="ok")
    if torch.cuda.is_available():
        resp.gpu_available = True
        resp.gpu_name = torch.cuda.get_device_name(0)
        mem = torch.cuda.get_device_properties(0).total_memory
        resp.gpu_memory_gb = round(mem / (1024**3), 1)
    resp.loaded_model = pipeline_manager.loaded_model
    return resp


@app.get("/models", response_model=ModelsResponse)
def list_models():
    """List available video generation models."""
    models_list = []
    for model_enum, info in MODEL_INFO.items():
        models_list.append({
            "id": model_enum.value,
            "loaded": pipeline_manager.loaded_model == model_enum.value,
            **info,
        })
    return ModelsResponse(models=models_list)


@app.post("/generate", response_model=JobStatus)
def generate(req: GenerateRequest):
    """Submit a video generation job. Returns immediately with a job_id."""
    job_id = str(uuid.uuid4())[:12]
    job = JobStatus(
        job_id=job_id,
        state=JobState.QUEUED,
        model=req.model,
        prompt=req.prompt,
    )
    jobs[job_id] = job
    executor.submit(_run_generation, job_id, req)
    logger.info(f"Job {job_id} queued: model={req.model.value}, prompt={req.prompt[:80]}...")
    return job


@app.post("/generate/triptych", response_model=TriptychJobStatus)
def generate_triptych(req: TriptychRequest):
    """Submit a triptych generation (3 scenes). Returns immediately."""
    triptych_id = str(uuid.uuid4())[:12]

    scene_jobs = []
    for scene in req.scenes:
        sub_id = str(uuid.uuid4())[:12]
        sub_job = JobStatus(
            job_id=sub_id,
            state=JobState.QUEUED,
            model=req.model,
            prompt=scene.prompt,
        )
        jobs[sub_id] = sub_job
        scene_jobs.append(sub_job)

    tri = TriptychJobStatus(
        triptych_id=triptych_id,
        state=JobState.QUEUED,
        scenes=scene_jobs,
    )
    triptych_jobs[triptych_id] = tri
    executor.submit(_run_triptych, triptych_id, req)
    logger.info(f"Triptych {triptych_id} queued: {len(req.scenes)} scenes")
    return tri


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    """Poll status of a single generation job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return jobs[job_id]


@app.get("/triptych/{triptych_id}", response_model=TriptychJobStatus)
def get_triptych(triptych_id: str):
    """Poll status of a triptych generation."""
    if triptych_id not in triptych_jobs:
        raise HTTPException(status_code=404, detail=f"Triptych {triptych_id} not found")
    return triptych_jobs[triptych_id]


@app.get("/videos/{job_id}/{filename}")
def get_video(job_id: str, filename: str):
    """Download a generated video file."""
    # Sanitize filename to prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    video_path = OUTPUT_DIR / job_id / filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename,
    )


@app.on_event("startup")
async def startup():
    logger.info(f"NEUROISE Video Gen API starting on port 8000")
    logger.info(f"Output dir: {OUTPUT_DIR}")
    logger.info(f"Model cache: {MODEL_CACHE}")
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logger.info(f"GPU Memory: {mem_gb:.1f} GB")
    else:
        logger.warning("No GPU available - generation will be extremely slow")
