"""Anthropic Claude implementation of the CreativePlanner interface using structured tool outputs."""

import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.interfaces.creative_planner import CreativePlanner
from app.schemas.storyboard import Storyboard, StoryboardShot
from worker.gemini_planner import PEXYL_8_SCENE_TEMPLATE

logger = logging.getLogger(__name__)


class ClaudePlanner(CreativePlanner):
    """Generates structured advertising scripts and configurable storyboard shots using Anthropic Claude."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        raw_key = api_key if api_key is not None else settings.CLAUDE_API_KEY
        self.api_key = raw_key.strip().rstrip(",") if raw_key else ""
        self.model = model or settings.CLAUDE_MODEL

    async def plan_storyboard(
        self,
        product_name: str,
        brief: str,
        audience: str,
        tone: str,
        cta: str,
        product_image_path: str | None = None,
        target_duration: int = 15,
        shot_count: int = 3,
        aspect_ratio: str = "16:9",
    ) -> Storyboard:
        """Generate a structured script and sequence of shots matching the Storyboard schema using Claude."""
        if not self.api_key:
            raise RuntimeError(
                "CLAUDE_API_KEY is not configured. "
                "Please configure a valid Anthropic Claude API key in your .env file to generate scripts."
            )

        is_pexyl = "pexyl" in product_name.lower() or "pexyl" in brief.lower()
        pexyl_guidance = PEXYL_8_SCENE_TEMPLATE if (is_pexyl and shot_count == 8 and target_duration == 60) else ""

        system_prompt = (
            "You are an award-winning executive creative director, cinematographer, and visual continuity "
            "architect specialized in luxury commercials, micro-dramas, and cinematic brand launch films. "
            "Your mission is to structure a compelling, rhythmically paced, and visually continuous advertisement "
            "that strictly matches the target duration, shot count, and aspect ratio."
        )

        user_prompt = (
            f"Campaign Brief:\n"
            f"- Product / Feature: {product_name}\n"
            f"- Campaign Brief: {brief}\n"
            f"- Target Audience: {audience}\n"
            f"- Aesthetic Direction & Tone: {tone}\n"
            f"- Call To Action (CTA): {cta}\n"
            f"- Target Total Duration: {target_duration} seconds\n"
            f"- Exact Planned Shot Count: {shot_count} shots\n"
            f"- Aspect Ratio: {aspect_ratio}\n\n"
            f"{pexyl_guidance}\n"
            f"Production Requirements:\n"
            f"1. Generate EXACTLY {shot_count} sequential storyboard shots.\n"
            f"2. The shots must cover the full timeline from 0.0 seconds to {target_duration}.0 seconds continuously.\n"
            f"   Ensure each shot's start_time and end_time align with its predecessor with zero gaps or overlaps.\n"
            f"3. For each shot provide:\n"
            f"   - shot_number (1 to {shot_count})\n"
            f"   - start_time and end_time (in seconds)\n"
            f"   - target_duration (in seconds, sum of all shots must equal {target_duration})\n"
            f"   - description: Vivid narrative summary of what occurs in the scene\n"
            f"   - visual_prompt: Photorealistic, cinematic video prompt specifying camera angle, composition, "
            f"lighting, subject motion, physics, and mood for video generation models (Seedance / Gemini)\n"
            f"   - camera_motion: Specific movement (e.g. 'Slow Dolly In', 'Dynamic Tracking Orbit', 'Hero Anamorphic Tilt')\n"
            f"   - transition: Transition intent to next scene (e.g. 'Cut', 'Whip Pan', 'Match Dissolve')\n"
            f"   - narration_text: Natural voiceover line for this shot's time window\n"
            f"   - on_screen_text: Any key text, title, or tagline appearing on screen\n"
            f"   - continuity_notes: Lighting and subject continuity linking to adjacent shots\n"
            f"4. Provide a cohesive full_narration connecting the entire storyline.\n"
            f"5. If {target_duration}s == 60s, reserve the final 4-5 seconds for the closing brand reveal and CTA.\n"
        )

        # Build message contents with optional multimodal image block
        content_blocks: list[dict[str, Any]] = []

        if product_image_path and Path(product_image_path).is_file():
            image_path = Path(product_image_path)
            mime_type, _ = mimetypes.guess_type(str(image_path))
            mime_type = mime_type or "image/png"
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": image_b64,
                },
            })
            user_prompt += (
                f"\nA reference product image is attached. Maintain strict visual identity "
                f"and design fidelity consistent with this reference across all visual prompts."
            )

        content_blocks.append({
            "type": "text",
            "text": user_prompt,
        })

        # Define structured tool schema matching Storyboard Pydantic model
        schema = Storyboard.model_json_schema()
        # Remove title if top-level schema has it
        tools = [
            {
                "name": "create_cinematic_storyboard",
                "description": "Construct and return the structured script and storyboard sequence.",
                "input_schema": schema,
            }
        ]

        logger.info(
            f"Requesting Claude planning: model={self.model}, duration={target_duration}s, shots={shot_count}"
        )

        # Attempt call via official anthropic SDK, with httpx fallback
        data_dict: dict[str, Any] | None = None
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": content_blocks}],
                tools=tools,
                tool_choice={"type": "tool", "name": "create_cinematic_storyboard"},
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "create_cinematic_storyboard":
                    data_dict = block.input
                    break

        except ImportError:
            logger.warning("anthropic SDK not found, falling back to direct httpx REST call")
            data_dict = await self._call_via_httpx(system_prompt, content_blocks, tools)
        except Exception as e:
            logger.error(f"Error in Claude SDK call: {e}, falling back to direct httpx REST call")
            data_dict = await self._call_via_httpx(system_prompt, content_blocks, tools)

        if not data_dict:
            raise RuntimeError("Claude did not return a valid structured storyboard output.")

        storyboard = Storyboard.model_validate(data_dict)
        return self._normalize_storyboard(storyboard, target_duration, shot_count)

    async def _call_via_httpx(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Direct Anthropic REST API fallback."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": content_blocks}],
            "tools": tools,
            "tool_choice": {"type": "tool", "name": "create_cinematic_storyboard"},
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "create_cinematic_storyboard":
                    return block.get("input", {})
        raise RuntimeError("Direct Claude REST call did not return structured tool output.")

    def _normalize_storyboard(
        self,
        storyboard: Storyboard,
        target_duration: int,
        shot_count: int,
    ) -> Storyboard:
        """Ensure shot count and timeline boundaries match the planned specifications exactly."""
        shots = storyboard.shots

        if len(shots) > shot_count:
            shots = shots[:shot_count]
        elif len(shots) < shot_count:
            last = shots[-1] if shots else StoryboardShot(
                shot_number=1,
                start_time=0.0,
                end_time=float(target_duration),
                target_duration=float(target_duration),
                description="Cinematic shot",
                visual_prompt="Cinematic shot of product",
                narration_text="Experience next-generation quality.",
            )
            while len(shots) < shot_count:
                num = len(shots) + 1
                shots.append(
                    StoryboardShot(
                        shot_number=num,
                        description=f"Scene {num}: Continuation of cinematic narrative",
                        visual_prompt=last.visual_prompt,
                        narration_text=last.narration_text,
                        camera_motion="Smooth tracking shot",
                        transition="Cut",
                    )
                )

        total_d = float(target_duration)
        avg_duration = total_d / shot_count
        current_time = 0.0

        for i, shot in enumerate(shots):
            shot.shot_number = i + 1
            dur = shot.target_duration if (shot.target_duration and shot.target_duration > 0) else avg_duration
            shot.start_time = round(current_time, 2)
            if i == len(shots) - 1:
                shot.end_time = round(total_d, 2)
                shot.target_duration = round(total_d - current_time, 2)
            else:
                shot.end_time = round(current_time + dur, 2)
                shot.target_duration = round(dur, 2)
                current_time = shot.end_time

        storyboard.shots = shots
        storyboard.target_duration = target_duration
        storyboard.total_planned_duration = total_d
        return storyboard

