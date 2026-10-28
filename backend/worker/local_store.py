"""Local filesystem implementation of the ArtifactStorage interface."""

from pathlib import Path

from app.config import settings
from app.interfaces.artifact_storage import ArtifactStorage


class LocalArtifactStorage(ArtifactStorage):
    """Stores generated media and assets on the local filesystem."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.ARTIFACT_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_local_path(self, key: str) -> str:
        """Resolve a storage key to an absolute filesystem path."""
        path = Path(key)
        if path.is_absolute():
            return str(path)
        return str(self.base_dir / key)

    async def save(self, data: bytes, destination_key: str) -> str:
        """Write raw bytes to the specified key/path."""
        dest = Path(self.get_local_path(destination_key))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    async def load(self, source_key: str) -> bytes:
        """Read bytes from the specified key/path."""
        src = Path(self.get_local_path(source_key))
        if not src.is_file():
            raise FileNotFoundError(f"Artifact not found at {src}")
        return src.read_bytes()

    async def exists(self, key: str) -> bool:
        """Check whether the file exists on the filesystem."""
        return Path(self.get_local_path(key)).is_file()

