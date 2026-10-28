"""Pydantic schemas for the structured storyboard output from the AI planner.

These schemas define the JSON structure that the Gemini text model must produce
when generating a script and storyboard. They are used both as the
response_schema for structured output and for validating the planner result.
"""

from pydantic import BaseModel, Field


class StoryboardShot(BaseModel):
    """A single shot in the storyboard."""

    shot_number: int = Field(..., ge=1, le=3, description="1, 2, or 3")
    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable description of what happens in this shot.",
    )
    visual_prompt: str = Field(
        ...,
        min_length=1,
        description="Detailed prompt for video generation, including camera angle, "
        "lighting, motion, and subject details.",
    )
    narration_text: str = Field(
        ...,
        min_length=1,
        description="Voiceover narration text for this shot segment.",
    )
    duration_hint: str = Field(
        default="5-8s",
        description="Approximate duration hint for the shot.",
    )


class Storyboard(BaseModel):
    """Complete script and three-shot storyboard produced by the AI planner."""

    title: str = Field(..., description="Working title for the advertisement.")
    script_summary: str = Field(
        ...,
        description="Brief narrative arc summary (2-3 sentences).",
    )
    shots: list[StoryboardShot] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly three storyboard shots.",
    )
    full_narration: str = Field(
        ...,
        description="Complete narration text for the entire ad, "
        "concatenating all shot narrations with natural transitions.",
    )
