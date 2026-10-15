from app.application.commands import SubmitJob
from app.application.dispatcher import run_once, submit_job
from app.domain.models import JobStatus
from app.infrastructure.repositories import JobRepository


def test_submit_leaves_the_job_queued_until_the_worker_runs(services):
    bundle, _video = services
    job_id = submit_job(
        SubmitJob(brief="Một buổi sáng ở quán cà phê.", recipe_id="drama_vertical_120s_v1"),
        services=bundle,
    )
    assert JobRepository(bundle.session).get_job(job_id).status == JobStatus.queued
    assert run_once("worker-a", services=bundle) == 1
    assert JobRepository(bundle.session).get_job(job_id).status == JobStatus.generating
