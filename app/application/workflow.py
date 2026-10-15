import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.commands import SubmitJob
from app.application.policy import BudgetPolicy, RetryAction, RetryPolicy
from app.application.qc import Candidate, CandidateSelection, select_candidate
from app.domain.models import AssetOrigin, EpisodePlan, JobStatus, Shot, Storyboard
from app.domain.ports import (
    ImageGenerator,
    ImageRequest,
    Planner,
    PlanRequest,
    SpeechGenerator,
    SpeechRequest,
    VideoGenerator,
    VideoRequest,
    VisualEvaluator,
)
from app.domain.recipes import Recipe, load_recipe
from app.infrastructure.repositories import (
    ArtifactRecord,
    ArtifactWrite,
    AttemptWrite,
    JobRecord,
    JobRepository,
    TaskRecord,
    TaskRepository,
)
from app.infrastructure.storage import ArtifactStore
from app.rendering.ffmpeg import FfmpegRenderer
from app.rendering.timeline import build_timeline

RECIPES = Path(__file__).resolve().parents[1] / "recipes"


@dataclass
class Services:
    session: Session
    store: ArtifactStore
    planner: Planner
    images: ImageGenerator
    speech: SpeechGenerator
    video: VideoGenerator
    evaluator: VisualEvaluator

    @property
    def jobs(self) -> JobRepository:
        return JobRepository(self.session)

    @property
    def tasks(self) -> TaskRepository:
        return TaskRepository(self.session)


def stage_key(version_id: str, stage: str, target_id: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode()).hexdigest()[:16]
    return f"{version_id}:{stage}:{target_id}:{digest}"


def submit_job(command: SubmitJob, *, services: Services) -> UUID:
    recipe, recipe_hash = _load_recipe(command.recipe_id)
    created = services.jobs.create_job(
        brief=command.brief,
        recipe_id=recipe.recipe_id,
        recipe_hash=recipe_hash,
        budget_cap=command.budget_cap or recipe.default_budget_cap,
    )
    services.jobs.record_event(
        created.version_id,
        "job.submitted",
        {"approved_asset_ids": [str(asset_id) for asset_id in command.approved_asset_ids]},
    )
    _enqueue(
        services,
        created,
        "plan",
        "episode",
        {"recipe_id": recipe.recipe_id, "recipe_hash": recipe_hash},
    )
    services.session.commit()
    return created.job_id


def advance_job(job_id: UUID, *, services: Services) -> None:
    job = services.jobs.get_job(job_id)
    recipe, _recipe_hash = _load_recipe(job.recipe_id)
    raw_plan = services.jobs.get_plan(job.version_id)
    if raw_plan is None:
        _enqueue(services, job, "plan", "episode", {"recipe_id": recipe.recipe_id, "recipe_hash": job.recipe_hash})
        return
    plan = EpisodePlan.model_validate(raw_plan)
    _enqueue_ready(services, job, recipe, plan)


def execute_task(services: Services, task: TaskRecord) -> None:
    job = _job_for_task(services, task)
    recipe, _recipe_hash = _load_recipe(job.recipe_id)
    if task.kind == "plan":
        _run_plan(services, job, recipe)
    else:
        raw_plan = services.jobs.get_plan(job.version_id)
        if raw_plan is None:
            raise RuntimeError("plan is missing")
        plan = EpisodePlan.model_validate(raw_plan)
        if task.kind == "reference":
            _run_reference(services, job, recipe, plan, task)
        elif task.kind == "speech":
            _run_speech(services, job, recipe, plan, task)
        elif task.kind == "video":
            _run_video(services, job, recipe, task)
        elif task.kind == "render":
            _run_render(services, job, plan)
        else:
            raise RuntimeError(f"unknown task kind {task.kind}")
    saved = services.jobs.get_plan(job.version_id)
    if saved is not None:
        _enqueue_ready(services, job, recipe, EpisodePlan.model_validate(saved))


def _run_plan(services: Services, job: JobRecord, recipe: Recipe) -> None:
    services.jobs.set_status(job.version_id, JobStatus.planning)
    roles = recipe.reference_roles or [f"ref-{index}" for index in range(recipe.reference_count)]
    plan = services.planner.plan(
        PlanRequest(
            brief=job.brief,
            recipe_id=recipe.recipe_id,
            aspect_ratio=recipe.aspect_ratio,
            storyboard_min=recipe.storyboard_min,
            storyboard_max=recipe.storyboard_max,
            reference_count=recipe.reference_count,
            reference_roles=roles,
        )
    )
    plan.validate_for(recipe)
    services.jobs.save_plan(job.version_id, _json_dict(plan.model_dump(mode="json")))
    services.jobs.set_status(job.version_id, JobStatus.generating)
    services.jobs.record_event(job.version_id, "plan.completed", {"storyboards": len(plan.storyboards)})


def _run_reference(
    services: Services, job: JobRecord, recipe: Recipe, plan: EpisodePlan, task: TaskRecord
) -> None:
    storyboard_id = _text(task.payload, "storyboard_id")
    role = _text(task.payload, "role")
    board = _board(plan, storyboard_id)
    if not _can_generate(services, job, recipe):
        _store_asset(
            services,
            job,
            data=f"fallback-ref:{storyboard_id}:{role}".encode(),
            media_type="image/png",
            origin=AssetOrigin.fallback,
            role=role,
            lineage={"stage": "reference", "storyboard_id": storyboard_id, "role": role, "fallback": True},
        )
        return
    asset = services.images.generate(
        ImageRequest(
            storyboard_id=storyboard_id,
            role=role,
            prompt=board.shots[0].prompt,
            idempotency_key=task.idempotency_key,
        )
    )
    services.jobs.save_artifact(
        ArtifactWrite(
            version_id=job.version_id,
            asset_id=asset.asset_id,
            sha256=asset.sha256,
            uri=asset.uri,
            media_type=asset.media_type,
            origin=asset.origin,
            role=role,
            lineage={"stage": "reference", "storyboard_id": storyboard_id, "role": role},
            cost="0",
        )
    )


def _run_speech(
    services: Services, job: JobRecord, recipe: Recipe, plan: EpisodePlan, task: TaskRecord
) -> None:
    shot = _shot(plan, _text(task.payload, "shot_id"))
    if not _can_generate(services, job, recipe):
        _store_asset(
            services,
            job,
            data=f"fallback-speech:{shot.shot_id}".encode(),
            media_type="audio/wav",
            origin=AssetOrigin.fallback,
            role="dialogue",
            lineage={
                "stage": "speech",
                "shot_id": shot.shot_id,
                "duration_seconds": "1.00",
                "fallback": True,
            },
        )
        return
    spoken = services.speech.synthesize(
        SpeechRequest(shot_id=shot.shot_id, text=shot.dialogue, idempotency_key=task.idempotency_key)
    )
    services.jobs.save_artifact(
        ArtifactWrite(
            version_id=job.version_id,
            asset_id=spoken.asset.asset_id,
            sha256=spoken.asset.sha256,
            uri=spoken.asset.uri,
            media_type=spoken.asset.media_type,
            origin=spoken.asset.origin,
            role="dialogue",
            lineage={
                "stage": "speech",
                "shot_id": shot.shot_id,
                "duration_seconds": f"{spoken.duration_seconds:.2f}",
            },
            cost="0",
        )
    )


def _run_video(services: Services, job: JobRecord, recipe: Recipe, task: TaskRecord) -> None:
    shot_id = _text(task.payload, "shot_id")
    existing = services.jobs.get_attempt_by_key(task.idempotency_key)
    if existing is not None and existing.external_task_id:
        external_task_id = existing.external_task_id
    elif not _can_generate(services, job, recipe):
        _store_fallback_clip(services, job, task)
        return
    else:
        started = _video_attempts(services, job, shot_id)
        action = RetryPolicy(recipe.max_attempts_per_shot).next_action(
            attempts_started=started, last_hard_pass=False
        )
        if action == RetryAction.fallback:
            _store_fallback_clip(services, job, task)
            return
        external_task_id = services.video.submit(
            VideoRequest(
                shot_id=_text(task.payload, "shot_id"),
                prompt=_text(task.payload, "prompt"),
                duration_seconds=float(_text(task.payload, "duration_seconds")),
                idempotency_key=task.idempotency_key,
            )
        )
        services.jobs.save_attempt(
            AttemptWrite(
                version_id=job.version_id,
                idempotency_key=task.idempotency_key,
                stage="video",
                target_id=_text(task.payload, "shot_id"),
                provider_alias="fake",
                external_task_id=external_task_id,
                status="submitted",
                cost="0",
            )
        )
        services.jobs.record_event(
            job.version_id,
            "video.submitted",
            {"external_task_id": external_task_id, "shot_id": _text(task.payload, "shot_id")},
        )
        services.session.commit()
    if services.video.poll(external_task_id) != "succeeded":
        raise RuntimeError("video attempt is not ready")
    asset = services.video.retrieve(external_task_id)
    evaluation = services.evaluator.evaluate(asset, _text(task.payload, "prompt"))
    services.jobs.save_artifact(
        ArtifactWrite(
            version_id=job.version_id,
            asset_id=asset.asset_id,
            sha256=asset.sha256,
            uri=asset.uri,
            media_type=asset.media_type,
            origin=asset.origin,
            role="clip",
            lineage={
                "stage": "video",
                "shot_id": _text(task.payload, "shot_id"),
                "storyboard_id": _text(task.payload, "storyboard_id"),
                "external_task_id": external_task_id,
                "hard_pass": evaluation.hard_pass,
                "soft_score": evaluation.soft_score,
            },
            cost="0",
        )
    )
    services.jobs.update_attempt(task.idempotency_key, status="retrieved")


def _run_render(services: Services, job: JobRecord, plan: EpisodePlan) -> None:
    services.jobs.set_status(job.version_id, JobStatus.rendering)
    selections, voices, sources = _timeline_inputs(services, job, plan)
    timeline = build_timeline(plan, selections, voices)
    output_dir = services.store.root / "renders" / str(job.version_id)
    rendered = FfmpegRenderer().render(timeline, output_dir, sources)
    _store_asset(
        services,
        job,
        data=rendered.video_path.read_bytes(),
        media_type="video/mp4",
        origin=AssetOrigin.generated,
        role="final",
        lineage={"stage": "render", "kind": "mp4"},
    )
    _store_asset(
        services,
        job,
        data=rendered.srt_path.read_bytes(),
        media_type="application/x-subrip",
        origin=AssetOrigin.generated,
        role="captions",
        lineage={"stage": "render", "kind": "srt"},
    )
    _store_asset(
        services,
        job,
        data=rendered.manifest_path.read_bytes(),
        media_type="application/json",
        origin=AssetOrigin.generated,
        role="manifest",
        lineage={"stage": "render", "kind": "timeline"},
    )
    flagged = _timeline_has_flags(services, job, plan)
    status = JobStatus.delivered_with_flags if flagged else JobStatus.delivered
    services.jobs.set_status(job.version_id, status)
    services.jobs.record_event(job.version_id, "job.delivered", {"status": status.value})


def _timeline_inputs(
    services: Services, job: JobRecord, plan: EpisodePlan
) -> tuple[dict[str, CandidateSelection], dict[str, float], dict[UUID, Path]]:
    artifacts = services.jobs.list_artifacts(job.version_id)
    selections: dict[str, CandidateSelection] = {}
    voices: dict[str, float] = {}
    sources: dict[UUID, Path] = {}
    for board in plan.storyboards:
        for shot in board.shots:
            clips = [
                artifact
                for artifact in artifacts
                if artifact.lineage.get("stage") == "video"
                and artifact.lineage.get("shot_id") == shot.shot_id
            ]
            chosen = select_candidate(
                [
                    Candidate(
                        shot_id=shot.shot_id,
                        asset_id=artifact.asset_id,
                        hard_pass=_as_bool(artifact.lineage.get("hard_pass")),
                        soft_score=_as_float(artifact.lineage.get("soft_score")),
                        fallback=_as_bool(artifact.lineage.get("fallback")),
                    )
                    for artifact in clips
                ]
            )
            speech = _find_lineage(artifacts, stage="speech", shot_id=shot.shot_id)
            duration = 1.0
            if speech is not None:
                raw = speech.get("duration_seconds", "1.00")
                duration = float(raw) if isinstance(raw, str | int | float) and not isinstance(raw, bool) else 1.0
            selections[shot.shot_id] = chosen
            voices[shot.shot_id] = duration
            sources[chosen.asset_id] = services.store.get_path(chosen.asset_id)
    return selections, voices, sources


def _can_generate(services: Services, job: JobRecord, recipe: Recipe) -> bool:
    current = services.jobs.get_job(job.job_id)
    return BudgetPolicy().can_start_attempt(current, recipe.attempt_estimate)


def _video_attempts(services: Services, job: JobRecord, shot_id: str) -> int:
    return sum(
        1
        for attempt in services.jobs.list_attempts(job.version_id)
        if attempt.stage == "video" and attempt.target_id == shot_id
    )


def _store_fallback_clip(services: Services, job: JobRecord, task: TaskRecord) -> None:
    shot_id = _text(task.payload, "shot_id")
    _store_asset(
        services,
        job,
        data=f"fallback-clip:{shot_id}".encode(),
        media_type="video/mp4",
        origin=AssetOrigin.fallback,
        role="clip",
        lineage={
            "stage": "video",
            "shot_id": shot_id,
            "storyboard_id": _text(task.payload, "storyboard_id"),
            "hard_pass": True,
            "soft_score": 0.0,
            "fallback": True,
        },
    )


def _store_asset(
    services: Services,
    job: JobRecord,
    *,
    data: bytes,
    media_type: str,
    origin: AssetOrigin,
    role: str,
    lineage: dict[str, object],
) -> None:
    asset = services.store.put_bytes(data, media_type, origin, role=role)
    services.jobs.save_artifact(
        ArtifactWrite(
            version_id=job.version_id,
            asset_id=asset.asset_id,
            sha256=asset.sha256,
            uri=asset.uri,
            media_type=asset.media_type,
            origin=origin,
            role=role,
            lineage=lineage,
            cost="0",
        )
    )


def _timeline_has_flags(services: Services, job: JobRecord, plan: EpisodePlan) -> bool:
    artifacts = services.jobs.list_artifacts(job.version_id)
    flagged = False
    for board in plan.storyboards:
        for shot in board.shots:
            clips = [
                artifact
                for artifact in artifacts
                if artifact.lineage.get("stage") == "video"
                and artifact.lineage.get("shot_id") == shot.shot_id
            ]
            chosen = select_candidate(
                [
                    Candidate(
                        shot_id=shot.shot_id,
                        asset_id=artifact.asset_id,
                        hard_pass=_as_bool(artifact.lineage.get("hard_pass")),
                        soft_score=_as_float(artifact.lineage.get("soft_score")),
                        fallback=_as_bool(artifact.lineage.get("fallback")),
                    )
                    for artifact in clips
                ]
            )
            if chosen.fallback or chosen.low_confidence:
                flagged = True
    return flagged


def _enqueue_ready(services: Services, job: JobRecord, recipe: Recipe, plan: EpisodePlan) -> None:
    artifacts = services.jobs.list_artifacts(job.version_id)
    for board in plan.storyboards:
        for role in board.references:
            if not _has_lineage(artifacts, stage="reference", storyboard_id=board.storyboard_id, role=role):
                _enqueue(
                    services,
                    job,
                    "reference",
                    f"{board.storyboard_id}:{role}",
                    {
                        "storyboard_id": board.storyboard_id,
                        "role": role,
                        "recipe_hash": job.recipe_hash,
                    },
                )
        for shot in board.shots:
            if not _has_lineage(artifacts, stage="speech", shot_id=shot.shot_id):
                _enqueue(
                    services,
                    job,
                    "speech",
                    shot.shot_id,
                    {"shot_id": shot.shot_id, "recipe_hash": job.recipe_hash},
                )
            speech = _find_lineage(artifacts, stage="speech", shot_id=shot.shot_id)
            if speech is None or _has_lineage(artifacts, stage="video", shot_id=shot.shot_id):
                continue
            _enqueue(
                services,
                job,
                "video",
                shot.shot_id,
                {
                    "shot_id": shot.shot_id,
                    "storyboard_id": board.storyboard_id,
                    "prompt": shot.prompt,
                    "duration_seconds": str(speech["duration_seconds"]),
                    "recipe_hash": job.recipe_hash,
                },
            )
    shots = [shot.shot_id for board in plan.storyboards for shot in board.shots]
    rendered = [item for item in artifacts if item.lineage.get("stage") == "video"]
    if len(rendered) >= len(shots):
        _enqueue(
            services,
            job,
            "render",
            "timeline",
            {"recipe_hash": job.recipe_hash, "fallback": recipe.fallback},
        )


def _enqueue(
    services: Services,
    job: JobRecord,
    kind: str,
    target_id: str,
    payload: dict[str, object],
) -> None:
    services.tasks.enqueue(
        version_id=job.version_id,
        kind=kind,
        payload=payload,
        idempotency_key=stage_key(str(job.version_id), kind, target_id, payload),
    )


def _load_recipe(recipe_id: str) -> tuple[Recipe, str]:
    path = RECIPES / f"{recipe_id}.yaml"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return load_recipe(path), digest


def _job_for_task(services: Services, task: TaskRecord) -> JobRecord:
    from app.infrastructure.orm import JobVersionRow

    row = services.session.get(JobVersionRow, str(task.version_id))
    if row is None:
        raise KeyError(task.version_id)
    return services.jobs.get_version(UUID(row.job_id), row.version_number)


def _board(plan: EpisodePlan, storyboard_id: str) -> Storyboard:
    for board in plan.storyboards:
        if board.storyboard_id == storyboard_id:
            return board
    raise KeyError(storyboard_id)


def _shot(plan: EpisodePlan, shot_id: str) -> Shot:
    for board in plan.storyboards:
        for shot in board.shots:
            if shot.shot_id == shot_id:
                return shot
    raise KeyError(shot_id)


def _as_bool(value: object) -> bool:
    return value is True


def _as_float(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _text(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise TypeError(key)
    return value


def _json_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return {str(key): item for key, item in value.items()}


def _has_lineage(artifacts: list[ArtifactRecord], **expected: str) -> bool:
    return _find_lineage(artifacts, **expected) is not None


def _find_lineage(artifacts: list[ArtifactRecord], **expected: str) -> dict[str, object] | None:
    for artifact in artifacts:
        lineage = artifact.lineage
        if all(lineage.get(key) == value for key, value in expected.items()):
            return lineage
    return None
