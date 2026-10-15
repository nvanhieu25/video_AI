from uuid import uuid4

import pytest

from app.application.commands import SubmitJob
from app.application.dispatcher import run_once, submit_job
from app.application.qc import Candidate, NoValidCandidate, select_candidate
from app.domain.models import AssetRef, JobStatus
from app.domain.ports import Evaluation
from app.infrastructure.repositories import JobRepository


class _RejectClips:
    def evaluate(self, asset: AssetRef, prompt: str) -> Evaluation:
        return Evaluation(hard_pass=False, soft_score=0.2, reasons=["malformed"])


def test_invalid_candidate_cannot_win_and_low_score_is_flagged():
    weak = uuid4()
    strong = uuid4()
    invalid = uuid4()
    chosen = select_candidate(
        [
            Candidate(shot_id="b0-s1", asset_id=invalid, hard_pass=False, soft_score=0.99),
            Candidate(shot_id="b0-s1", asset_id=weak, hard_pass=True, soft_score=0.2),
            Candidate(shot_id="b0-s1", asset_id=strong, hard_pass=True, soft_score=0.4, fallback=True),
        ]
    )
    assert chosen.asset_id == strong
    assert chosen.low_confidence is True
    assert chosen.fallback is True


def test_high_score_is_not_flagged():
    asset_id = uuid4()
    chosen = select_candidate(
        [Candidate(shot_id="b0-s1", asset_id=asset_id, hard_pass=True, soft_score=0.91)]
    )
    assert chosen.asset_id == asset_id
    assert chosen.low_confidence is False
    assert chosen.fallback is False


def test_no_valid_candidate_is_rejected():
    with pytest.raises(NoValidCandidate):
        select_candidate(
            [Candidate(shot_id="b0-s1", asset_id=uuid4(), hard_pass=False, soft_score=0.99)]
        )


def test_rejected_clip_does_not_enter_the_timeline(services):
    bundle, video = services
    video.interrupt = False
    bundle.evaluator = _RejectClips()
    job_id = submit_job(
        SubmitJob(brief="Hai người gặp lại dưới mưa.", recipe_id="drama_vertical_120s_v1"),
        services=bundle,
    )
    for _ in range(400):
        if run_once("worker-a", services=bundle) == 0:
            break
    jobs = JobRepository(bundle.session)
    job = jobs.get_job(job_id)
    artifacts = jobs.list_artifacts(job.version_id)
    failed = [
        artifact
        for artifact in artifacts
        if artifact.lineage.get("stage") == "video" and artifact.lineage.get("hard_pass") is False
    ]
    manifest = next(artifact for artifact in artifacts if artifact.lineage.get("kind") == "timeline")
    body = bundle.store.get_path(manifest.asset_id).read_text(encoding="utf-8")
    assert job.status == JobStatus.delivered_with_flags
    assert failed
    assert all(str(artifact.asset_id) not in body for artifact in failed)
    assert len(video.submitted) == 20
