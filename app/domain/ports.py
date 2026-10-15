from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.models import AssetRef, EpisodePlan


class ProviderNotConfigured(RuntimeError):
    """Raised before any network call when a provider has no credentials."""


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: str
    recipe_id: str
    aspect_ratio: str
    storyboard_min: int
    storyboard_max: int
    reference_count: int
    reference_roles: list[str]


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storyboard_id: str
    role: str
    prompt: str
    idempotency_key: str


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    text: str
    idempotency_key: str


class SpeechResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: AssetRef
    duration_seconds: float


class VideoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    prompt: str
    duration_seconds: float
    idempotency_key: str
    reference_asset_ids: list[UUID] = []


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hard_pass: bool
    soft_score: float
    reasons: list[str]


class Planner(Protocol):
    def plan(self, request: PlanRequest) -> EpisodePlan: ...


class ImageGenerator(Protocol):
    def generate(self, request: ImageRequest) -> AssetRef: ...


class SpeechGenerator(Protocol):
    def synthesize(self, request: SpeechRequest) -> SpeechResult: ...


class VideoGenerator(Protocol):
    def submit(self, request: VideoRequest) -> str: ...

    def poll(self, external_task_id: str) -> str: ...

    def retrieve(self, external_task_id: str) -> AssetRef: ...


class VisualEvaluator(Protocol):
    def evaluate(self, asset: AssetRef, prompt: str) -> Evaluation: ...
