from datetime import UTC, datetime, timedelta

import pytest

from app.application.commands import SubmitJob
from app.application.dispatcher import run_once, stage_key, submit_job
from app.application.workflow import advance_job
from app.domain.models import JobStatus
from app.infrastructure.repositories import JobRepository, TaskRepository


def test_stage_key_is_stable():
    payload = {"prompt": "hello", "shot_id": "b0-s1"}
    assert stage_key("version", "video", "b0-s1", payload) == stage_key(
        "version", "video", "b0-s1", payload
    )


def test_planning_enqueues_reference_and_speech_together(services):
    bundle, _video = services
    job_id = submit_job(
        SubmitJob(brief="Hai người gặp lại dưới mưa.", recipe_id="drama_vertical_120s_v1"),
        services=bundle,
    )
    assert JobRepository(bundle.session).get_job(job_id).status == JobStatus.queued
    assert run_once("worker-a", services=bundle) == 1
    job = JobRepository(bundle.session).get_job(job_id)
    assert job.status == JobStatus.generating
    tasks = TaskRepository(bundle.session).list_tasks(job.version_id)
    kinds = {task.kind for task in tasks}
    assert "reference" in kinds
    assert "speech" in kinds
    advance_job(job_id, services=bundle)
    again = TaskRepository(bundle.session).list_tasks(job.version_id)
    assert [task.task_id for task in again] == [task.task_id for task in tasks]


def test_interrupted_video_resumes_the_same_attempt(services):
    bundle, video = services
    job_id = submit_job(
        SubmitJob(brief="Hai người gặp lại dưới mưa.", recipe_id="drama_vertical_120s_v1"),
        services=bundle,
    )
    with pytest.raises(RuntimeError, match="worker interrupted"):
        for _ in range(400):
            run_once("worker-a", services=bundle)
        raise AssertionError("video task did not interrupt")
    assert len(video.submitted) == 1
    released = TaskRepository(bundle.session).release_expired(
        datetime.now(UTC) + timedelta(minutes=10)
    )
    assert released == 1
    for _ in range(400):
        if run_once("worker-b", services=bundle) == 0:
            break
    assert video.submitted.count(video.submitted[0]) == 1
    job = JobRepository(bundle.session).get_job(job_id)
    assert job.status in {JobStatus.delivered, JobStatus.delivered_with_flags}
