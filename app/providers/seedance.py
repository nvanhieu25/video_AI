import os

from app.domain.models import AssetRef
from app.domain.ports import ProviderNotConfigured, VideoRequest


class SeedanceVideoGenerator:
    """Credential gate for Seedance. The base never opens a network call."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("SEEDANCE_API_KEY")

    def _require_configured(self) -> None:
        if not self.api_key:
            raise ProviderNotConfigured("Seedance credentials are not configured")

    def submit(self, request: VideoRequest) -> str:
        self._require_configured()
        raise ProviderNotConfigured("Seedance live submission is outside the base")

    def poll(self, external_task_id: str) -> str:
        self._require_configured()
        raise ProviderNotConfigured("Seedance live polling is outside the base")

    def retrieve(self, external_task_id: str) -> AssetRef:
        self._require_configured()
        raise ProviderNotConfigured("Seedance live retrieval is outside the base")
