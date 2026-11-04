"""Built-in Cinematic Template Planner for Pexyl Studio.

Provides deterministic, highly cinematic storyboard planning when external AI APIs
(Claude / Gemini) are unavailable, rate-limited, or out of credit balance.
"""

import math
from typing import Any

from app.interfaces.creative_planner import CreativePlanner
from app.schemas.storyboard import Storyboard, StoryboardShot


class TemplateCreativePlanner(CreativePlanner):
    """High-fidelity fallback creative director and storyboard planner."""

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
        """Synthesize a complete cinematic storyboard matching duration and shot count specifications."""
        count = max(1, shot_count)
        base_dur = round(target_duration / count, 1)

        # Diverse cinematic camera movements
        camera_motions = [
            "Slow cinematic dolly forward with shallow depth of field",
            "Dynamic sweeping aerial drone orbit, smooth motion blur",
            "High-speed macro tracking shot with anamorphic lens flare",
            "Hero pedestal upward pan revealing architectural scale",
            "Low-angle gliding tracking shot, 35mm film aesthetic",
            "Slow motion 120fps rotational orbit around focal subject",
            "Smooth lateral slider pan across sleek reflective surfaces",
            "Cinematic snap-zoom with rack focus to hero subject",
            "Atmospheric crane descent into golden-hour backlight",
            "Kinetic whip pan transition with motion blur",
            "Locked-off architectural master shot, symmetrical framing",
            "Intimate handheld tracking shot, organic micro-jitter",
        ]

        transitions = [
            "Cinematic Cut",
            "Smooth Match Dissolve",
            "Kinetic Whip Pan",
            "Light Leak Transition",
            "Crossfade (0.5s)",
            "Hard Impact Cut",
        ]

        # Narrative templates based on scene sequence
        narrative_phases = [
            ("The Awakening", "Opening provocative visual hook drawing the viewer into the world of"),
            ("The Challenge", "Visually illustrating the everyday limitation or friction experienced by"),
            ("The Catalyst", "An elegant cinematic glimpse of the breakthrough innovation behind"),
            ("The Revelation", "Dramatic hero showcase highlighting the premium craftsmanship of"),
            ("The Experience", "Dynamic operational montage demonstrating seamless power and agility in"),
            ("The Transformation", "Elevated lifestyle and cinematic satisfaction realized by"),
            ("The Climax", "Epic full-scale visual crescendo bringing together all capabilities of"),
            ("The Call to Action", "Sleek closing hero frame with subtle atmospheric lighting and closing reveal for"),
        ]

        shots: list[StoryboardShot] = []
        accumulated_time = 0.0

        for i in range(count):
            shot_num = i + 1
            is_last = (shot_num == count)

            # Compute timing
            if is_last:
                this_dur = round(float(target_duration) - accumulated_time, 1)
                if this_dur <= 0:
                    this_dur = base_dur
            else:
                this_dur = base_dur

            start_t = round(accumulated_time, 1)
            end_t = round(start_t + this_dur, 1)
            accumulated_time = end_t

            # Select narrative phase
            phase_idx = min(i, len(narrative_phases) - 1)
            phase_title, phase_desc = narrative_phases[phase_idx]

            cam_motion = camera_motions[i % len(camera_motions)]
            trans = "Fade to Black" if is_last else transitions[i % len(transitions)]

            # Generate descriptive narrative & prompts
            if shot_num == 1:
                description = f"Opening cinematic hook: {brief[:120]} introducing {product_name}."
                visual_prompt = (
                    f"Cinematic {aspect_ratio} opening shot for {product_name}. {brief[:140]}. "
                    f"Atmospheric volumetric lighting, premium {tone} tone, photorealistic textures, "
                    f"Arri Alexa 65 cinema footage, 8k resolution, dramatic color grading."
                )
                narration = f"In a world where ordinary is no longer enough, meet {product_name}."
            elif is_last:
                description = f"Closing reveal & hero call to action for {product_name}: {cta}."
                visual_prompt = (
                    f"Sleek hero closing shot of {product_name} in {aspect_ratio}. High-end commercial aesthetic, "
                    f"minimalist dark studio reflections, golden rim lighting, luxury typography environment. "
                    f"Aesthetic tone: {tone}. Pristine 8k advertising render."
                )
                narration = f"{cta}. {product_name}."
            else:
                description = f"{phase_title}: {phase_desc} {product_name} designed for {audience[:80]}."
                visual_prompt = (
                    f"Dynamic {aspect_ratio} commercial scene showcasing {product_name} in action. "
                    f"{tone} aesthetic, beautiful natural lens flare, sharp focal plane, crisp motion dynamics, "
                    f"tailored for {audience[:60]}. Photorealistic cinema quality."
                )
                narration = f"Engineered for {audience}, {product_name} delivers uncompromising precision."

            shots.append(
                StoryboardShot(
                    shot_number=shot_num,
                    start_time=start_t,
                    end_time=end_t,
                    target_duration=this_dur,
                    description=description,
                    visual_prompt=visual_prompt,
                    camera_motion=cam_motion,
                    transition=trans,
                    narration_text=narration,
                    on_screen_text=product_name if (shot_num == 1 or is_last) else None,
                    continuity_notes=f"Match {tone} color palette and lighting temperature with Shot #{max(1, shot_num - 1)}.",
                )
            )

        script_summary = (
            f"A cohesive {target_duration}-second commercial for {product_name}. "
            f"Tailored for {audience} with a {tone} creative direction. "
            f"The arc begins with a compelling hook ({brief[:100]}), evolves through dynamic capability showcases, "
            f"and concludes with an impactful call to action: {cta}."
        )

        full_narration = " ".join(s.narration_text for s in shots)

        return Storyboard(
            title=f"{product_name} — {tone.capitalize()} Campaign",
            script_summary=script_summary,
            full_narration=full_narration,
            target_duration=target_duration,
            total_planned_duration=round(sum(s.target_duration for s in shots), 1),
            shot_count=count,
            shots=shots,
        )
