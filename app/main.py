from fastapi import FastAPI

from app.core.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title=settings.service_name)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return app
