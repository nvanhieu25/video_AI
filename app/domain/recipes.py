from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class RecipeValidationError(ValueError):
    """A plan or recipe file violates the selected recipe."""


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    aspect_ratio: str
    storyboard_min: int
    storyboard_max: int
    reference_count: int
    shots_per_storyboard_min: int = 1
    shots_per_storyboard_max: int = 2
    reference_roles: list[str] = []
    resolution: str = "720p"
    target_duration_seconds: int = 120
    fallback: str = "reference_image_motion"
    max_attempts_per_shot: int = 2
    default_budget_cap: str | None = None
    product_closeup_requires_approved_asset: bool = True
    forbid_ai_branding: list[str] = []
    approved_claims: list[str] = []

    @model_validator(mode="after")
    def reference_roles_match_count(self) -> "Recipe":
        if self.reference_roles and len(self.reference_roles) != self.reference_count:
            raise ValueError("reference_roles length must equal reference_count")
        if self.storyboard_min > self.storyboard_max:
            raise ValueError("storyboard_min cannot exceed storyboard_max")
        return self


def load_recipe(path: Path | str) -> Recipe:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RecipeValidationError("recipe file must be a mapping")
    try:
        return Recipe.model_validate(raw)
    except ValidationError as exc:
        raise RecipeValidationError(str(exc)) from exc
