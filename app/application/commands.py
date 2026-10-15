from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubmitJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: str
    recipe_id: str
    approved_asset_ids: list[UUID] = Field(default_factory=list)
    budget_cap: str | None = None
