import shutil
import subprocess
from uuid import uuid4

import pytest

from app.application.qc import CandidateSelection
from app.domain.models import EpisodePlan, Shot, Storyboard
from app.rendering.ffmpeg import FfmpegRenderer, MediaInspector, MediaValidationError
from app.rendering.timeline import build_timeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def _color_video(path, size: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x224466:s={size}:d=0.4",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_inspector_rejects_unreadable_and_wrong_aspect(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("not media", encoding="utf-8")
    inspector = MediaInspector()
    with pytest.raises(MediaValidationError):
        inspector.validate(notes, required_duration=0.4, aspect_ratio="9:16")
    wide = tmp_path / "wide.mp4"
    _color_video(wide, "1280x720")
    with pytest.raises(MediaValidationError):
        inspector.validate(wide, required_duration=0.4, aspect_ratio="9:16")


def test_renderer_writes_a_playable_vertical_mp4(tmp_path):
    clip = tmp_path / "clip.mp4"
    still = tmp_path / "still.png"
    _color_video(clip, "720x1280")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x112233:s=720x1280:d=0.2", "-frames:v", "1", str(still)],
        check=True,
        capture_output=True,
    )
    video_id = uuid4()
    image_id = uuid4()
    plan = EpisodePlan(
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
    timeline = build_timeline(
        plan,
        {
            "b0-s1": CandidateSelection(
                shot_id="b0-s1", asset_id=video_id, fallback=False, low_confidence=False
            ),
            "b1-s1": CandidateSelection(
                shot_id="b1-s1", asset_id=image_id, fallback=True, low_confidence=True
            ),
        },
        {"b0-s1": 0.4, "b1-s1": 0.4},
    )
    rendered = FfmpegRenderer().render(
        timeline,
        tmp_path / "out",
        {video_id: clip, image_id: still},
    )
    metadata = MediaInspector().validate(
        rendered.video_path, required_duration=0.8, aspect_ratio="9:16"
    )
    assert metadata.width == 720
    assert metadata.height == 1280
    assert "Xin chào" in rendered.srt_path.read_text(encoding="utf-8")
    assert rendered.manifest_path.exists()
