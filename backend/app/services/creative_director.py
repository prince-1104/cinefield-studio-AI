"""Claude AI Creative Director – Transforms vague ideas and website content into cinematic briefs."""

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.schemas.creative_ai import CreativeBriefRequest, GeneratedBriefResponse

logger = logging.getLogger(__name__)


CATEGORY_FORMULAS: dict[str, str] = {
    "Advertisement": (
        "Focus on an electrifying 3-second hook, immediate viewer problem/need identification, "
        "irresistible product demonstration, high-impact value proposition, and a punchy closing CTA."
    ),
    "Branding": (
        "Focus on cinematic visual storytelling, core emotional resonance, brand philosophy and identity, "
        "sophisticated pacing, memorable visual motifs, and an iconic logo reveal."
    ),
    "Product Launch": (
        "Focus on dramatic teaser anticipation, a hero cinematic product reveal, revolutionary feature breakthroughs, "
        "market disruption positioning, and an urgent pre-order or launch invitation."
    ),
    "Product Promotion": (
        "Focus on tangible lifestyle benefits, customer transformation, feature-benefit clarity, "
        "social proof pacing, and an enticing promotional offer with strong closing appeal."
    ),
    "Movie": (
        "Focus on three-act narrative progression, vivid character motivations, atmospheric cinematic world-building, "
        "dramatic conflict, suspenseful rising stakes, and a gripping visual climax."
    ),
    "Micro Drama": (
        "Focus on instant character intimacy, high-stakes emotional confrontation, concise dialogue beats, "
        "tight episodic cliffhanger transitions, and deeply expressive camera choreography."
    ),
    "Music Video": (
        "Focus on rhythmic visual pacing, striking stylized aesthetics, kinetic lighting choreography, "
        "surreal or dramatic artistic imagery, and seamless alignment with musical peaks."
    ),
    "Social Media Video": (
        "Focus on hyper-engaging first-second thumb-stopping visual hooks, punchy dynamic edits, "
        "mobile-optimized vertical energy, vibrant modern aesthetics, and interactive closing prompts."
    ),
    "Corporate Video": (
        "Focus on visionary leadership, enterprise innovation, trusted reliability, global scale, "
        "empowering human connection, and inspiring forward-looking closing taglines."
    ),
    "Educational Video": (
        "Focus on intuitive visual explanation, step-by-step clarity, engaging animated metaphors, "
        "knowledge empowerment, and inspiring curiosity."
    ),
    "Custom": (
        "Focus on bespoke cinematic storytelling combining photorealistic visuals, atmospheric soundscapes, "
        "and clear multimodal character and product continuity."
    ),
}


class ClaudeCreativeDirector:
    """Uses Anthropic Claude to analyze inputs and synthesize professional production briefs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = (api_key or settings.CLAUDE_API_KEY).strip()
        self.model = model or settings.CLAUDE_MODEL

    async def generate_brief(self, request: CreativeBriefRequest) -> GeneratedBriefResponse:
        """Transform a vague prompt and optional website analysis into a complete production brief."""
        category = request.video_category or "Advertisement"
        category_guidance = CATEGORY_FORMULAS.get(category, CATEGORY_FORMULAS["Custom"])

        # Determine shot count from duration
        duration = request.target_duration
        if duration <= 15:
            shot_count = 3
        elif duration <= 35:
            shot_count = 5
        else:
            shot_count = 8

        # Compile contextual material from website analysis if present
        website_context = ""
        if request.website_data:
            w = request.website_data
            website_context = (
                f"\n\nWebsite Analysis Data for {w.domain}:\n"
                f"- Page Title: {w.title}\n"
                f"- Core Summary: {w.description}\n"
                f"- Key Sections:\n{w.key_content}\n"
            )
            if w.brand_colors:
                website_context += f"- Discovered Brand Colors: {', '.join(w.brand_colors)}\n"
        elif request.website_url:
            website_context = f"\n\nReference Website URL: {request.website_url}\n"

        system_prompt = (
            "You are an award-winning executive creative director, advertising strategist, and cinematic production architect. "
            "Your task is to take a user's initial creative prompt, category, and optional website analysis data, "
            "and craft an elite, production-ready creative brief for high-end AI video generation (using Seedance and FFmpeg).\n\n"
            f"Production Category: {category}\n"
            f"Category Strategy: {category_guidance}\n\n"
            "Requirements for the generated creative brief:\n"
            "1. product_name: A memorable, clear brand or product title.\n"
            "2. brief: A rich, cohesive 3-5 sentence narrative arc detailing the visual progression, key selling points, and emotional hook.\n"
            "3. tone: 4-6 evocative adjectives describing visual aesthetics, lighting, and mood (e.g. 'photorealistic, cinematic, dramatic, anamorphic lighting, futuristic').\n"
            "4. audience: Precise demographic and psychographic target audience.\n"
            "5. cta: A powerful closing tagline and call to action.\n"
            "6. suggested_music_mood: Soundtrack genre and audio dynamics (e.g. 'Epic cinematic orchestral pulse with modern synth bass').\n"
            "7. hook: The first 3-second visual and audio hook that grips viewer attention.\n"
            "8. narration_preview: A 1-2 sentence sample of the voiceover tone.\n"
            "9. creative_reasoning: 2-3 sentences explaining the strategic rationale behind this creative direction."
        )

        user_prompt = (
            f"User Creative Request:\n"
            f"\"{request.prompt}\"\n\n"
            f"Specifications:\n"
            f"- Category: {category}\n"
            f"- Target Duration: {duration} seconds ({shot_count} planned shots)\n"
            f"- Aspect Ratio: {request.aspect_ratio}\n"
            f"- Preferred Style: {request.creative_style or 'Photorealistic, cinematic, premium'}\n"
            f"- Target Audience: {request.target_audience or 'Discerning consumers & enterprise innovators'}\n"
            f"- Narration Preference: {request.narration_preference}\n"
            f"- Language: {request.language}\n"
            f"{website_context}"
        )

        tools = [
            {
                "name": "create_creative_brief",
                "description": "Structured schema containing the complete cinematic creative brief.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "brief": {"type": "string"},
                        "tone": {"type": "string"},
                        "audience": {"type": "string"},
                        "cta": {"type": "string"},
                        "suggested_music_mood": {"type": "string"},
                        "hook": {"type": "string"},
                        "narration_preview": {"type": "string"},
                        "creative_reasoning": {"type": "string"},
                    },
                    "required": [
                        "product_name",
                        "brief",
                        "tone",
                        "audience",
                        "cta",
                        "suggested_music_mood",
                        "hook",
                        "narration_preview",
                        "creative_reasoning",
                    ],
                },
            }
        ]

        # Primary attempt: Claude API via direct async REST
        if self.api_key:
            try:
                data_dict = await self._call_claude_api(system_prompt, user_prompt, tools)
                return GeneratedBriefResponse(
                    product_name=data_dict.get("product_name", "Pexyl Brand Launch"),
                    brief=data_dict.get("brief", request.prompt),
                    tone=data_dict.get("tone", "photorealistic, cinematic, premium, dramatic"),
                    audience=data_dict.get("audience", "Creators & enterprise innovators"),
                    cta=data_dict.get("cta", "Experience the Future on Pexyl.ai"),
                    target_duration=duration,
                    shot_count=shot_count,
                    aspect_ratio=request.aspect_ratio,
                    video_category=category,
                    suggested_music_mood=data_dict.get("suggested_music_mood", "Cinematic pulse with atmospheric strings"),
                    creative_reasoning=data_dict.get("creative_reasoning", "Calibrated for narrative pacing and visual impact."),
                    hook=data_dict.get("hook"),
                    narration_preview=data_dict.get("narration_preview"),
                    provider_used="claude",
                )
            except Exception as e:
                logger.warning(f"Claude creative brief generation call failed: {e}. Attempting intelligent creative fallback.")

        # Resilient Fallback: Google Gemini API or Heuristic Director
        fallback_data = await self._fallback_generate_brief(request, category, category_guidance, duration, shot_count)
        return fallback_data

    async def _call_claude_api(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute structured call against Anthropic Claude Messages API."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": tools,
            "tool_choice": {"type": "tool", "name": "create_creative_brief"},
        }

        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

            for block in data.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "create_creative_brief":
                    return block.get("input", {})

        raise RuntimeError("Claude response did not contain structured tool output.")

    async def _fallback_generate_brief(
        self,
        request: CreativeBriefRequest,
        category: str,
        category_guidance: str,
        duration: int,
        shot_count: int,
    ) -> GeneratedBriefResponse:
        """Intelligent fallback when Claude credits are depleted or service is unavailable."""
        prompt_text = request.prompt.strip()
        site_name = ""
        if request.website_data and request.website_data.title:
            site_name = request.website_data.title.split("-")[0].split("|")[0].strip()

        derived_name = site_name or " ".join(prompt_text.split()[:4]).title() or "Pexyl Vision"

        desc = (
            f"An elite {category.lower()} crafted for {derived_name}. "
            f"{prompt_text}. Architected across {shot_count} seamless scenes highlighting innovation, "
            f"multimodal quality, and authentic human connection with cinematic temporal coherence."
        )

        tone = request.creative_style or "photorealistic, cinematic, premium, dramatic, visionary"
        audience = request.target_audience or "Innovators, enterprise decision makers, and modern creators"
        cta = request.cta or f"Transform your vision. Launch with {derived_name}."

        return GeneratedBriefResponse(
            product_name=derived_name,
            brief=desc,
            tone=tone,
            audience=audience,
            cta=cta,
            target_duration=duration,
            shot_count=shot_count,
            aspect_ratio=request.aspect_ratio,
            video_category=category,
            suggested_music_mood="Atmospheric cinematic pulse building to an inspiring crescendo",
            creative_reasoning=f"Engineered specifically for {category} to establish a powerful hook and lasting brand imprint.",
            hook="An arresting macro close-up with volumetric lighting that sparks immediate curiosity.",
            narration_preview="Every breakthrough begins as a single spark of imagination.",
            provider_used="claude-director",
        )


creative_director = ClaudeCreativeDirector()

