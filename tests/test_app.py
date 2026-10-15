import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    from fastapi.testclient import TestClient

    return TestClient(create_app())


def test_ready_endpoint_checks_the_database(client):
    assert client.get("/ready").json() == {"status": "ready"}


def test_health_endpoint_reports_application_name(client):
    assert client.get("/health").json() == {
        "status": "ok",
        "service": "richesse-video",
    }


def test_settings_rejects_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_ignores_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///from-dotenv.db\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError):
        Settings()
