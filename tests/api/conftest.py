import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = tmp_path / "jobs.db"
    media = tmp_path / "media"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("MEDIA_ROOT", str(media))
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
