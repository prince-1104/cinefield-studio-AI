"""Gemini implementation of the CreativePlanner interface using structured outputs."""

import mimetypes
from pathlib import Path

from google import genai
from google.genai import types

from app.config import settings
from app.interfaces.creative_planner import CreativePlanner
from app.schemas.storyboard import Storyboard, StoryboardShot


class GeminiPlanner(CreativePlanner):
    """Generates structured advertising scripts and 3 storyboard shots using Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
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
    ) -> Storyboard:
        """Generate a structured script and 3 storyboard shots matching the Storyboard schema."""
        prompt = (
            f"You are an award-winning creative director for cinematic video advertisements.\n\n"
            f"Create a high-impact, 3-shot advertisement campaign for the following product:\n"
            f"- Product Name: {product_name}\n"
            f"- Product Brief: {brief}\n"
            f"- Target Audience: {audience}\n"
            f"- Desired Tone: {tone}\n"
            f"- Call To Action (CTA): {cta}\n\n"
            f"Requirements:\n"
            f"1. Produce EXACTLY THREE sequential storyboard shots:\n"
            f"   - Shot 1 (The Hook): Grab attention, present the problem or intrigue.\n"
            f"   - Shot 2 (The Reveal): Showcase the product in dynamic, cinematic action.\n"
            f"   - Shot 3 (The Climax & CTA): Deliver emotional payoff and clear call to action.\n"
            f"2. For each shot, provide a highly descriptive visual prompt suitable for video generation "
            f"(camera angles, lens choice, lighting, subject motion, physics, and mood).\n"
            f"3. For each shot, provide a natural narration voiceover line.\n"
            f"4. Provide a coherent full narration text connecting all three shots seamlessly.\n"
        )

        contents: list[str | types.Part] = []

        # If a product image was uploaded, attach it as multimodal reference
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
                f"\nA reference product image is attached. Describe the product visually "
                f"consistent with the attached reference image in all visual prompts."
            )

        contents.append(prompt)

        # Enforce structured output matching the Storyboard schema
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Storyboard,
            temperature=0.7,
        )

        # Call Gemini text model via official SDK
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        storyboard = Storyboard.model_validate_json(response.text)

        # Sanity check: Ensure exactly 3 shots
        if len(storyboard.shots) != 3:
            raise ValueError(
                f"Gemini returned {len(storyboard.shots)} shots, but exactly 3 shots are required."
            )

        # Ensure shot numbers are 1, 2, 3
        for i, shot in enumerate(storyboard.shots, start=1):
            shot.shot_number = i

        return storyboard

