"""
HTTP client for the Video Generation API.

Follows the same adapter pattern as OllamaAdapter: wraps HTTP calls
to the video-gen FastAPI service with a clean Python interface.

Example:
    >>> client = VideoClient("http://localhost:8000")
    >>> job = client.submit("calm ocean at sunset")
    >>> status = client.poll(job["job_id"], wait=True)
    >>> client.download(job["job_id"], "output.mp4", "/tmp/video.mp4")
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests

logger = logging.getLogger(__name__)


class VideoClient:
    """
    Client for the NEUROISE Video Generation API.

    Attributes:
        base_url: URL of the video-gen service (default: http://localhost:8000)
    """

    DEFAULT_URL = "http://localhost:8000"

    # Available models (mirrors server-side VideoModel enum)
    MODELS = [
        "wan2.2-ti2v-5b",
        "wan2.2-t2v-a14b",
        "turbowanv2-t2v-1.3b",
        "turbowanv2-t2v-14b",
        "ltx-2.3-distilled",
        "ltx-2.3-full",
    ]

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (
            base_url
            or os.environ.get("VIDEO_GEN_URL")
            or self.DEFAULT_URL
        )

    def health(self) -> Dict[str, Any]:
        """Check service health. Returns dict with gpu info."""
        r = requests.get(f"{self.base_url}/health", timeout=5)
        r.raise_for_status()
        return r.json()

    def is_available(self) -> bool:
        """Check if the video-gen service is reachable."""
        try:
            h = self.health()
            return h.get("status") == "ok"
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """List available video generation models."""
        r = requests.get(f"{self.base_url}/models", timeout=5)
        r.raise_for_status()
        return r.json().get("models", [])

    def submit(
        self,
        prompt: str,
        model: str = "wan2.2-ti2v-5b",
        negative_prompt: Optional[str] = None,
        num_frames: int = 81,
        width: int = 832,
        height: int = 480,
        guidance_scale: float = 5.0,
        num_inference_steps: Optional[int] = None,
        seed: Optional[int] = None,
        audio_enabled: bool = True,
        reference_image_b64: Optional[str] = None,
        mode: str = "t2v",
        use_fp8: bool = False,
        frame_rate: float = 25.0,
    ) -> Dict[str, Any]:
        """
        Submit a single video generation job.

        Returns immediately with job metadata including job_id.
        """
        payload = {
            "prompt": prompt,
            "model": model,
            "num_frames": num_frames,
            "width": width,
            "height": height,
            "guidance_scale": guidance_scale,
            "audio_enabled": audio_enabled,
            "mode": mode,
            "use_fp8": use_fp8,
            "frame_rate": frame_rate,
        }
        if negative_prompt is not None:
            payload["negative_prompt"] = negative_prompt
        if num_inference_steps is not None:
            payload["num_inference_steps"] = num_inference_steps
        if seed is not None:
            payload["seed"] = seed
        if reference_image_b64 is not None:
            payload["reference_image_b64"] = reference_image_b64

        r = requests.post(f"{self.base_url}/generate", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def submit_triptych(
        self,
        scenes: List[Dict[str, str]],
        model: str = "wan2.2-ti2v-5b",
        audio_enabled: bool = True,
        use_fp8: bool = False,
        frame_rate: float = 25.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Submit a triptych generation (3 scenes: start, evolve, end).

        Args:
            scenes: List of 3 dicts with 'role' and 'prompt' keys
            model: Model to use
            audio_enabled: Generate audio with video (LTX models)
            use_fp8: Use FP8 quantization
            **kwargs: Additional generation params

        Returns:
            Triptych job metadata including triptych_id and scene sub-jobs.
        """
        payload = {
            "scenes": scenes,
            "model": model,
            "audio_enabled": audio_enabled,
            "use_fp8": use_fp8,
            "frame_rate": frame_rate,
            **kwargs,
        }
        r = requests.post(
            f"{self.base_url}/generate/triptych",
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get current status of a generation job."""
        r = requests.get(f"{self.base_url}/jobs/{job_id}", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_triptych(self, triptych_id: str) -> Dict[str, Any]:
        """Get current status of a triptych generation."""
        r = requests.get(
            f"{self.base_url}/triptych/{triptych_id}", timeout=10
        )
        r.raise_for_status()
        return r.json()

    def poll(
        self,
        job_id: str,
        wait: bool = True,
        interval: float = 2.0,
        timeout: float = 1800.0,
    ) -> Dict[str, Any]:
        """
        Poll a job until completion (or just check once).

        Args:
            job_id: Job ID to poll
            wait: If True, blocks until job completes or fails
            interval: Seconds between polls
            timeout: Max wait time in seconds

        Returns:
            Final job status dict
        """
        deadline = time.time() + timeout
        while True:
            status = self.get_job(job_id)
            state = status.get("state")
            if not wait or state in ("completed", "failed"):
                return status
            if time.time() > deadline:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout}s"
                )
            time.sleep(interval)

    def poll_triptych(
        self,
        triptych_id: str,
        wait: bool = True,
        interval: float = 3.0,
        timeout: float = 3600.0,
    ) -> Dict[str, Any]:
        """Poll a triptych job until all scenes complete."""
        deadline = time.time() + timeout
        while True:
            status = self.get_triptych(triptych_id)
            state = status.get("state")
            if not wait or state in ("completed", "failed"):
                return status
            if time.time() > deadline:
                raise TimeoutError(
                    f"Triptych {triptych_id} did not complete within {timeout}s"
                )
            time.sleep(interval)

    def download(
        self,
        job_id: str,
        filename: str = "output.mp4",
        dest_path: Optional[str] = None,
    ) -> Path:
        """
        Download a generated video to local filesystem.

        Args:
            job_id: Job ID
            filename: Filename on server (default: output.mp4)
            dest_path: Local destination path. If None, saves to
                       data/outputs/videos/{job_id}/{filename}

        Returns:
            Path to downloaded file
        """
        if dest_path is None:
            dest = (
                Path(__file__).parent.parent.parent
                / "data" / "outputs" / "videos" / job_id / filename
            )
        else:
            dest = Path(dest_path)

        dest.parent.mkdir(parents=True, exist_ok=True)

        r = requests.get(
            f"{self.base_url}/videos/{job_id}/{filename}",
            stream=True,
            timeout=60,
        )
        r.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded video to {dest}")
        return dest

    def download_triptych(
        self,
        triptych_status: Dict[str, Any],
        dest_dir: Optional[str] = None,
    ) -> List[Path]:
        """
        Download all videos from a completed triptych.

        Returns:
            List of Paths to the 3 downloaded video files.
        """
        paths = []
        for scene in triptych_status.get("scenes", []):
            if scene.get("state") == "completed" and scene.get("video_url"):
                job_id = scene["job_id"]
                path = self.download(job_id, "output.mp4", dest_path=dest_dir)
                paths.append(path)
        return paths

    @staticmethod
    def compose_ltx_prompt(
        visual_prompt: str,
        ost_prompt: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Compose a single LTX prompt from visual description + OST metadata."""
        if not ost_prompt:
            return visual_prompt

        parts = [visual_prompt]
        audio_parts = []
        if ost_prompt.get("prompt"):
            audio_parts.append(ost_prompt["prompt"])
        if ost_prompt.get("genre"):
            audio_parts.append(f"Genre: {ost_prompt['genre']}")
        if ost_prompt.get("bpm"):
            audio_parts.append(f"{ost_prompt['bpm']} BPM")
        if ost_prompt.get("mood"):
            audio_parts.append(f"Mood: {ost_prompt['mood']}")
        if ost_prompt.get("instruments_hint"):
            audio_parts.append(f"Instruments: {ost_prompt['instruments_hint']}")

        if audio_parts:
            parts.append("Background music: " + ", ".join(audio_parts))

        return ". ".join(parts)
