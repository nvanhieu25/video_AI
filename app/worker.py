import os
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.application.dispatcher import run_once
from app.application.workflow import Services
from app.core.settings import Settings
from app.infrastructure.database import create_db_engine, create_schema, session_factory
from app.infrastructure.storage import ArtifactStore
from app.providers.fake import (
    FakeImageGenerator,
    FakePlanner,
    FakeSpeechGenerator,
    FakeVideoGenerator,
    FakeVisualEvaluator,
)


def build_services(session: Session, store: ArtifactStore) -> Services:
    return Services(
        session=session,
        store=store,
        planner=FakePlanner(),
        images=FakeImageGenerator(store),
        speech=FakeSpeechGenerator(store),
        video=FakeVideoGenerator(store),
        evaluator=FakeVisualEvaluator(),
    )


def main() -> None:
    settings = Settings()
    engine = create_db_engine(settings.database_url)
    create_schema(engine)
    factory = session_factory(engine)
    store = ArtifactStore(Path(settings.media_root))
    worker_id = os.environ.get("WORKER_ID", "worker-1")
    while True:
        with factory() as session:
            processed = run_once(worker_id, services=build_services(session, store))
        if processed == 0:
            time.sleep(2)


if __name__ == "__main__":
    main()
