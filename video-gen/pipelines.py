"""
Pipeline loading and inference for video generation models.

Supports:
- Wan2.2-TI2V-5B (diffusers WanPipeline)
- Wan2.2-T2V-A14B (diffusers WanPipeline with CPU offloading)
- TurboWanV2-T2V-1.3B (turbodiffusion)
- TurboWanV2-T2V-14B (turbodiffusion)
"""

import argparse
import gc
import logging
import math
import os
import time
from typing import Optional, Callable

import numpy as np
import torch
from PIL import Image

from models import VideoModel

logger = logging.getLogger(__name__)

# HuggingFace model IDs (diffusers-compatible versions)
MODEL_REPOS = {
    VideoModel.WAN_TI2V_5B: "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
    VideoModel.WAN_T2V_A14B: "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
    VideoModel.TURBO_1_3B: "TurboDiffusion/TurboWan2.1-T2V-1.3B-480P",
    VideoModel.TURBO_14B: "TurboDiffusion/TurboWan2.1-T2V-14B-480P",
}

# Default inference steps per model
DEFAULT_STEPS = {
    VideoModel.WAN_TI2V_5B: 50,
    VideoModel.WAN_T2V_A14B: 50,
    VideoModel.TURBO_1_3B: 4,
    VideoModel.TURBO_14B: 8,
}

# TurboDiffusion checkpoint directory (under cache_dir)
TURBO_CHECKPOINT_DIR = "turbo"

# DiT checkpoint filenames per turbo model
TURBO_DIT_PATHS = {
    VideoModel.TURBO_1_3B: "TurboWan2.1-T2V-1.3B-480P.pth",
    VideoModel.TURBO_14B: "TurboWan2.1-T2V-14B-480P.pth",
}

# TurboDiffusion model architecture names
TURBO_MODEL_ARCH = {
    VideoModel.TURBO_1_3B: "Wan2.1-1.3B",
    VideoModel.TURBO_14B: "Wan2.1-14B",
}

# Module-level singleton for TurboDiffusion UMT5 text encoder
_turbo_t5_encoder = None


def _clear_turbo_text_encoder():
    """Free the global TurboDiffusion text encoder from GPU memory."""
    global _turbo_t5_encoder
    if _turbo_t5_encoder is not None:
        del _turbo_t5_encoder
        _turbo_t5_encoder = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


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
        # TurboDiffusion components (loaded separately from diffusers pipeline)
        self._turbo_net = None
        self._turbo_tokenizer = None
        self._turbo_args = None

    @property
    def loaded_model(self) -> Optional[str]:
        return self._current_model.value if self._current_model else None

    def unload(self):
        """Unload current pipeline and free GPU memory."""
        if self._pipeline is not None:
            logger.info(f"Unloading model {self._current_model}")
            # Clean up turbo-specific components
            if self._turbo_net is not None:
                del self._turbo_net
                self._turbo_net = None
            if self._turbo_tokenizer is not None:
                del self._turbo_tokenizer
                self._turbo_tokenizer = None
            self._turbo_args = None
            _clear_turbo_text_encoder()
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
        """Load TurboWan pipeline via turbodiffusion.

        Uses the TurboDiffusion custom API (not diffusers-compatible).
        Requires local checkpoint files downloaded via scripts/download_turbo_checkpoints.sh.
        """
        turbo_dir = os.path.join(self.cache_dir, TURBO_CHECKPOINT_DIR)
        dit_filename = TURBO_DIT_PATHS[model]
        dit_path = os.path.join(turbo_dir, dit_filename)
        vae_path = os.path.join(turbo_dir, "Wan2.1_VAE.pth")

        # Check checkpoints exist
        for path, name in [(dit_path, "DiT"), (vae_path, "VAE")]:
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"{name} checkpoint not found at {path}. "
                    "Run: docker exec <container> bash /app/scripts/download_turbo_checkpoints.sh"
                )

        # Import VAE tokenizer (no CUDA ops dependency)
        try:
            from rcm.tokenizers.wan2pt1 import Wan2pt1VAEInterface
        except ImportError as e:
            raise RuntimeError(
                f"TurboDiffusion modules not available: {e}. "
                "Ensure the container was built with the TurboDiffusion repo clone."
            )

        # Determine best available attention type:
        #   sagesla > sla > original
        # Checkpoint was fine-tuned with SLA, so we MUST use at least "sla"
        # to match state_dict keys (local_attn.proj_l weights).
        attention_type = "sla"
        try:
            from SLA import SageSparseLinearAttention  # noqa: F401
            import spargeattn  # noqa: F401
            attention_type = "sagesla"
            logger.info("SageSLA available — using optimized attention")
        except (ImportError, OSError):
            logger.info("SageSLA not available, using plain SLA attention")

        # Try full create_model (needs CUDA ops for norm/quant),
        # fall back to minimal loader if ops aren't compiled
        create_fn = None
        use_full_api = False
        try:
            from modify_model import create_model as _cm
            create_fn = _cm
            use_full_api = True
            logger.info("TurboDiffusion CUDA ops available — using optimized model loader")
        except (ImportError, OSError) as e:
            logger.warning(
                f"TurboDiffusion CUDA ops not available ({e}), "
                "using fallback loader (original attention, no quantization)"
            )

        # Load VAE
        logger.info(f"Loading TurboWan VAE from {vae_path}")
        tokenizer = Wan2pt1VAEInterface(
            chunk_duration=81,
            vae_pth=vae_path,
        )

        # Load DiT
        logger.info(f"Loading TurboWan DiT from {dit_path}")
        if use_full_api:
            args = argparse.Namespace(
                model=TURBO_MODEL_ARCH[model],
                attention_type=attention_type,
                sla_topk=0.1,
                quant_linear=False,
                default_norm=(attention_type == "original"),
            )
            net = create_fn(dit_path=dit_path, args=args)
        else:
            net = self._create_model_fallback(
                TURBO_MODEL_ARCH[model], dit_path, attention_type,
            )

        self._turbo_net = net
        self._turbo_tokenizer = tokenizer
        self._turbo_args = None
        # Set _pipeline as sentinel so generate() knows a model is loaded
        self._pipeline = True

    @staticmethod
    def _create_model_fallback(
        model_name: str, dit_path: str, attention_type: str = "sla",
    ) -> torch.nn.Module:
        """Minimal model loader without CUDA ops dependency.

        Supports SLA attention (needed for checkpoint compatibility) but not
        SageSLA or quantization. Used when turbo_diffusion_ops aren't compiled.
        """
        from rcm.networks.wan2pt1 import WanModel
        from rcm.utils.model_utils import load_state_dict

        MODEL_CONFIGS = {
            "Wan2.1-1.3B": dict(
                dim=1536, eps=1e-6, ffn_dim=8960, freq_dim=256,
                in_dim=16, model_type="t2v", num_heads=12, num_layers=30,
                out_dim=16, text_len=512,
            ),
            "Wan2.1-14B": dict(
                dim=5120, eps=1e-6, ffn_dim=13824, freq_dim=256,
                in_dim=16, model_type="t2v", num_heads=40, num_layers=40,
                out_dim=16, text_len=512,
            ),
        }

        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}")

        with torch.device("meta"):
            net = WanModel(**MODEL_CONFIGS[model_name])

        # Checkpoint was fine-tuned with SLA — add SLA layers before loading
        if attention_type in ("sla", "sagesla"):
            try:
                from SLA import SparseLinearAttention as SLA
                from rcm.networks.wan2pt1 import WanSelfAttention
                cfg = MODEL_CONFIGS[model_name]
                head_dim = cfg["dim"] // cfg["num_heads"]
                for module in net.modules():
                    if isinstance(module, WanSelfAttention):
                        module.attn_op.local_attn = SLA(
                            head_dim=head_dim, topk=0.1, BLKQ=128, BLKK=64,
                        )
                logger.info("SLA attention layers added for checkpoint compatibility")
            except ImportError as e:
                logger.warning(f"SLA not available ({e}), loading with strict=False")
                attention_type = "original"

        state_dict = load_state_dict(dit_path)
        strict = attention_type != "original"
        net.load_state_dict(state_dict, assign=True, strict=strict)
        net = net.to(device="cuda", dtype=torch.bfloat16).eval()
        del state_dict
        return net

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

        # Dispatch turbo models to dedicated generation path
        if model in (VideoModel.TURBO_1_3B, VideoModel.TURBO_14B):
            return self._generate_turbo(
                prompt, num_frames, width, height, steps, seed, progress_callback,
            )

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

    def _generate_turbo(
        self,
        prompt: str,
        num_frames: int,
        width: int,
        height: int,
        steps: int,
        seed: Optional[int],
        progress_callback: Optional[Callable[[float], None]],
    ) -> list:
        """
        Generate video frames using TurboDiffusion sampling loop.

        Implements the RectifiedFlow sampling from TurboDiffusion serve/pipeline.py
        with TrigFlow→RectifiedFlow timestep conversion.

        Returns:
            List of PIL Image frames.
        """
        global _turbo_t5_encoder

        net = self._turbo_net
        tokenizer = self._turbo_tokenizer

        # Validate dimensions (must be multiples of 16 = spatial_compression * 2)
        if width % 16 != 0:
            old_w = width
            width = round(width / 16) * 16
            logger.warning(f"Width {old_w} not multiple of 16, rounded to {width}")
        if height % 16 != 0:
            old_h = height
            height = round(height / 16) * 16
            logger.warning(f"Height {old_h} not multiple of 16, rounded to {height}")

        tensor_kwargs = {"device": "cuda", "dtype": torch.bfloat16}

        # --- Text embedding ---
        t5_ckpt = os.path.join(
            self.cache_dir, TURBO_CHECKPOINT_DIR, "models_t5_umt5-xxl-enc-bf16.pth",
        )
        t5_tokenizer_path = os.path.join(
            self.cache_dir, TURBO_CHECKPOINT_DIR, "google", "umt5-xxl",
        )
        if not os.path.exists(t5_ckpt):
            raise FileNotFoundError(
                f"UMT5 checkpoint not found at {t5_ckpt}. "
                "Run: docker exec <container> bash /app/scripts/download_turbo_checkpoints.sh"
            )

        logger.info(f"Computing text embedding for: {prompt[:80]}...")
        if _turbo_t5_encoder is None:
            from rcm.utils.umt5 import UMT5EncoderModel
            _turbo_t5_encoder = UMT5EncoderModel(
                text_len=512,
                dtype=torch.bfloat16,
                device="cuda",
                checkpoint_path=t5_ckpt,
                tokenizer_path=t5_tokenizer_path,
            )

        with torch.no_grad():
            text_emb = _turbo_t5_encoder(prompt).to(**tensor_kwargs)

        condition = {"crossattn_emb": text_emb}

        # --- Latent dimensions ---
        state_shape = [
            tokenizer.latent_ch,                                    # 16
            tokenizer.get_latent_num_frames(num_frames),            # (T-1)//4 + 1
            height // tokenizer.spatial_compression_factor,         # H // 8
            width // tokenizer.spatial_compression_factor,          # W // 8
        ]

        # --- Noise initialization ---
        generator = torch.Generator(device="cuda")
        if seed is not None:
            generator.manual_seed(seed)
        else:
            generator.seed()

        init_noise = torch.randn(
            1, *state_shape,
            dtype=torch.float32,
            device="cuda",
            generator=generator,
        )

        # --- TrigFlow timestep schedule ---
        sigma_max = 80  # T2V default
        mid_t = [1.5, 1.4, 1.0][: steps - 1]
        t_steps = torch.tensor(
            [math.atan(sigma_max), *mid_t, 0],
            dtype=torch.float64,
            device="cuda",
        )
        # TrigFlow → RectifiedFlow conversion
        t_steps = torch.sin(t_steps) / (torch.cos(t_steps) + torch.sin(t_steps))

        x = init_noise.to(torch.float64) * t_steps[0]
        ones = torch.ones(x.size(0), 1, device=x.device, dtype=x.dtype)
        total_steps = t_steps.shape[0] - 1

        # --- Sampling loop ---
        logger.info(f"Sampling with {total_steps} steps...")
        for i, (t_cur, t_next) in enumerate(zip(t_steps[:-1], t_steps[1:])):
            with torch.no_grad():
                v_pred = net(
                    x_B_C_T_H_W=x.to(**tensor_kwargs),
                    timesteps_B_T=(t_cur.float() * ones * 1000).to(**tensor_kwargs),
                    **condition,
                ).to(torch.float64)

                x = (1 - t_next) * (x - t_cur * v_pred) + t_next * torch.randn(
                    *x.shape,
                    dtype=torch.float32,
                    device="cuda",
                    generator=generator,
                )

            if progress_callback:
                progress_callback((i + 1) / total_steps)

        # --- VAE decode ---
        logger.info("Decoding video with VAE...")
        samples = x.float()
        with torch.no_grad():
            video = tokenizer.decode(samples)
        # video shape: [B, C, T, H, W], range [-1, 1]
        video = (1.0 + video.float().cpu().clamp(-1, 1)) / 2.0  # → [0, 1]

        # --- Convert to list of PIL Images ---
        frames_tensor = video[0]                              # [C, T, H, W]
        frames_tensor = frames_tensor.permute(1, 2, 3, 0)    # [T, H, W, C]
        frames_np = (frames_tensor.numpy() * 255).astype(np.uint8)
        frames = [Image.fromarray(frames_np[t]) for t in range(frames_np.shape[0])]

        if progress_callback:
            progress_callback(1.0)

        return frames
