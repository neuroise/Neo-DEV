"""
Pipeline loading and inference for video generation models.

Supports:
- Wan2.2-TI2V-5B (diffusers WanPipeline)
- Wan2.2-T2V-A14B (diffusers WanPipeline with CPU offloading)
- TurboWanV2-T2V-1.3B (turbodiffusion)
- TurboWanV2-T2V-14B (turbodiffusion)
"""

import gc
import logging
import time
from typing import Optional, Callable

import torch

from models import VideoModel

logger = logging.getLogger(__name__)

# HuggingFace model IDs (diffusers-compatible versions)
MODEL_REPOS = {
    VideoModel.WAN_TI2V_5B: "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
    VideoModel.WAN_T2V_A14B: "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
    VideoModel.TURBO_1_3B: "turbodiffusion-v2/TurboWanV2-T2V-1.3B",
    VideoModel.TURBO_14B: "turbodiffusion-v2/TurboWanV2-T2V-14B",
}

# Default inference steps per model
DEFAULT_STEPS = {
    VideoModel.WAN_TI2V_5B: 50,
    VideoModel.WAN_T2V_A14B: 50,
    VideoModel.TURBO_1_3B: 4,
    VideoModel.TURBO_14B: 8,
}


class PipelineManager:
    """
    Manages loading and switching between video generation pipelines.

    Only one pipeline is loaded at a time to conserve GPU memory.
    Switching models triggers unloading of the current pipeline.
    """

    def __init__(self, cache_dir: str = "/models"):
        self.cache_dir = cache_dir
        self._current_model: Optional[VideoModel] = None
        self._pipeline = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

    @property
    def loaded_model(self) -> Optional[str]:
        return self._current_model.value if self._current_model else None

    def unload(self):
        """Unload current pipeline and free GPU memory."""
        if self._pipeline is not None:
            logger.info(f"Unloading model {self._current_model}")
            del self._pipeline
            self._pipeline = None
            self._current_model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

    def load(self, model: VideoModel):
        """
        Load a pipeline for the given model.

        If a different model is already loaded, unloads it first.
        """
        if self._current_model == model and self._pipeline is not None:
            logger.info(f"Model {model.value} already loaded")
            return

        self.unload()
        logger.info(f"Loading model {model.value}...")
        start = time.time()

        if model in (VideoModel.TURBO_1_3B, VideoModel.TURBO_14B):
            self._load_turbo(model)
        else:
            self._load_wan(model)

        self._current_model = model
        elapsed = time.time() - start
        logger.info(f"Model {model.value} loaded in {elapsed:.1f}s")

    def _load_wan(self, model: VideoModel):
        """Load Wan2.2 pipeline via diffusers."""
        from diffusers import WanPipeline, AutoencoderKLWan
        from transformers import UMT5EncoderModel

        repo = MODEL_REPOS[model]

        # Load text encoder explicitly - fix weight tying for embed_tokens
        text_encoder = UMT5EncoderModel.from_pretrained(
            repo,
            subfolder="text_encoder",
            torch_dtype=torch.bfloat16,
            cache_dir=self.cache_dir,
        )
        # UMT5 uses shared.weight but embed_tokens expects it via weight tying
        if hasattr(text_encoder, 'shared') and text_encoder.shared.weight is not None:
            embed = text_encoder.encoder.embed_tokens.weight
            if embed.abs().sum() == 0:
                logger.info("Fixing embed_tokens weight from shared.weight")
                text_encoder.encoder.embed_tokens.weight = text_encoder.shared.weight

        vae = AutoencoderKLWan.from_pretrained(
            repo,
            subfolder="vae",
            torch_dtype=torch.float32,
            cache_dir=self.cache_dir,
        )

        pipe = WanPipeline.from_pretrained(
            repo,
            text_encoder=text_encoder,
            vae=vae,
            torch_dtype=torch.bfloat16,
            cache_dir=self.cache_dir,
        )

        # Memory optimization based on model size
        if model == VideoModel.WAN_T2V_A14B:
            # 14B MoE needs aggressive offloading
            pipe.enable_model_cpu_offload()
        else:
            pipe.to(self._device)

        self._pipeline = pipe

    def _load_turbo(self, model: VideoModel):
        """Load TurboWan pipeline via turbodiffusion."""
        from turbodiffusion import TurboWanPipeline

        repo = MODEL_REPOS[model]
        pipe = TurboWanPipeline.from_pretrained(
            repo,
            torch_dtype=torch.bfloat16,
            cache_dir=self.cache_dir,
        )
        pipe.to(self._device)
        self._pipeline = pipe

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        num_frames: int = 81,
        width: int = 832,
        height: int = 480,
        guidance_scale: float = 5.0,
        num_inference_steps: Optional[int] = None,
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> list:
        """
        Generate video frames from a text prompt.

        Args:
            prompt: Text description of the video
            negative_prompt: What to avoid
            num_frames: Number of frames (must be 4k+1 for Wan)
            width: Video width
            height: Video height
            guidance_scale: CFG scale
            num_inference_steps: Override default steps
            seed: Random seed for reproducibility
            progress_callback: Called with float 0.0-1.0 during generation

        Returns:
            List of PIL Image frames
        """
        if self._pipeline is None:
            raise RuntimeError("No model loaded. Call load() first.")

        model = self._current_model
        steps = num_inference_steps or DEFAULT_STEPS.get(model, 50)

        generator = None
        if seed is not None:
            generator = torch.Generator(device=self._device).manual_seed(seed)

        # Build callback for progress tracking
        def step_callback(pipe, step, timestep, kwargs):
            if progress_callback:
                progress_callback(step / steps)
            return kwargs

        kwargs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_frames": num_frames,
            "width": width,
            "height": height,
            "guidance_scale": guidance_scale,
            "num_inference_steps": steps,
            "generator": generator,
            "callback_on_step_end": step_callback,
        }

        # TurboWan doesn't use negative_prompt
        if model in (VideoModel.TURBO_1_3B, VideoModel.TURBO_14B):
            kwargs.pop("negative_prompt", None)

        with torch.inference_mode():
            output = self._pipeline(**kwargs)

        # Extract frames - diffusers returns .frames[0] as list of PIL images
        if hasattr(output, "frames"):
            frames = output.frames[0]
        else:
            frames = output

        if progress_callback:
            progress_callback(1.0)

        return frames
