import hashlib

from app.domain.models import AssetOrigin, AssetRef, EpisodePlan, Shot, Storyboard
from app.domain.ports import (
    Evaluation,
    ImageRequest,
    PlanRequest,
    SpeechRequest,
    SpeechResult,
    VideoRequest,
)
from app.infrastructure.storage import ArtifactStore


class FakePlanner:
    def plan(self, request: PlanRequest) -> EpisodePlan:
        storyboards: list[Storyboard] = []
        for index in range(request.storyboard_min):
            storyboards.append(
                Storyboard(
                    storyboard_id=f"b{index}",
                    shots=[
                        Shot(
                            shot_id=f"b{index}-s1",
                            action="turns toward the window",
                            prompt=f"scene {index}: {request.brief}",
                            dialogue="Xin chào",
                        )
                    ],
                    references=list(request.reference_roles),
                )
            )
        return EpisodePlan(
            brief=request.brief,
            aspect_ratio=request.aspect_ratio,
            storyboards=storyboards,
        )


class FakeImageGenerator:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def generate(self, request: ImageRequest) -> AssetRef:
        data = f"image:{request.idempotency_key}:{request.role}:{request.prompt}".encode()
        return self.store.put_bytes(data, "image/png", AssetOrigin.generated, role=request.role)


class FakeSpeechGenerator:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        data = f"speech:{request.idempotency_key}:{request.text}".encode()
        asset = self.store.put_bytes(data, "audio/wav", AssetOrigin.generated, role="dialogue")
        duration = max(0.4, round(len(request.text) * 0.08, 2))
        return SpeechResult(asset=asset, duration_seconds=duration)


class FakeVideoGenerator:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self._requests: dict[str, VideoRequest] = {}

    def submit(self, request: VideoRequest) -> str:
        external_id = f"fake-{request.idempotency_key}"
        self._requests.setdefault(external_id, request)
        return external_id

    def poll(self, external_task_id: str) -> str:
        if external_task_id not in self._requests:
            raise KeyError(external_task_id)
        return "succeeded"

    def retrieve(self, external_task_id: str) -> AssetRef:
        request = self._requests[external_task_id]
        from app.rendering.ffmpeg import color_clip_bytes

        color = "0x" + hashlib.sha256(request.idempotency_key.encode()).hexdigest()[:6]
        data = color_clip_bytes(max(request.duration_seconds, 0.2), color)
        return self.store.put_bytes(data, "video/mp4", AssetOrigin.generated)


class FakeVisualEvaluator:
    def evaluate(self, asset: AssetRef, prompt: str) -> Evaluation:
        return Evaluation(hard_pass=True, soft_score=0.91, reasons=[f"checked {asset.sha256[:8]}"])
