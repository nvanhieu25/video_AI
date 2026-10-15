import os
from datetime import UTC, datetime, timedelta

from app.domain.models import AssetOrigin
from app.infrastructure.storage import ArtifactStore


def test_put_bytes_is_content_addressed(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.put_bytes(b"frame", "image/png", AssetOrigin.generated, role="character")
    second = store.put_bytes(b"frame", "image/png", AssetOrigin.generated, role="character")
    assert first.sha256 == second.sha256
    assert first.asset_id == second.asset_id
    assert store.get_path(first.asset_id).read_bytes() == b"frame"


def test_expired_files_follow_the_retention_window(tmp_path):
    store = ArtifactStore(tmp_path)
    old = tmp_path / "blobs" / "old.bin"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    stale = datetime.now(UTC) - timedelta(days=40)
    os_time = stale.timestamp()
    os.utime(old, (os_time, os_time))
    due = store.expired_files(30, datetime.now(UTC))
    assert old in due
