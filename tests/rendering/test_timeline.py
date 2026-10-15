from uuid import uuid4

from app.application.qc import CandidateSelection
from app.domain.models import EpisodePlan, Shot, Storyboard
from app.rendering.subtitles import format_srt
from app.rendering.timeline import build_timeline


def _plan() -> EpisodePlan:
    return EpisodePlan(
        brief="brief",
        aspect_ratio="9:16",
        storyboards=[
            Storyboard(
                storyboard_id="b0",
                shots=[Shot(shot_id="b0-s1", action="looks", prompt="window", dialogue="Xin chào")],
                references=["character"],
            ),
            Storyboard(
                storyboard_id="b1",
                shots=[Shot(shot_id="b1-s1", action="turns", prompt="door", dialogue="Tạm biệt")],
                references=["character"],
            ),
        ],
    )


def test_timeline_uses_storyboard_order_and_voice_duration():
    first = uuid4()
    second = uuid4()
    timeline = build_timeline(
        _plan(),
        {
            "b0-s1": CandidateSelection(
                shot_id="b0-s1", asset_id=first, fallback=False, low_confidence=False
            ),
            "b1-s1": CandidateSelection(
                shot_id="b1-s1", asset_id=second, fallback=True, low_confidence=True
            ),
        },
        {"b0-s1": 1.5, "b1-s1": 0.5},
    )
    assert [clip.shot_id for clip in timeline.clips] == ["b0-s1", "b1-s1"]
    assert timeline.clips[0].duration_seconds == 1.5
    assert timeline.clips[1].fallback is True
    assert timeline.subtitles[0].text == "Xin chào"
    assert timeline.subtitles[1].start_seconds == 1.5
    srt = format_srt(timeline.subtitles)
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "Xin chào" in srt
    assert "Tạm biệt" in srt
