from collections.abc import Mapping

from app.application.qc import CandidateSelection
from app.domain.models import EpisodePlan, SubtitleCue, Timeline, TimelineClip


def build_timeline(
    plan: EpisodePlan,
    selections: Mapping[str, CandidateSelection],
    voices: Mapping[str, float],
) -> Timeline:
    cursor = 0.0
    clips: list[TimelineClip] = []
    subtitles: list[SubtitleCue] = []
    for board in plan.storyboards:
        for shot in board.shots:
            selection = selections[shot.shot_id]
            duration = voices[shot.shot_id]
            clips.append(
                TimelineClip(
                    storyboard_id=board.storyboard_id,
                    shot_id=shot.shot_id,
                    asset_id=selection.asset_id,
                    duration_seconds=duration,
                    fallback=selection.fallback,
                )
            )
            if shot.dialogue:
                subtitles.append(
                    SubtitleCue(
                        start_seconds=cursor,
                        end_seconds=cursor + duration,
                        text=shot.dialogue,
                    )
                )
            cursor += duration
    return Timeline(
        aspect_ratio=plan.aspect_ratio,
        resolution="720p",
        clips=clips,
        subtitles=subtitles,
    )
