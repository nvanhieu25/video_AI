import pytest

from app.domain.models import AssetOrigin
from app.domain.ports import (
    ImageRequest,
    PlanRequest,
    ProviderNotConfigured,
    SpeechRequest,
    VideoRequest,
)
from app.infrastructure.storage import ArtifactStore
from app.providers.fake import (
    FakeImageGenerator,
    FakePlanner,
    FakeSpeechGenerator,
    FakeVideoGenerator,
)
from app.providers.minimax import MiniMaxSpeechGenerator
from app.providers.seedance import SeedanceVideoGenerator


def plan_request() -> PlanRequest:
    return PlanRequest(
        brief="Hai người gặp lại nhau dưới mưa.",
        recipe_id="drama_vertical_120s_v1",
        aspect_ratio="9:16",
        storyboard_min=10,
        storyboard_max=12,
        reference_count=9,
        reference_roles=[f"role-{index}" for index in range(9)],
    )


def test_fake_plan_is_deterministic_and_respects_reference_count():
    planner = FakePlanner()
    first = planner.plan(plan_request())
    second = planner.plan(plan_request())
    assert first == second
    assert len(first.storyboards) == 10
    assert len(first.storyboards[0].references) == 9


def test_fake_media_results_are_deterministic(tmp_path):
    store = ArtifactStore(tmp_path)
    image_request = ImageRequest(
        storyboard_id="b0",
        role="character",
        prompt="a person by a window",
        idempotency_key="job:image:b0:character",
    )
    speech_request = SpeechRequest(
        shot_id="b0-s1",
        text="Xin chào",
        idempotency_key="job:speech:b0-s1",
    )
    video_request = VideoRequest(
        shot_id="b0-s1",
        prompt="a person by a window",
        duration_seconds=1.25,
        idempotency_key="job:video:b0-s1",
    )
    images = FakeImageGenerator(store)
    speech = FakeSpeechGenerator(store)
    video = FakeVideoGenerator(store)
    assert images.generate(image_request) == images.generate(image_request)
    spoken = speech.synthesize(speech_request)
    assert spoken == speech.synthesize(speech_request)
    assert spoken.duration_seconds > 0
    assert spoken.asset.origin == AssetOrigin.generated
    external_id = video.submit(video_request)
    assert video.submit(video_request) == external_id
    assert video.poll(external_id) == "succeeded"
    assert video.retrieve(external_id) == video.retrieve(external_id)


def test_unconfigured_providers_do_not_call_the_network(monkeypatch):
    monkeypatch.delenv("SEEDANCE_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    video = VideoRequest(
        shot_id="b0-s1",
        prompt="a person by a window",
        duration_seconds=1.0,
        idempotency_key="job:video:b0-s1",
    )
    speech = SpeechRequest(shot_id="b0-s1", text="Xin chào", idempotency_key="job:speech:b0-s1")
    with pytest.raises(ProviderNotConfigured):
        SeedanceVideoGenerator().submit(video)
    with pytest.raises(ProviderNotConfigured):
        MiniMaxSpeechGenerator().synthesize(speech)
