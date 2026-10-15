import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.domain.models import Timeline
from app.rendering.subtitles import format_srt


class MediaValidationError(RuntimeError):
    """A source file cannot enter the timeline."""


@dataclass(frozen=True)
class MediaMetadata:
    width: int
    height: int
    duration_seconds: float
    aspect_ratio: str


@dataclass(frozen=True)
class RenderArtifact:
    video_path: Path
    srt_path: Path
    manifest_path: Path


class MediaInspector:
    def validate(self, path: Path, required_duration: float, aspect_ratio: str) -> MediaMetadata:
        metadata = _probe(path)
        if metadata.aspect_ratio != aspect_ratio:
            raise MediaValidationError(
                f"{path.name} is {metadata.aspect_ratio}, expected {aspect_ratio}"
            )
        if abs(metadata.duration_seconds - required_duration) > 0.35:
            raise MediaValidationError(
                f"{path.name} duration {metadata.duration_seconds} != {required_duration}"
            )
        return metadata


class FfmpegRenderer:
    def render(
        self,
        timeline: Timeline,
        output_dir: Path,
        sources: dict[UUID, Path],
    ) -> RenderArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        normalized: list[Path] = []
        for index, clip in enumerate(timeline.clips):
            source = sources[clip.asset_id]
            target = output_dir / f"part-{index}.mp4"
            if _is_still(source):
                _motion_from_still(source, target, clip.duration_seconds)
            elif clip.fallback and not _readable(source):
                _color_video(target, clip.duration_seconds, "0x333333")
            else:
                MediaInspector().validate(source, clip.duration_seconds, timeline.aspect_ratio)
                _normalize_video(source, target, clip.duration_seconds)
            normalized.append(target)
        video_path = output_dir / "final.mp4"
        _concat(normalized, video_path, sum(clip.duration_seconds for clip in timeline.clips))
        srt_path = output_dir / "final.srt"
        srt_path.write_text(format_srt(timeline.subtitles), encoding="utf-8")
        manifest_path = output_dir / "timeline.json"
        manifest_path.write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
        return RenderArtifact(
            video_path=video_path, srt_path=srt_path, manifest_path=manifest_path
        )


def color_clip_bytes(duration: float, color: str) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "clip.mp4"
        _color_video(path, duration, color)
        return path.read_bytes()


def _probe(path: Path) -> MediaMetadata:
    if not path.is_file():
        raise MediaValidationError(f"{path} is missing")
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration,codec_name",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise MediaValidationError(f"{path.name} is not readable media")
    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise MediaValidationError(f"{path.name} has no video stream")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise MediaValidationError(f"{path.name} has no video stream")
    width = stream.get("width")
    height = stream.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or height == 0:
        raise MediaValidationError(f"{path.name} has no frame size")
    raw_duration = stream.get("duration", 0)
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError) as exc:
        raise MediaValidationError(f"{path.name} has no duration") from exc
    return MediaMetadata(
        width=width,
        height=height,
        duration_seconds=duration,
        aspect_ratio=_aspect_ratio(width, height),
    )


def _aspect_ratio(width: int, height: int) -> str:
    if height > width:
        return "9:16"
    if width > height:
        return "16:9"
    return "1:1"


def _readable(path: Path) -> bool:
    try:
        _probe(path)
    except MediaValidationError:
        return False
    return True


def _is_still(path: Path) -> bool:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return True
    try:
        metadata = _probe(path)
    except MediaValidationError:
        return False
    return metadata.duration_seconds <= 0.05


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise MediaValidationError(completed.stderr[-500:])


def _color_video(path: Path, duration: float, color: str) -> None:
    length = max(duration, 0.2)
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=720x1280:d={length:.3f}",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(path),
        ]
    )


def _normalize_video(source: Path, target: Path, duration: float) -> None:
    length = max(duration, 0.2)
    _run(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(source),
            "-t",
            f"{length:.3f}",
            "-vf",
            "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=25,setsar=1",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(target),
        ]
    )


def _motion_from_still(source: Path, target: Path, duration: float) -> None:
    frames = max(int(duration * 25), 5)
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(source),
            "-vf",
            (
                "scale=800:1422,"
                f"zoompan=z='min(1.0+0.001*on,1.08)':d={frames}:s=720x1280:fps=25,setsar=1"
            ),
            "-t",
            f"{max(duration, 0.2):.3f}",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(target),
        ]
    )


def _concat(parts: list[Path], target: Path, duration: float) -> None:
    inputs: list[str] = []
    for part in parts:
        inputs.extend(["-i", str(part)])
    scaled = [
        f"[{index}:v]scale=720:1280,setsar=1[v{index}]" for index in range(len(parts))
    ]
    labels = "".join(f"[v{index}]" for index in range(len(parts)))
    _run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-f",
            "lavfi",
            "-t",
            f"{max(duration, 0.2):.3f}",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-filter_complex",
            ";".join(scaled) + f";{labels}concat=n={len(parts)}:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            f"{len(parts)}:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(target),
        ]
    )
