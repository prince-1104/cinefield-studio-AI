"""Abstract interface definitions for all pluggable studio providers."""

from app.interfaces.artifact_storage import ArtifactStorage
from app.interfaces.creative_planner import CreativePlanner
from app.interfaces.media_renderer import MediaRenderer
from app.interfaces.speech_provider import SpeechProvider
from app.interfaces.video_generator import VideoGenerationProvider

__all__ = [
    "ArtifactStorage",
    "CreativePlanner",
    "MediaRenderer",
    "SpeechProvider",
    "VideoGenerationProvider",
]
