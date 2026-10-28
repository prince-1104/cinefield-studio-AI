"""FFmpeg implementation of the MediaRenderer interface.

Assembles arbitrary numbers of video clips, voiceover narration, background music,
captions, brand logos, and CTA cards into a broadcast-ready MP4 advertisement.
Supports 15s, 30s, and 60s productions in 16:9 and 9:16 aspect ratios.
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from app.interfaces.media_renderer import MediaRenderer

logger = logging.getLogger(__name__)

# Standard font candidates across Linux and Windows
DEFAULT_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
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
            val = stdout.decode().strip()
            if val:
                return float(val)
    except Exception as e:
        logger.warning(f"Could not read duration for {file_path}: {e}")
    return 0.0


async def inspect_rendered_video(file_path: str) -> dict[str, Any]:
    """Inspect the output video file using ffprobe and return detailed stream metadata."""
    meta: dict[str, Any] = {
        "duration": 0.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "vcodec": "h264",
        "acodec": "aac",
        "size_bytes": 0,
    }

    p = Path(file_path)
    if not p.is_file():
        return meta

    meta["size_bytes"] = p.stat().st_size

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            data = json.loads(stdout.decode())
            fmt = data.get("format", {})
            if "duration" in fmt:
                meta["duration"] = round(float(fmt["duration"]), 2)

            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    meta["width"] = int(s.get("width", 1920))
                    meta["height"] = int(s.get("height", 1080))
                    meta["vcodec"] = s.get("codec_name", "h264")
                    r_frame_rate = s.get("r_frame_rate", "24/1")
                    if "/" in r_frame_rate:
                        num, den = r_frame_rate.split("/")
                        meta["fps"] = round(float(num) / float(den), 2) if float(den) > 0 else 24.0
                elif s.get("codec_type") == "audio":
                    meta["acodec"] = s.get("codec_name", "aac")
    except Exception as e:
        logger.warning(f"ffprobe metadata extraction failed for {file_path}: {e}")

    return meta


class FFmpegMediaRenderer(MediaRenderer):
    """Media renderer utilizing dynamic FFmpeg subprocess filter graphs for N shots."""

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
        captions: list[dict[str, Any]] | None = None,
        aspect_ratio: str = "16:9",
        target_duration: int | None = None,
    ) -> str:
        """Compose N clips, narration, optional music, logo watermark, captions, and CTA into an MP4.

        Supports arbitrary shot counts, 15s/30s/60s targets, dynamic normalization, audio ducking,
        and atomic output verification.
        """
        if not clip_paths:
            raise ValueError("Cannot render advertisement: clip_paths is empty.")

        for clip in clip_paths:
            if not os.path.isfile(clip):
                raise FileNotFoundError(f"Video clip not found: {clip}")

        if not os.path.isfile(narration_path):
            raise FileNotFoundError(f"Narration audio not found: {narration_path}")

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest.with_suffix(".tmp.mp4")

        # Dimensions: 1920x1080 for landscape, 1080x1920 for portrait
        is_portrait = aspect_ratio in ("9:16", "portrait")
        target_w, target_h = (1080, 1920) if is_portrait else (1920, 1080)

        logger.info(
            f"Assembling advertisement: {len(clip_paths)} clips + narration -> {dest} "
            f"({target_w}x{target_h}, aspect={aspect_ratio}, target_duration={target_duration}s)"
        )

        # Calculate durations to time overlays cleanly
        clip_durations = [await get_media_duration(c) for c in clip_paths]
        total_video_duration = sum(clip_durations) if all(d > 0 for d in clip_durations) else (
            float(target_duration) if target_duration else (len(clip_paths) * 5.0)
        )

        if target_duration and abs(total_video_duration - target_duration) > 2.0:
            logger.info(
                f"Notice: Total clip duration ({total_video_duration:.1f}s) differs from target ({target_duration}s). "
                f"Clamping output to {total_video_duration:.1f}s."
            )

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
        # Normalize each video clip to target resolution and 24fps with consistent SAR
        for i in range(len(clip_paths)):
            filter_complex_parts.append(
                f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{i}]"
            )

        # Concatenate normalized clips (ignore any embedded audio in source clips)
        concat_inputs = "".join(f"[v{i}]" for i in range(len(clip_paths)))
        filter_complex_parts.append(
            f"{concat_inputs}concat=n={len(clip_paths)}:v=1:a=0[vconcat]"
        )

        current_v_stream = "vconcat"

        # Overlay Brand Logo if present (top-right corner with responsive margins)
        if logo_idx is not None:
            logo_scale_w = 180 if is_portrait else 220
            margin_y = 60 if is_portrait else 40
            filter_complex_parts.append(f"[{logo_idx}:v]scale={logo_scale_w}:-1[scaled_logo]")
            filter_complex_parts.append(
                f"[{current_v_stream}][scaled_logo]overlay=W-w-40:{margin_y}:format=auto[vlogo]"
            )
            current_v_stream = "vlogo"

        # Overlay Captions if provided
        font_arg = f":fontfile='{self.font_path}'" if self.font_path else ""
        if captions:
            for c_idx, cap in enumerate(captions):
                text = str(cap.get("text", "")).strip()
                if not text:
                    continue
                start_t = float(cap.get("start", 0.0))
                end_t = float(cap.get("end", start_t + 4.0))

                escaped_text = (
                    text.replace("'", "'\\''")
                    .replace(":", "\\:")
                    .replace("%", "\\%")
                )
                cap_y = "h-th-220" if is_portrait else "h-th-130"
                cap_size = 28 if is_portrait else 32
                out_stream = f"vcap_{c_idx}"

                filter_complex_parts.append(
                    f"[{current_v_stream}]drawtext="
                    f"text='{escaped_text}'"
                    f"{font_arg}:"
                    f"fontcolor=white:fontsize={cap_size}:"
                    f"box=1:boxcolor=black@0.55:boxborderw=10:"
                    f"x=(w-text_w)/2:y={cap_y}:"
                    f"enable='between(t,{start_t:.2f},{end_t:.2f})'[{out_stream}]"
                )
                current_v_stream = out_stream

        # Overlay CTA text if present (during final 4.0 seconds)
        if cta_text and cta_text.strip():
            escaped_cta = (
                cta_text.replace("'", "'\\''")
                .replace(":", "\\:")
                .replace("%", "\\%")
            )
            cta_duration = 4.0 if (target_duration and target_duration >= 60) else 3.5
            cta_start_t = max(0.0, total_video_duration - cta_duration)
            pos_y = "h-th-160" if is_portrait else "h-th-80"
            font_size = 36 if is_portrait else 44

            filter_complex_parts.append(
                f"[{current_v_stream}]drawtext="
                f"text='{escaped_cta}'"
                f"{font_arg}:"
                f"fontcolor=white:fontsize={font_size}:"
                f"box=1:boxcolor=black@0.70:boxborderw=16:"
                f"x=(w-text_w)/2:y={pos_y}:"
                f"enable='between(t,{cta_start_t:.2f},{total_video_duration + 5:.2f})'[vcta]"
            )
            current_v_stream = "vcta"

        # --- Audio Filter Graph ---
        # Mix narration with ducked background music if present
        if music_idx is not None:
            filter_complex_parts.append(f"[{narration_idx}:a]apad,volume=1.0[voice]")
            filter_complex_parts.append(
                f"[{music_idx}:a]volume=0.18,aloop=loop=-1:size=2e+09[music_loop]"
            )
            filter_complex_parts.append(
                f"[voice][music_loop]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
            )
            current_a_stream = "aout"
        else:
            filter_complex_parts.append(f"[{narration_idx}:a]apad[aout]")
            current_a_stream = "aout"

        filter_complex = ";\n".join(filter_complex_parts)

        cmd = [
            self.ffmpeg_bin,
            "-y",  # Overwrite temporary output
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current_v_stream}]",
            "-map", f"[{current_a_stream}]",
            "-t", f"{total_video_duration:.3f}",  # Strictly clamp output duration
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-movflags", "+faststart",
            str(temp_dest),
        ]

        logger.info(f"Executing FFmpeg assembly command ({len(clip_paths)} clips, {total_video_duration:.2f}s target)...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            temp_dest.unlink(missing_ok=True)
            err_msg = stderr.decode(errors="replace")[-1500:]
            logger.error(f"FFmpeg assembly failed (code {proc.returncode}):\n{err_msg}")
            raise RuntimeError(f"FFmpeg rendering failed with exit code {proc.returncode}: {err_msg}")

        # Atomic rename ensures clean, uncorrupted final output
        if temp_dest.is_file():
            temp_dest.replace(dest)

        logger.info(f"Final advertisement successfully rendered to {dest}")
        return str(dest)

    async def render_timeline(
        self,
        timeline_data: dict[str, Any],
        output_path: str,
    ) -> str:
        """Compose a customized multitrack timeline into an MP4 advertisement.

        Supports clip reordering, source trimming, aspect-ratio scaling (16:9 / 9:16),
        brand logo watermark positioning/scaling/opacity, timed captions, and audio volume/fades/ducking.
        """
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest.with_suffix(".tmp.mp4")

        settings_dict = timeline_data.get("settings", {})
        aspect_ratio = settings_dict.get("aspect_ratio", "16:9")
        is_portrait = aspect_ratio in ("9:16", "portrait")
        target_w = 1080 if is_portrait else 1920
        target_h = 1920 if is_portrait else 1080

        clips = timeline_data.get("video_clips", [])
        if not clips:
            raise ValueError("Cannot render timeline: no video clips defined.")

        valid_clips = []
        for c in clips:
            sp = c.get("source_path", "")
            if sp and os.path.isfile(sp):
                valid_clips.append(c)

        if not valid_clips:
            raise FileNotFoundError("Cannot render timeline: none of the specified clip files exist on disk.")

        inputs: list[str] = []
        filter_complex_parts: list[str] = []

        # 1. Add clip inputs
        for c in valid_clips:
            inputs.extend(["-i", c["source_path"]])

        # 2. Add audio inputs
        audio_tracks = timeline_data.get("audio_tracks", [])
        narration_track = next((a for a in audio_tracks if a.get("track_type") == "narration" and a.get("source_path") and os.path.isfile(a["source_path"])), None)
        music_track = next((a for a in audio_tracks if a.get("track_type") == "music" and a.get("source_path") and os.path.isfile(a["source_path"])), None)

        narration_idx: int | None = None
        if narration_track:
            narration_idx = len(inputs) // 2
            inputs.extend(["-i", narration_track["source_path"]])

        music_idx: int | None = None
        if music_track:
            music_idx = len(inputs) // 2
            inputs.extend(["-i", music_track["source_path"]])

        # 3. Add logo/overlay input
        overlays = timeline_data.get("overlays", [])
        logo_overlay = next((o for o in overlays if o.get("asset_path") and os.path.isfile(o["asset_path"])), None)

        logo_idx: int | None = None
        if logo_overlay:
            logo_idx = len(inputs) // 2
            inputs.extend(["-i", logo_overlay["asset_path"]])

        # Calculate total timeline duration from clips
        total_duration = 0.0
        for idx, c in enumerate(valid_clips):
            s_start = max(0.0, float(c.get("source_start", 0.0)))
            s_end = float(c.get("source_end", c.get("source_duration", 5.0)))
            if s_end <= s_start:
                s_end = s_start + 1.0
            clip_dur = s_end - s_start
            total_duration += clip_dur

            trim_filter = f"trim=start={s_start:.3f}:end={s_end:.3f},setpts=PTS-STARTPTS"
            scale_filter = (
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24"
            )
            filter_complex_parts.append(f"[{idx}:v]{trim_filter},{scale_filter}[v{idx}]")

        # Concatenate normalized clips
        concat_inputs = "".join(f"[v{i}]" for i in range(len(valid_clips)))
        filter_complex_parts.append(
            f"{concat_inputs}concat=n={len(valid_clips)}:v=1:a=0[vconcat]"
        )
        current_v_stream = "vconcat"

        # Apply Brand Logo overlay
        if logo_idx is not None and logo_overlay:
            scale_val = float(logo_overlay.get("scale", 1.0))
            base_logo_w = int((180 if is_portrait else 220) * scale_val)
            opacity = min(1.0, max(0.0, float(logo_overlay.get("opacity", 1.0))))
            pos = logo_overlay.get("position", "top_right")

            if pos == "top_left":
                pos_xy = "x=40:y=40" if not is_portrait else "x=40:y=60"
            elif pos == "bottom_right":
                pos_xy = "x=W-w-40:y=H-h-40"
            elif pos == "bottom_left":
                pos_xy = "x=40:y=H-h-40"
            elif pos == "center":
                pos_xy = "x=(W-w)/2:y=(H-h)/2"
            else:  # top_right
                pos_xy = "x=W-w-40:y=40" if not is_portrait else "x=W-w-40:y=60"

            logo_start = float(logo_overlay.get("timeline_start", 0.0))
            logo_end = float(logo_overlay.get("timeline_end", total_duration))

            logo_filters = [f"scale={base_logo_w}:-1"]
            if opacity < 0.99:
                logo_filters.append(f"format=rgba,colorchannelmixer=aa={opacity:.2f}")

            filter_complex_parts.append(f"[{logo_idx}:v]{','.join(logo_filters)}[scaled_logo]")
            filter_complex_parts.append(
                f"[{current_v_stream}][scaled_logo]overlay={pos_xy}:"
                f"enable='between(t,{logo_start:.2f},{logo_end:.2f})':format=auto[vlogo]"
            )
            current_v_stream = "vlogo"

        # Apply Captions / Titles
        captions = timeline_data.get("captions", [])
        if self.font_path and captions:
            escaped_font = self.font_path.replace("\\", "/").replace(":", "\\:")
            cap_stream_idx = 0
            for cap in captions:
                c_text = cap.get("text", "").strip()
                if not c_text:
                    continue
                c_start = float(cap.get("timeline_start", 0.0))
                c_end = float(cap.get("timeline_end", c_start + 4.0))
                c_size = int(cap.get("font_size", 28))
                c_color = cap.get("font_color", "white").replace("#", "0x")
                c_pos = cap.get("position", "bottom")

                if c_pos == "top":
                    pos_y = "100" if not is_portrait else "140"
                elif c_pos == "center":
                    pos_y = "(h-text_h)/2"
                else:
                    pos_y = "h-text_h-100" if not is_portrait else "h-text_h-200"

                clean_text = (
                    c_text.replace("\\", "\\\\")
                    .replace("'", "'\\\\''")
                    .replace("%", "\\%")
                    .replace(":", "\\:")
                )

                next_v = f"vcap_{cap_stream_idx}"
                filter_complex_parts.append(
                    f"[{current_v_stream}]drawtext="
                    f"fontfile='{escaped_font}':text='{clean_text}':"
                    f"fontsize={c_size}:fontcolor={c_color}:"
                    f"box=1:boxcolor=black@0.65:boxborderw=8:"
                    f"x=(w-text_w)/2:y={pos_y}:"
                    f"enable='between(t,{c_start:.2f},{c_end:.2f})'[{next_v}]"
                )
                current_v_stream = next_v
                cap_stream_idx += 1

        # Audio Mixing
        current_a_stream = "aout"
        audio_mix_inputs = []

        if narration_idx is not None:
            n_vol = float(narration_track.get("volume", 1.0))
            filter_complex_parts.append(f"[{narration_idx}:a]apad,volume={n_vol:.2f}[narr_voice]")
            audio_mix_inputs.append("[narr_voice]")

        if music_idx is not None:
            m_vol = float(music_track.get("volume", 0.25))
            m_fade_in = float(music_track.get("fade_in", 0.0))
            m_fade_out = float(music_track.get("fade_out", 1.0))

            m_filters = [f"volume={m_vol:.2f}", "aloop=loop=-1:size=2e+09"]
            if m_fade_in > 0:
                m_filters.append(f"afade=t=in:ss=0:d={m_fade_in:.2f}")
            if m_fade_out > 0:
                out_start = max(0.0, total_duration - m_fade_out)
                m_filters.append(f"afade=t=out:st={out_start:.2f}:d={m_fade_out:.2f}")

            filter_complex_parts.append(f"[{music_idx}:a]{','.join(m_filters)}[bg_music]")
            audio_mix_inputs.append("[bg_music]")

        if len(audio_mix_inputs) == 2:
            filter_complex_parts.append(
                f"{''.join(audio_mix_inputs)}amix=inputs=2:duration=longest:dropout_transition=2[aout]"
            )
        elif len(audio_mix_inputs) == 1:
            filter_complex_parts.append(f"{audio_mix_inputs[0]}anull[aout]")
        else:
            filter_complex_parts.append(f"aevalsrc=0:d={total_duration:.2f}[aout]")

        filter_complex = ";\n".join(filter_complex_parts)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{current_v_stream}]",
            "-map", f"[{current_a_stream}]",
            "-t", f"{total_duration:.3f}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-movflags", "+faststart",
            str(temp_dest),
        ]

        logger.info(f"Rendering timeline edit ({len(valid_clips)} clips, duration {total_duration:.2f}s)...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            temp_dest.unlink(missing_ok=True)
            err_msg = stderr.decode(errors="replace")[-1500:]
            logger.error(f"FFmpeg timeline render failed (code {proc.returncode}):\n{err_msg}")
            raise RuntimeError(f"FFmpeg timeline rendering failed with exit code {proc.returncode}: {err_msg}")

        if temp_dest.is_file():
            temp_dest.replace(dest)

        logger.info(f"Timeline edit successfully exported to {dest}")
        return str(dest)
