"""Pydantic schemas for the structured storyboard output from the AI planner.

Supports configurable video duration (15s, 30s, 60s) and arbitrary shot counts (3, 5, 8-12).
"""

from pydantic import BaseModel, Field


class StoryboardShot(BaseModel):
    """A single shot in the storyboard timeline."""

    shot_number: int = Field(..., ge=1, description="Sequence number of the shot (1-based)")
    start_time: float = Field(default=0.0, description="Start time in seconds within planned advertisement")
    end_time: float = Field(default=5.0, description="End time in seconds within planned advertisement")
    target_duration: float = Field(default=5.0, description="Target duration of this shot in seconds")

    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable scene description and narrative purpose.",
    )
    visual_prompt: str = Field(
        ...,
        min_length=1,
        description="Detailed prompt for video generation (camera angle, composition, lighting, subject motion, physics, mood).",
    )
    camera_motion: str = Field(
        default="Dynamic cinematic camera motion",
        description="Camera movement and angle (e.g. 'Macro Dolly In', 'Dynamic Tracking Orbit', 'Hero Tilt').",
    )
    transition: str = Field(
        default="Cut",
        description="Transition intent to the next scene (e.g. 'Hard Cut', 'Kinetic Whip Pan', 'Dissolve').",
    )
    narration_text: str = Field(
        ...,
        min_length=1,
        description="Voiceover narration line for this shot segment.",
    )
    on_screen_text: str | None = Field(
        default=None,
        description="Optional text overlay or graphics displayed during this shot.",
    )
    continuity_notes: str | None = Field(
        default=None,
        description="Visual and lighting continuity constraints linking to neighboring scenes.",
    )


class Storyboard(BaseModel):
    """Complete script and multi-shot storyboard produced by the AI planner."""

    title: str = Field(..., description="Working title for the advertisement.")
    script_summary: str = Field(
        ...,
        description="Brief narrative arc summary connecting the scenes.",
    )
    target_duration: int = Field(
        default=15,
        description="Target duration of the entire advertisement in seconds (e.g. 15, 30, 60).",
    )
    total_planned_duration: float = Field(
        default=15.0,
        description="Sum of all planned shot durations in seconds.",
    )
    shots: list[StoryboardShot] = Field(
        ...,
        min_length=1,
        description="Ordered sequence of storyboard shots covering the planned timeline.",
    )
    full_narration: str = Field(
        ...,
        description="Complete narration text for the entire ad, concatenating all shot narrations with natural transitions.",
    )
