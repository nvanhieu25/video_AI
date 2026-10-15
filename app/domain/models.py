from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.domain.recipes import Recipe


class JobStatus(StrEnum):
    queued = "queued"
    planning = "planning"
    generating = "generating"
    selecting = "selecting"
    rendering = "rendering"
    delivered = "delivered"
    delivered_with_flags = "delivered_with_flags"
    failed = "failed"


class TaskStatus(StrEnum):
    pending = "pending"
    leased = "leased"
    complete = "complete"
    failed = "failed"


class AssetOrigin(StrEnum):
    approved_real = "approved_real"
    generated = "generated"
    fallback = "fallback"


class AssetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    sha256: str
    uri: str
    media_type: str
    origin: AssetOrigin
    role: str | None = None


class Shot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str
    action: str
    prompt: str
    dialogue: str = ""
    product_closeup: bool = False
    approved_asset_id: UUID | None = None


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storyboard_id: str
    shots: list[Shot]
    references: list[str] = Field(default_factory=list)


class EpisodePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: str
    aspect_ratio: str
    storyboards: list[Storyboard]

    def validate_for(self, recipe: Recipe) -> None:
        from app.domain.recipes import RecipeValidationError

        errors: list[str] = []
        if self.aspect_ratio != recipe.aspect_ratio:
            errors.append(f"aspect ratio must be {recipe.aspect_ratio}")
        count = len(self.storyboards)
        if count < recipe.storyboard_min or count > recipe.storyboard_max:
            errors.append(
                f"storyboard count {count} is outside "
                f"{recipe.storyboard_min}-{recipe.storyboard_max}"
            )
        for board in self.storyboards:
            shot_count = len(board.shots)
            if (
                shot_count < recipe.shots_per_storyboard_min
                or shot_count > recipe.shots_per_storyboard_max
            ):
                errors.append(f"{board.storyboard_id} has {shot_count} shots")
            if len(board.references) != recipe.reference_count:
                errors.append(
                    f"{board.storyboard_id} needs {recipe.reference_count} references"
                )
            for shot in board.shots:
                if (
                    recipe.product_closeup_requires_approved_asset
                    and shot.product_closeup
                    and shot.approved_asset_id is None
                ):
                    errors.append(
                        f"{shot.shot_id} product close-up requires an approved real asset"
                    )
        if errors:
            raise RecipeValidationError("; ".join(errors))


class TimelineClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storyboard_id: str
    shot_id: str
    asset_id: UUID
    duration_seconds: float
    fallback: bool = False


class SubtitleCue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_seconds: float
    end_seconds: float
    text: str


class Timeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aspect_ratio: str
    resolution: str
    clips: list[TimelineClip]
    subtitles: list[SubtitleCue]
