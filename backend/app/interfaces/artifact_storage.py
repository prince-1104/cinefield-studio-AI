"""Abstract base class for media and artifact storage."""

from abc import ABC, abstractmethod
from pathlib import Path


class ArtifactStorage(ABC):
    """Interface for persisting and reading media files (local filesystem or object store)."""

    @abstractmethod
    async def save(self, data: bytes, destination_key: str) -> str:
        """Save raw bytes to storage and return its identifier or local path."""
        pass

    @abstractmethod
    async def load(self, source_key: str) -> bytes:
        """Read and return raw bytes from storage."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether an artifact exists in storage."""
        pass

    @abstractmethod
    def get_local_path(self, key: str) -> str:
        """Resolve a local filesystem path for tools that require direct POSIX file paths."""
        pass
