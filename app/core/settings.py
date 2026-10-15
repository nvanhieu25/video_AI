from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings supplied only by the process environment."""

    database_url: str = ""
    service_name: str = "richesse-video"
    media_root: str = "media"
    media_retention_days: int = 30

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
    )

    @model_validator(mode="after")
    def database_url_is_required(self) -> Self:
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        return self
