"""FFmpeg implementation of the MediaRenderer interface.

Assembles multiple video clips, voiceover narration, background music,
brand logos, and CTA overlays into a production-ready MP4 advertisement.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from app.interfaces.media_renderer import MediaRenderer

logger = logging.getLogger(__name__)

# Standard font candidates
DEFAULT_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]


def find_system_font() -> str | None:
    """Find an available TrueType font file on the system."""
    for p in DEFAULT_FONT_PATHS:
        if os.path.exists(p):
            return p
    return None


async def get_media_duration(file_path: str) -> float:
    """Query duration in seconds using ffprobe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            return float(stdout.decode().strip())
    except Exception as e:
        logger.warning(f"Could not read duration for {file_path}: {e}")
    return 0.0


class FFmpegMediaRenderer(MediaRenderer):
    """Media renderer utilizing FFmpeg subprocess filter graphs."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.font_path = find_system_font()

    async def render_advertisement(
        self,
        clip_paths: list[str],
        narration_path: str,
        output_path: str,
        music_path: str | None = None,
        logo_path: str | None = None,
        cta_text: str | None = None,
        captions: list[dict[str, str | float]] | None = None,
    ) -> str:
        """Compose clips, narration, optional music, logo watermark, and CTA into an MP4."""
        if not clip_paths:
            raise ValueError("Cannot render advertisement: clip_paths is empty.")

        for clip in clip_paths:
            if not os.path.isfile(clip):
                raise FileNotFoundError(f"Video clip not found: {clip}")

        if not os.path.isfile(narration_path):
            raise FileNotFoundError(f"Narration audio not found: {narration_path}")

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Assembling advertisement: {len(clip_paths)} clips + narration -> {dest}"
        )

        # Calculate durations to time overlays cleanly
        clip_durations = [await get_media_duration(c) for c in clip_paths]
        total_video_duration = sum(clip_durations) if all(d > 0 for d in clip_durations) else 15.0

        # Build FFmpeg command inputs and filter graph
        inputs: list[str] = []
        filter_complex_parts: list[str] = []

        # 1. Add clip inputs
        for clip in clip_paths:
            inputs.extend(["-i", clip])

        # 2. Add narration input
        narration_idx = len(clip_paths)
        inputs.extend(["-i", narration_path])

        # 3. Add optional background music input
        music_idx: int | None = None
        if music_path and os.path.isfile(music_path):
            music_idx = narration_idx + 1
            inputs.extend(["-i", music_path])

        # 4. Add optional brand logo input
        logo_idx: int | None = None
        if logo_path and os.path.isfile(logo_path):
            logo_idx = (music_idx + 1) if music_idx is not None else (narration_idx + 1)
            inputs.extend(["-i", logo_path])

        # --- Video Filter Graph ---
        # Normalize each video clip to 1080p 24fps with consistent SAR
        for i in range(len(clip_paths)):
            filter_complex_parts.append(
                f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{i}]"
            )

        # Concatenate normalized clips
        concat_inputs = "".join(f"[v{i}]" for i in range(len(clip_paths)))
        filter_complex_parts.append(
            f"{concat_inputs}concat=n={len(clip_paths)}:v=1:a=0[vconcat]"
        )

        current_v_stream = "vconcat"

        # Overlay Brand Logo if present (top-right with padding)
        if logo_idx is not None:
            filter_complex_parts.append(f"[{logo_idx}:v]scale=220:-1[scaled_logo]")
            filter_complex_parts.append(
                f"[{current_v_stream}][scaled_logo]overlay=W-w-40:40:format=auto[vlogo]"
            )
            current_v_stream = "vlogo"

        # Overlay CTA text if present (during final 3.5 seconds)
        if cta_text and cta_text.strip():
            escaped_cta = (
                cta_text.replace("'", "'\\''")
                .replace(":", "\\:")
                .replace("%", "\\%")
            )
            cta_start_t = max(0.0, total_video_duration - 3.5)

            font_arg = f":fontfile='{self.font_path}'" if self.font_path else ""
            filter_complex_parts.append(
                f"[{current_v_stream}]drawtext="
                f"text='{escaped_cta}'"
                f"{font_arg}:"
                f"fontcolor=white:fontsize=46:"
                f"box=1:boxcolor=black@0.65:boxborderw=18:"
                f"x=(w-text_w)/2:y=h-th-90:"
                f"enable='between(t,{cta_start_t:.2f},{total_video_duration + 5:.2f})'[vcta]"
            )
            current_v_stream = "vcta"

        # --- Audio Filter Graph ---
        # Mix narration with ducked background music if present
        if music_idx is not None:
            filter_complex_parts.append(f"[{narration_idx}:a]volume=1.0[voice]")
            filter_complex_parts.append(
                f"[{music_idx}:a]volume=0.18,aloop=loop=-1:size=2e+09[music_loop]"
            )
            filter_complex_parts.append(
                f"[voice][music_loop]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            current_a_stream = "aout"
        else:
            filter_complex_parts.append(f"[{narration_idx}:a]anull[aout]")
            current_a_stream = "aout"

        filter_complex = ";\n".join(filter_complex_parts)

        cmd = [
            self.ffmpeg_bin,
            "-y",  # Overwrite output
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current_v_stream}]",
            "-map", f"[{current_a_stream}]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-movflags", "+faststart",
            str(dest),
        ]

        logger.info(f"Executing FFmpeg assembly command:\n{' '.join(cmd[:15])}...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")[-1500:]
            logger.error(f"FFmpeg assembly failed (code {proc.returncode}):\n{err_msg}")
            raise RuntimeError(f"FFmpeg rendering failed with exit code {proc.returncode}: {err_msg}")

        logger.info(f"Final advertisement successfully rendered to {dest}")
        return str(dest)

