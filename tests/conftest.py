import pytest

from app.application.workflow import Services
from app.domain.models import AssetRef
from app.domain.ports import VideoRequest
from app.infrastructure.database import create_db_engine, create_schema, session_factory
from app.infrastructure.storage import ArtifactStore
from app.providers.fake import (
    FakeImageGenerator,
    FakePlanner,
    FakeSpeechGenerator,
    FakeVideoGenerator,
    FakeVisualEvaluator,
)


class InterruptingVideo:
    def __init__(self, inner: FakeVideoGenerator) -> None:
        self.inner = inner
        self.submitted: list[str] = []
        self.interrupt = True

    def submit(self, request: VideoRequest) -> str:
        self.submitted.append(request.idempotency_key)
        return self.inner.submit(request)

    def poll(self, external_task_id: str) -> str:
        return self.inner.poll(external_task_id)

    def retrieve(self, external_task_id: str) -> AssetRef:
        if self.interrupt:
            self.interrupt = False
            raise RuntimeError("worker interrupted")
        return self.inner.retrieve(external_task_id)


@pytest.fixture
def services(tmp_path):
    engine = create_db_engine("sqlite://")
    create_schema(engine)
    session = session_factory(engine)()
    store = ArtifactStore(tmp_path)
    video = InterruptingVideo(FakeVideoGenerator(store))
    bundle = Services(
        session=session,
        store=store,
        planner=FakePlanner(),
        images=FakeImageGenerator(store),
        speech=FakeSpeechGenerator(store),
        video=video,
        evaluator=FakeVisualEvaluator(),
    )
    return bundle, video
