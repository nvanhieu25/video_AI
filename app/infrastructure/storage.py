import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.domain.models import AssetOrigin, AssetRef

ASSET_NAMESPACE = uuid.UUID("8c0d1e2a-3b4c-5d6e-7f80-91a2b3c4d5e6")


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put_bytes(
        self,
        data: bytes,
        media_type: str,
        origin: AssetOrigin,
        role: str | None = None,
    ) -> AssetRef:
        digest = hashlib.sha256(data).hexdigest()
        asset_id = uuid.uuid5(ASSET_NAMESPACE, digest)
        blob = self.root / "blobs" / digest
        blob.parent.mkdir(parents=True, exist_ok=True)
        if not blob.exists():
            blob.write_bytes(data)
        index = self.root / "ids" / str(asset_id)
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(digest, encoding="utf-8")
        return AssetRef(
            asset_id=asset_id,
            sha256=digest,
            uri=blob.resolve().as_uri(),
            media_type=media_type,
            origin=origin,
            role=role,
        )

    def expired_files(self, retention_days: int, now: datetime) -> list[Path]:
        if retention_days <= 0 or not self.root.exists():
            return []
        cutoff = now.timestamp() - retention_days * 86_400
        return [
            path
            for path in self.root.rglob("*")
            if path.is_file() and path.stat().st_mtime < cutoff
        ]

    def get_path(self, asset_id: uuid.UUID) -> Path:
        index = self.root / "ids" / str(asset_id)
        if not index.exists():
            raise KeyError(asset_id)
        digest = index.read_text(encoding="utf-8")
        return self.root / "blobs" / digest
