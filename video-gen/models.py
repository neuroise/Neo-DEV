"""
Pydantic models for the Video Generation API.

Defines request/response schemas for all endpoints.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VideoModel(str, Enum):
    """Supported video generation models."""
    WAN_TI2V_5B = "wan2.2-ti2v-5b"
    WAN_T2V_A14B = "wan2.2-t2v-a14b"
    TURBO_1_3B = "turbowanv2-t2v-1.3b"
    TURBO_14B = "turbowanv2-t2v-14b"


# Model metadata for /models endpoint
MODEL_INFO = {
    VideoModel.WAN_TI2V_5B: {
        "name": "Wan2.2-TI2V-5B",
        "params": "5B",
        "vram_gb": 24,
        "speed": "slow",
        "description": "Text/Image-to-Video, most reliable quality",
    },
    VideoModel.WAN_T2V_A14B: {
        "name": "Wan2.2-T2V-A14B",
        "params": "14B active (27B total MoE)",
        "vram_gb": 80,
        "speed": "very_slow",
        "description": "Highest quality, MoE architecture, needs CPU offloading",
    },
    VideoModel.TURBO_1_3B: {
        "name": "TurboWanV2-T2V-1.3B",
        "params": "1.3B",
        "vram_gb": 3,
        "speed": "fast",
        "description": "Fastest generation, lower quality",
    },
    VideoModel.TURBO_14B: {
        "name": "TurboWanV2-T2V-14B",
        "params": "14B",
        "vram_gb": 27,
        "speed": "medium",
        "description": "Fast generation with good quality",
    },
}


class GenerateRequest(BaseModel):
    """Request to generate a single video."""
    prompt: str = Field(..., min_length=1, max_length=2000)
    model: VideoModel = VideoModel.WAN_TI2V_5B
    negative_prompt: str = Field(
        default="blurry, low quality, distorted, watermark, text, logo",
        max_length=1000,
    )
    num_frames: int = Field(default=81, ge=17, le=129)
    width: int = Field(default=832, ge=256, le=1280)
    height: int = Field(default=480, ge=256, le=720)
    guidance_scale: float = Field(default=5.0, ge=1.0, le=20.0)
    num_inference_steps: Optional[int] = None  # model-dependent default
    seed: Optional[int] = None


class JobState(str, Enum):
    """Job lifecycle states."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(BaseModel):
    """Status of a generation job."""
    job_id: str
    state: JobState
    model: VideoModel
    prompt: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    video_url: Optional[str] = None
    error: Optional[str] = None
    elapsed_seconds: Optional[float] = None


class TriptychScene(BaseModel):
    """A single scene in a triptych request."""
    role: str = Field(..., pattern="^(start|evolve|end)$")
    prompt: str = Field(..., min_length=1, max_length=2000)


class TriptychRequest(BaseModel):
    """Request to generate a full video triptych (3 scenes)."""
    scenes: List[TriptychScene] = Field(..., min_length=3, max_length=3)
    model: VideoModel = VideoModel.WAN_TI2V_5B
    negative_prompt: str = Field(
        default="blurry, low quality, distorted, watermark, text, logo",
        max_length=1000,
    )
    num_frames: int = Field(default=81, ge=17, le=129)
    width: int = Field(default=832, ge=256, le=1280)
    height: int = Field(default=480, ge=256, le=720)
    guidance_scale: float = Field(default=5.0, ge=1.0, le=20.0)
    num_inference_steps: Optional[int] = None
    seed: Optional[int] = None


class TriptychJobStatus(BaseModel):
    """Status of a triptych generation (3 sub-jobs)."""
    triptych_id: str
    state: JobState
    scenes: List[JobStatus]
    progress: float = Field(default=0.0, ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    loaded_model: Optional[str] = None


class ModelsResponse(BaseModel):
    """Response listing available models."""
    models: list
    default: str = VideoModel.WAN_TI2V_5B.value
