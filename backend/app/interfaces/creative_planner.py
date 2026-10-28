"""Abstract base class for creative advertisement planners."""

from abc import ABC, abstractmethod

from app.schemas.storyboard import Storyboard


class CreativePlanner(ABC):
    """Interface for generating script and storyboard from a product brief."""

    @abstractmethod
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
        """Generate a structured script and sequence of storyboard shots covering the target duration."""
        pass
