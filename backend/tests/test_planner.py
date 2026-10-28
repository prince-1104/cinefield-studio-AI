"""Tests for Phase P3: Pluggable Interfaces, Local Storage, and Gemini Planner."""

import inspect
import json
import os
from pathlib import Path

from app.interfaces.artifact_storage import ArtifactStorage
from app.interfaces.creative_planner import CreativePlanner
from app.interfaces.media_renderer import MediaRenderer
from app.interfaces.speech_provider import SpeechProvider
from app.interfaces.video_generator import VideoGenerationProvider
from app.schemas.storyboard import Storyboard, StoryboardShot
from worker.gemini_planner import GeminiPlanner
from worker.local_store import LocalArtifactStorage


async def test_interfaces_structure() -> None:
    """Verify all 5 interfaces define the required abstract methods."""
    interfaces = [
        ArtifactStorage,
        CreativePlanner,
        MediaRenderer,
        SpeechProvider,
        VideoGenerationProvider,
    ]
    for iface in interfaces:
        assert inspect.isabstract(iface), f"{iface.__name__} should be abstract"

    # Verify CreativePlanner abstract methods
    assert "plan_storyboard" in CreativePlanner.__abstractmethods__

    # Verify VideoGenerationProvider abstract methods
    assert "generate_clip" in VideoGenerationProvider.__abstractmethods__

    # Verify SpeechProvider abstract methods
    assert "synthesize" in SpeechProvider.__abstractmethods__

    # Verify MediaRenderer abstract methods
    assert "render_advertisement" in MediaRenderer.__abstractmethods__

    # Verify ArtifactStorage abstract methods
    assert "save" in ArtifactStorage.__abstractmethods__
    assert "load" in ArtifactStorage.__abstractmethods__


async def test_local_artifact_storage(tmp_path: Path) -> None:
    """Verify LocalArtifactStorage persists and retrieves raw bytes."""
    store = LocalArtifactStorage(base_dir=str(tmp_path))

    test_data = b"video-frame-bytes-12345"
    key = "projects/test-proj/clips/shot1.mp4"

    # Save
    saved_path = await store.save(test_data, key)
    assert Path(saved_path).is_file()

    # Exists
    assert await store.exists(key)
    assert not await store.exists("non-existent.mp4")

    # Load
    loaded_data = await store.load(key)
    assert loaded_data == test_data

    # Resolve local path
    local_path = store.get_local_path(key)
    assert str(tmp_path) in local_path


async def test_storyboard_schema_validation() -> None:
    """Verify Storyboard Pydantic schema strictly enforces 3 shots."""
    raw_payload = {
        "title": "Quantum Coffee Commercial",
        "script_summary": "Morning fog lifts to reveal cold brew precision.",
        "full_narration": "Wake up. Feel the precision. Taste Quantum.",
        "shots": [
            {
                "shot_number": 1,
                "description": "Macro shot of coffee droplet falling in slow motion",
                "visual_prompt": "Ultra macro 8K shot of single dark roast droplet falling against neon black background",
                "narration_text": "Wake up.",
                "duration_hint": "5s",
            },
            {
                "shot_number": 2,
                "description": "Sleek matte-black machine brewing coffee under soft studio lighting",
                "visual_prompt": "Cinematic pan around matte-black titanium coffee machine with warm golden crema flowing",
                "narration_text": "Feel the precision.",
                "duration_hint": "6s",
            },
            {
                "shot_number": 3,
                "description": "Steaming cup held looking over mountain sunrise with logo watermark",
                "visual_prompt": "Wide 16:9 aerial shot of traveler savoring coffee on balcony overlooking sunrise mist",
                "narration_text": "Taste Quantum.",
                "duration_hint": "6s",
            },
        ],
    }

    storyboard = Storyboard.model_validate(raw_payload)
    assert storyboard.title == "Quantum Coffee Commercial"
    assert len(storyboard.shots) == 3
    assert storyboard.shots[0].shot_number == 1
    assert storyboard.shots[2].shot_number == 3

    # Test invalid shot count (< 3)
    invalid_payload = dict(raw_payload)
    invalid_payload["shots"] = raw_payload["shots"][:2]
    try:
        Storyboard.model_validate(invalid_payload)
        assert False, "Should have raised validation error for < 3 shots"
    except Exception:
        pass  # Expected


async def test_gemini_planner_key_guard() -> None:
    """Verify GeminiPlanner refuses to silently mock and raises RuntimeError when key is missing."""
    planner = GeminiPlanner(api_key="")
    try:
        await planner.plan_storyboard(
            product_name="Test Product",
            brief="A revolutionary gadget",
            audience="Consumers",
            tone="Exciting",
            cta="Buy now",
        )
        assert False, "Should have raised RuntimeError for unconfigured GEMINI_API_KEY"
    except RuntimeError as err:
        assert "GEMINI_API_KEY is not configured" in str(err)


async def run_all() -> None:
    print("Running test_interfaces_structure...")
    await test_interfaces_structure()

    print("Running test_local_artifact_storage...")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        await test_local_artifact_storage(Path(tmp_dir))

    print("Running test_storyboard_schema_validation...")
    await test_storyboard_schema_validation()

    print("Running test_gemini_planner_key_guard...")
    await test_gemini_planner_key_guard()

    print("Phase P3 tests PASSED! Interfaces, storage, schema, and planner guards verified.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_all())
