from uuid import uuid4

from app.application.commands import SubmitJob
from app.application.dispatcher import run_once, submit_job
from app.application.policy import BudgetPolicy, RetryAction, RetryPolicy
from app.domain.models import JobStatus
from app.infrastructure.repositories import JobRecord, JobRepository


def _job(*, spent: str, cap: str | None) -> JobRecord:
    return JobRecord(
        job_id=uuid4(),
        version_id=uuid4(),
        version_number=1,
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash",
        brief="brief",
        budget_cap=cap,
        status=JobStatus.generating,
        spent=spent,
    )


def test_hard_cap_denies_another_attempt():
    policy = BudgetPolicy()
    assert policy.can_start_attempt(_job(spent="1.00", cap="1.00"), "0.01") is False
    assert policy.can_start_attempt(_job(spent="0.50", cap="1.00"), "0.25") is True


def test_retry_policy_falls_back_at_max_attempts():
    policy = RetryPolicy(max_attempts=2)
    assert policy.next_action(attempts_started=1, last_hard_pass=False) == RetryAction.retry
    assert policy.next_action(attempts_started=2, last_hard_pass=False) == RetryAction.fallback
    assert policy.next_action(attempts_started=1, last_hard_pass=True) == RetryAction.accept


def test_cap_exhaustion_delivers_without_a_new_generation(services):
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
        if run_once("worker-a", services=bundle) == 0:
            break
    assert video.submitted == []
    job = JobRepository(bundle.session).get_job(job_id)
    assert job.status == JobStatus.delivered_with_flags
    assert JobRepository(bundle.session).list_attempts(job.version_id) == []
