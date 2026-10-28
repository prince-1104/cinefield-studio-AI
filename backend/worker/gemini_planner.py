"""Gemini implementation of the CreativePlanner interface using structured outputs."""

import logging
import mimetypes
from pathlib import Path

from google import genai
from google.genai import types

from app.config import settings
from app.interfaces.creative_planner import CreativePlanner
from app.schemas.storyboard import Storyboard, StoryboardShot

logger = logging.getLogger(__name__)

PEXYL_8_SCENE_TEMPLATE = """
For Pexyl brand productions, follow this calibrated 8-scene cinematic structure:
1. The Vision (0–7s): Introduce the raw power of human creative vision. A creator in contemplation, luminous ideas sparking into reality.
2. Micro-Dramas (7–16s): High emotional tension, cinematic cliffhanger, dramatic portrait lighting, visceral character interaction.
3. Cinema (16–25s): Epic cinematic scale, expansive worlds, anamorphic lens flares, sweeping vista, production value.
4. Music (25–33s): Artist performance, dynamic rhythm, expressive lighting, kinetic audio-visual energy.
5. Advertising (33–42s): Premium commercial product showcase, macro details, luxury aesthetics, high-speed camera elegance.
6. Production Intelligence (42–51s): Collaborative AI engine in motion — real-time storyboards, multimodal continuity, generative precision.
7. Enterprise Production (51–56s): High-volume creative output, diverse multi-screen media delivery across global platforms.
8. Brand Reveal & Tagline (56–60s): Hero lock on the Pexyl.ai identity and final closing tagline: 'Where Every Story Becomes a Production.'
"""


class GeminiPlanner(CreativePlanner):
    """Generates structured advertising scripts and configurable storyboard shots using Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        raw_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.api_key = raw_key.strip().rstrip(",") if raw_key else ""
        self.model = model or settings.GEMINI_TEXT_MODEL
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Please configure a valid Google Gemini API key in your .env file to generate scripts."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

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
        """Generate a structured script and sequence of shots matching the Storyboard schema."""
        is_pexyl = "pexyl" in product_name.lower() or "pexyl" in brief.lower()

        pexyl_guidance = PEXYL_8_SCENE_TEMPLATE if (is_pexyl and shot_count == 8 and target_duration == 60) else ""

        prompt = (
            f"You are an award-winning executive creative director and cinematographer creating a premium "
            f"AI-generated video advertisement.\n\n"
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
            f"lighting, subject motion, physics, and mood\n"
            f"   - camera_motion: Specific movement (e.g. 'Slow Dolly In', 'Dynamic Tracking Orbit', 'Anamorphic Tilt')\n"
            f"   - transition: Transition intent to next scene (e.g. 'Cut', 'Whip Pan', 'Match Dissolve')\n"
            f"   - narration_text: Natural voiceover line for this shot's time window\n"
            f"   - on_screen_text: Any key text, title, or tagline appearing on screen\n"
            f"4. Provide a cohesive full_narration connecting the entire storyline.\n"
            f"5. If {target_duration}s == 60s, reserve the final 4 seconds for the closing brand reveal and CTA.\n"
        )

        contents: list[str | types.Part] = []

        # Multimodal conditioning if product image is provided
        if product_image_path and Path(product_image_path).is_file():
            image_path = Path(product_image_path)
            mime_type, _ = mimetypes.guess_type(str(image_path))
            image_bytes = image_path.read_bytes()
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type or "image/png",
            )
            contents.append(image_part)
            prompt += (
                f"\nA reference product image is attached. Maintain strict visual identity "
                f"and design fidelity consistent with this reference across all visual prompts."
            )

        contents.append(prompt)

        # Enforce structured output via Pydantic response_schema
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Storyboard,
            temperature=0.7,
        )

        logger.info(
            f"Requesting Gemini planning: model={self.model}, duration={target_duration}s, shots={shot_count}"
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        if not response.text:
            raise RuntimeError("Gemini model returned empty response for storyboard generation")

        storyboard = Storyboard.model_validate_json(response.text)

        # Post-validation and timeline normalization
        storyboard = self._normalize_storyboard(storyboard, target_duration, shot_count)
        return storyboard

    def _normalize_storyboard(
        self,
        storyboard: Storyboard,
        target_duration: int,
        shot_count: int,
    ) -> Storyboard:
        """Ensure shot count and timeline boundaries match the planned specifications exactly."""
        shots = storyboard.shots

        # If LLM returned slightly different shot count, adjust to match requested shot_count
        if len(shots) > shot_count:
            shots = shots[:shot_count]
        elif len(shots) < shot_count:
            # Replicate or extrapolate remaining shots if under-generated
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

        # Recalculate continuous timeline without gaps
        total_d = float(target_duration)
        avg_duration = total_d / shot_count
        current_time = 0.0

        for i, shot in enumerate(shots):
            shot.shot_number = i + 1
            dur = shot.target_duration if (shot.target_duration and shot.target_duration > 0) else avg_duration
            shot.start_time = round(current_time, 2)
            # For the final shot, lock to total_duration
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
