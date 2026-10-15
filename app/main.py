from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.core.settings import Settings
from app.infrastructure.database import create_db_engine, create_schema, session_factory
from app.infrastructure.storage import ArtifactStore

WEB = Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    settings = Settings()
    engine = create_db_engine(settings.database_url)
    create_schema(engine)
    app = FastAPI(title=settings.service_name)
    app.state.session_factory = session_factory(engine)
    app.state.store = ArtifactStore(Path(settings.media_root))
    app.state.templates = Jinja2Templates(directory=str(WEB / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB / "static")), name="static")
    app.include_router(health_router)
    app.include_router(jobs_router)
    return app
