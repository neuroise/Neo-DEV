"""
Pydantic models for the Video Generation API.

Defines request/response schemas for all endpoints.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class VideoModel(str, Enum):
    """Supported video generation models."""
    WAN_TI2V_5B = "wan2.2-ti2v-5b"
    WAN_T2V_A14B = "wan2.2-t2v-a14b"
    TURBO_1_3B = "turbowanv2-t2v-1.3b"
    TURBO_14B = "turbowanv2-t2v-14b"
    LTX_23_DISTILLED = "ltx-2.3-distilled"
    LTX_23_FULL = "ltx-2.3-full"


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
        "vram_gb": 16,
        "speed": "fast",
        "description": "Fastest generation (4 steps), good quality at 480p",
    },
    VideoModel.TURBO_14B: {
        "name": "TurboWanV2-T2V-14B",
        "params": "14B",
        "vram_gb": 45,
        "speed": "medium",
        "description": "Fast generation (4-8 steps) with high quality at 480p",
    },
    VideoModel.LTX_23_DISTILLED: {
        "name": "LTX-2.3 Distilled",
        "params": "22B (8-step distilled)",
        "vram_gb": 30,
        "speed": "fast",
        "description": "Fast video+audio generation, 8 inference steps",
        "capabilities": ["t2v", "i2v", "audio"],
    },
    VideoModel.LTX_23_FULL: {
        "name": "LTX-2.3 Full",
        "params": "22B (bf16)",
        "vram_gb": 42,
        "speed": "slow",
        "description": "Highest quality video+audio generation",
        "capabilities": ["t2v", "i2v", "audio"],
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
    num_frames: int = Field(default=81, ge=9, le=513)
    width: int = Field(default=832, ge=256, le=1920)
    height: int = Field(default=480, ge=256, le=1088)
    guidance_scale: float = Field(default=5.0, ge=1.0, le=20.0)
    num_inference_steps: Optional[int] = None  # model-dependent default
    seed: Optional[int] = None
    frame_rate: float = Field(default=25.0, ge=8.0, le=50.0)
    audio_enabled: bool = Field(default=True, description="Generate audio (LTX models only)")
    reference_image_b64: Optional[str] = Field(default=None, description="Base64 image for I2V mode")
    mode: str = Field(default="t2v", pattern="^(t2v|i2v)$")
    use_fp8: bool = Field(default=False, description="Use FP8 quantization (less VRAM)")

    @model_validator(mode="after")
    def validate_ltx_constraints(self):
        if self.model.value.startswith("ltx"):
            if self.width % 32 != 0:
                raise ValueError("LTX models require width divisible by 32")
            if self.height % 32 != 0:
                raise ValueError("LTX models require height divisible by 32")
            if (self.num_frames - 1) % 8 != 0:
                raise ValueError("LTX models require (num_frames - 1) divisible by 8")
        if self.mode == "i2v" and not self.reference_image_b64:
            raise ValueError("Image-to-video mode requires reference_image_b64")
        return self


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
    audio_included: bool = False
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
    num_frames: int = Field(default=81, ge=9, le=513)
    width: int = Field(default=832, ge=256, le=1920)
    height: int = Field(default=480, ge=256, le=1088)
    guidance_scale: float = Field(default=5.0, ge=1.0, le=20.0)
    num_inference_steps: Optional[int] = None
    seed: Optional[int] = None
    frame_rate: float = Field(default=25.0, ge=8.0, le=50.0)
    audio_enabled: bool = Field(default=True, description="Generate audio (LTX models only)")
    use_fp8: bool = Field(default=False, description="Use FP8 quantization")


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
