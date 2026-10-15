from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import AssetOrigin, JobStatus
from app.infrastructure.database import create_db_engine, create_schema, session_factory
from app.infrastructure.orm import JobVersionRow
from app.infrastructure.repositories import (
    ArtifactWrite,
    AttemptWrite,
    JobRepository,
    TaskRepository,
)


@pytest.fixture
def session() -> Session:
    engine = create_db_engine("sqlite://")
    create_schema(engine)
    factory = session_factory(engine)
    with factory() as db:
        yield db


def test_postgres_url_uses_the_psycopg_driver():
    engine = create_db_engine("postgresql+psycopg://postgres:postgres@localhost/richesse")
    assert engine.url.drivername == "postgresql+psycopg"


def test_create_job_persists_an_immutable_version(session: Session):
    jobs = JobRepository(session)
    created = jobs.create_job(
        brief="A rainy reunion.",
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash-v1",
        budget_cap="5.00",
    )
    session.commit()
    loaded = jobs.get_job(created.job_id)
    assert loaded.version_number == 1
    assert loaded.status == JobStatus.queued
    assert loaded.recipe_hash == "hash-v1"
    events = jobs.list_events(created.version_id)
    assert events[0].kind == "job.created"


def test_artifact_persists_lineage_and_cost(session: Session):
    jobs = JobRepository(session)
    created = jobs.create_job(
        brief="A rainy reunion.",
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash-v1",
        budget_cap="5.00",
    )
    asset_id = uuid4()
    jobs.save_artifact(
        ArtifactWrite(
            version_id=created.version_id,
            asset_id=asset_id,
            sha256="abc123",
            uri="file://media/abc123",
            media_type="image/png",
            origin=AssetOrigin.generated,
            role="character",
            lineage={
                "source_asset_ids": [],
                "prompt_version": "planner-v1",
                "provider": "fake",
                "model": "fake-image",
                "parameters": {"seed": 1},
            },
            cost="0.10",
        )
    )
    session.commit()
    stored = jobs.get_artifact(asset_id)
    assert stored.cost == "0.10"
    assert stored.lineage["prompt_version"] == "planner-v1"
    assert stored.lineage["provider"] == "fake"


def test_attempt_stores_credential_alias_only(session: Session):
    with pytest.raises(ValidationError):
        AttemptWrite(
            version_id=uuid4(),
            idempotency_key="job:plan",
            stage="plan",
            target_id="episode",
            provider_alias="seedance-default",
            api_key="sk-live-should-not-persist",
        )
    jobs = JobRepository(session)
    created = jobs.create_job(
        brief="A rainy reunion.",
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash-v1",
        budget_cap="5.00",
    )
    jobs.save_attempt(
        AttemptWrite(
            version_id=created.version_id,
            idempotency_key=f"{created.version_id}:video:shot-1",
            stage="video",
            target_id="shot-1",
            provider_alias="seedance-default",
            external_task_id="ext-1",
            cost="0.20",
        )
    )
    session.commit()
    stored = jobs.get_attempt_by_key(f"{created.version_id}:video:shot-1")
    assert stored is not None
    assert stored.provider_alias == "seedance-default"
    assert stored.external_task_id == "ext-1"
    assert stored.cost == "0.20"
    assert "api_key" not in stored.__dict__


def test_claim_hands_each_task_to_one_worker(session: Session):
    jobs = JobRepository(session)
    tasks = TaskRepository(session)
    created = jobs.create_job(
        brief="A rainy reunion.",
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash-v1",
        budget_cap="5.00",
    )
    task_id = tasks.enqueue(
        version_id=created.version_id,
        kind="plan",
        payload={"job_id": str(created.job_id)},
        idempotency_key=f"{created.version_id}:plan",
    )
    now = datetime(2026, 10, 16, tzinfo=UTC)
    first = tasks.claim("worker-a", now)
    second = tasks.claim("worker-b", now)
    assert first is not None
    assert first.task_id == task_id
    assert second is None
    tasks.complete(task_id)
    assert tasks.claim("worker-c", now) is None


def test_release_expired_lease_makes_the_task_claimable(session: Session):
    jobs = JobRepository(session)
    tasks = TaskRepository(session)
    created = jobs.create_job(
        brief="A rainy reunion.",
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash-v1",
        budget_cap="5.00",
    )
    tasks.enqueue(
        version_id=created.version_id,
        kind="plan",
        payload={},
        idempotency_key=f"{created.version_id}:plan",
    )
    start = datetime(2026, 10, 16, tzinfo=UTC)
    claimed = tasks.claim("worker-a", start)
    assert claimed is not None
    released = tasks.release_expired(start + timedelta(minutes=10))
    assert released == 1
    again = tasks.claim("worker-b", start + timedelta(minutes=10))
    assert again is not None
    assert again.task_id == claimed.task_id


def test_changed_recipe_creates_a_new_version(session: Session):
    jobs = JobRepository(session)
    created = jobs.create_job(
        brief="A rainy reunion.",
        recipe_id="drama_vertical_120s_v1",
        recipe_hash="hash-v1",
        budget_cap="5.00",
    )
    revised = jobs.add_version(
        job_id=created.job_id,
        brief="A rainy reunion.",
        recipe_id="five_ref_v1",
        recipe_hash="hash-v2",
        budget_cap="4.00",
    )
    session.commit()
    original = session.get(JobVersionRow, str(created.version_id))
    assert original is not None
    assert original.recipe_id == "drama_vertical_120s_v1"
    assert original.recipe_hash == "hash-v1"
    assert revised.version_number == 2
    assert jobs.get_job(created.job_id).recipe_id == "five_ref_v1"
    assert session.scalar(select(JobVersionRow).where(JobVersionRow.version_number == 1)).recipe_id == (
        "drama_vertical_120s_v1"
    )
