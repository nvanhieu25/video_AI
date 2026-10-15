from app.application.commands import SubmitJob
from app.application.dispatcher import run_once, submit_job
from app.domain.models import JobStatus
from app.infrastructure.repositories import JobRepository
from app.rendering.ffmpeg import MediaInspector


def test_fake_job_delivers_playable_outputs(services):
    bundle, video = services
    video.interrupt = False
    job_id = submit_job(
        SubmitJob(
            brief="Hai người gặp lại dưới mưa.",
            recipe_id="drama_vertical_120s_v1",
            budget_cap="0",
        ),
        services=bundle,
    )
    for _ in range(400):
        if run_once("worker-e2e", services=bundle) == 0:
            break
    jobs = JobRepository(bundle.session)
    job = jobs.get_job(job_id)
    assert job.status == JobStatus.delivered_with_flags
    artifacts = jobs.list_artifacts(job.version_id)
    kinds = {artifact.lineage.get("kind") for artifact in artifacts}
    assert {"mp4", "srt", "timeline"} <= kinds
    final = next(artifact for artifact in artifacts if artifact.lineage.get("kind") == "mp4")
    metadata = MediaInspector().validate(
        bundle.store.get_path(final.asset_id),
        required_duration=10,
        aspect_ratio="9:16",
    )
    assert metadata.width == 720
    events = jobs.list_events(job.version_id)
    delivered = next(event for event in events if event.kind == "job.delivered")
    assert "cost" in delivered.payload
    assert delivered.payload["flags"] is True
