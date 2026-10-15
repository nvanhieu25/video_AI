import re
from typing import cast

SECRET_NAME = re.compile(r"(api[_-]?key|secret|token|password|authorization)", re.IGNORECASE)
SECRET_VALUE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}|bearer\s+\S+", re.IGNORECASE)


def redact(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            name = str(key)
            cleaned[name] = "[REDACTED]" if SECRET_NAME.search(name) else redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub("[REDACTED]", value)
    return value


def redact_text(value: str) -> str:
    redacted = redact(value)
    return cast(str, redacted)
