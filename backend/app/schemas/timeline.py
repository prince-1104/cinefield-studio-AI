"""Pydantic schemas for canonical, editable timeline compositions."""

import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimelineSettings(BaseModel):
    """Render resolution, frame rate, and target constraints."""

    duration_target_seconds: int = Field(default=15, ge=5, le=120)
    aspect_ratio: Literal["16:9", "9:16"] = Field(default="16:9")
    fps: float = Field(default=24.0, ge=12.0, le=60.0)
    width: int = Field(default=1920)
    height: int = Field(default=1080)


class TimelineClip(BaseModel):
    """A video segment placed on the timeline with source in/out trim points."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    shot_id: str | None = None
    shot_number: int = 1
    source_path: str = Field(..., min_length=1)
    source_duration: float = Field(default=5.0, ge=0.1)
    source_start: float = Field(default=0.0, ge=0.0)
    source_end: float = Field(default=5.0, ge=0.1)
    timeline_start: float = Field(default=0.0, ge=0.0)
    duration: float = Field(default=5.0, ge=0.1)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    transition: str = Field(default="Cut")
    description: str | None = None
    visual_prompt: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "TimelineClip":
        if self.source_end < self.source_start:
            self.source_end = self.source_start + 0.1
        self.duration = round(self.source_end - self.source_start, 2)
        return self


class TimelineOverlay(BaseModel):
    """Brand watermark or visual overlay."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: Literal["logo", "watermark", "badge"] = "logo"
    asset_path: str = Field(..., min_length=1)
    timeline_start: float = Field(default=0.0, ge=0.0)
    timeline_end: float = Field(default=15.0, ge=0.1)
    position: Literal[
        "top_right", "top_left", "bottom_right", "bottom_left", "center"
    ] = "top_right"
    scale: float = Field(default=1.0, ge=0.2, le=2.5)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class TimelineAudio(BaseModel):
    """Voiceover narration or background soundtrack."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    track_type: Literal["narration", "music"] = "narration"
    source_path: str = Field(..., min_length=1)
    timeline_start: float = Field(default=0.0, ge=0.0)
    duration: float = Field(default=15.0, ge=0.1)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    fade_in: float = Field(default=0.0, ge=0.0, le=10.0)
    fade_out: float = Field(default=0.5, ge=0.0, le=10.0)
    ducking: bool = Field(default=True)


class TimelineCaption(BaseModel):
    """Subtitle or screen title overlay."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(..., min_length=1)
    timeline_start: float = Field(default=0.0, ge=0.0)
    timeline_end: float = Field(default=5.0, ge=0.1)
    font_size: int = Field(default=28, ge=12, le=72)
    font_color: str = Field(default="#ffffff")
    position: Literal["bottom", "center", "top"] = "bottom"
    style: Literal["standard", "boxed", "glow"] = "standard"


class TimelineData(BaseModel):
    """The complete multitrack timeline composition."""

    settings: TimelineSettings = Field(default_factory=TimelineSettings)
    video_clips: list[TimelineClip] = Field(default_factory=list)
    overlays: list[TimelineOverlay] = Field(default_factory=list)
    audio_tracks: list[TimelineAudio] = Field(default_factory=list)
    captions: list[TimelineCaption] = Field(default_factory=list)

    @property
    def total_duration(self) -> float:
        """Sum of sequential video clip durations."""
        return round(sum(c.duration for c in self.video_clips), 2)


class TimelineEditCreate(BaseModel):
    """Payload to save an updated timeline edit."""

    timeline_data: TimelineData


class TimelineEditResponse(BaseModel):
    """Response representing a persisted timeline edit version."""

    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    timeline_data: TimelineData
    is_current: bool
    rendered_video_path: str | None = None
    render_job_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineEditSummary(BaseModel):
    """Brief summary for version history dropdown."""

    id: uuid.UUID
    version: int
    is_current: bool
    clip_count: int
    duration: float
    has_rendered_video: bool
    created_at: datetime
