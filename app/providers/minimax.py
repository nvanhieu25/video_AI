import os

from app.domain.ports import ProviderNotConfigured, SpeechRequest, SpeechResult


class MiniMaxSpeechGenerator:
    """Credential gate for MiniMax. The base never opens a network call."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("MINIMAX_API_KEY")

    def _require_configured(self) -> None:
        if not self.api_key:
            raise ProviderNotConfigured("MiniMax credentials are not configured")

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        self._require_configured()
        raise ProviderNotConfigured("MiniMax live synthesis is outside the base")
