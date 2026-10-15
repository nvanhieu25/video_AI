from app.domain.models import SubtitleCue


def format_srt(cues: list[SubtitleCue]) -> str:
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_timestamp(cue.start_seconds)} --> {_timestamp(cue.end_seconds)}\n{cue.text}\n"
        )
    return "\n".join(blocks)


def _timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
