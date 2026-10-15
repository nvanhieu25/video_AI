from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.domain.models import AssetOrigin, JobStatus, TaskStatus
from app.infrastructure.orm import ArtifactRow, AttemptRow, EventRow, JobRow, JobVersionRow, TaskRow

LEASE = timedelta(minutes=5)


class ArtifactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    asset_id: UUID
    sha256: str
    uri: str
    media_type: str
    origin: AssetOrigin
    role: str | None = None
    lineage: dict[str, object]
    cost: str


class AttemptWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    idempotency_key: str
    stage: str
    target_id: str
    provider_alias: str
    external_task_id: str | None = None
    status: str = "submitted"
    cost: str = "0"


@dataclass(frozen=True)
class JobRecord:
    job_id: UUID
    version_id: UUID
    version_number: int
    recipe_id: str
    recipe_hash: str
    brief: str
    budget_cap: str | None
    status: JobStatus
    spent: str


@dataclass(frozen=True)
class EventRecord:
    event_id: UUID
    kind: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ArtifactRecord:
    asset_id: UUID
    sha256: str
    uri: str
    media_type: str
    origin: AssetOrigin
    role: str | None
    lineage: dict[str, object]
    cost: str


@dataclass(frozen=True)
class AttemptRecord:
    attempt_id: UUID
    idempotency_key: str
    stage: str
    target_id: str
    provider_alias: str
    external_task_id: str | None
    status: str
    cost: str


@dataclass(frozen=True)
class TaskRecord:
    task_id: UUID
    version_id: UUID
    kind: str
    payload: dict[str, object]
    idempotency_key: str
    status: TaskStatus


def _now() -> datetime:
    return datetime.now(UTC)


def _job_record(row: JobVersionRow) -> JobRecord:
    return JobRecord(
        job_id=UUID(row.job_id),
        version_id=UUID(row.id),
        version_number=row.version_number,
        recipe_id=row.recipe_id,
        recipe_hash=row.recipe_hash,
        brief=row.brief,
        budget_cap=row.budget_cap,
        status=JobStatus(row.status),
        spent=row.spent,
    )


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        brief: str,
        recipe_id: str,
        recipe_hash: str,
        budget_cap: str | None,
    ) -> JobRecord:
        now = _now()
        job_id = uuid4()
        version_id = uuid4()
        self.session.add(JobRow(id=str(job_id), created_at=now))
        self.session.add(
            JobVersionRow(
                id=str(version_id),
                job_id=str(job_id),
                version_number=1,
                recipe_id=recipe_id,
                recipe_hash=recipe_hash,
                brief=brief,
                budget_cap=budget_cap,
                spent="0",
                status=JobStatus.queued.value,
                created_at=now,
            )
        )
        self.record_event(version_id, "job.created", {"status": JobStatus.queued.value})
        self.session.flush()
        return self.get_version(job_id, 1)

    def add_version(
        self,
        *,
        job_id: UUID,
        brief: str,
        recipe_id: str,
        recipe_hash: str,
        budget_cap: str | None,
    ) -> JobRecord:
        current = self.get_job(job_id)
        now = _now()
        version_id = uuid4()
        number = current.version_number + 1
        self.session.add(
            JobVersionRow(
                id=str(version_id),
                job_id=str(job_id),
                version_number=number,
                recipe_id=recipe_id,
                recipe_hash=recipe_hash,
                brief=brief,
                budget_cap=budget_cap,
                spent="0",
                status=JobStatus.queued.value,
                created_at=now,
            )
        )
        self.record_event(version_id, "job.version_created", {"recipe_id": recipe_id})
        self.session.flush()
        return self.get_version(job_id, number)

    def get_job(self, job_id: UUID) -> JobRecord:
        row = self.session.scalar(
            select(JobVersionRow)
            .where(JobVersionRow.job_id == str(job_id))
            .order_by(JobVersionRow.version_number.desc())
            .limit(1)
        )
        if row is None:
            raise KeyError(job_id)
        return _job_record(row)

    def get_version(self, job_id: UUID, number: int) -> JobRecord:
        row = self.session.scalar(
            select(JobVersionRow).where(
                JobVersionRow.job_id == str(job_id),
                JobVersionRow.version_number == number,
            )
        )
        if row is None:
            raise KeyError((job_id, number))
        return _job_record(row)

    def set_status(self, version_id: UUID, status: JobStatus) -> None:
        self._version_row(version_id).status = status.value
        self.session.flush()

    def save_plan(self, version_id: UUID, plan: dict[str, object]) -> None:
        self._version_row(version_id).plan = plan
        self.session.flush()

    def get_plan(self, version_id: UUID) -> dict[str, object] | None:
        plan = self._version_row(version_id).plan
        if plan is None:
            return None
        return dict(plan)

    def add_spend(self, version_id: UUID, amount: str) -> str:
        row = self._version_row(version_id)
        row.spent = str(Decimal(row.spent) + Decimal(amount))
        self.session.flush()
        return row.spent

    def _version_row(self, version_id: UUID) -> JobVersionRow:
        row = self.session.get(JobVersionRow, str(version_id))
        if row is None:
            raise KeyError(version_id)
        return row

    def record_event(self, version_id: UUID, kind: str, payload: dict[str, object]) -> UUID:
        event_id = uuid4()
        self.session.add(
            EventRow(
                id=str(event_id),
                version_id=str(version_id),
                kind=kind,
                payload=payload,
                created_at=_now(),
            )
        )
        self.session.flush()
        return event_id

    def list_events(self, version_id: UUID) -> list[EventRecord]:
        rows = self.session.scalars(
            select(EventRow)
            .where(EventRow.version_id == str(version_id))
            .order_by(EventRow.created_at)
        ).all()
        return [
            EventRecord(event_id=UUID(row.id), kind=row.kind, payload=dict(row.payload))
            for row in rows
        ]

    def list_artifacts(self, version_id: UUID) -> list[ArtifactRecord]:
        rows = self.session.scalars(
            select(ArtifactRow)
            .where(ArtifactRow.version_id == str(version_id))
            .order_by(ArtifactRow.created_at)
        ).all()
        return [_artifact_record(row) for row in rows]

    def save_artifact(self, artifact: ArtifactWrite) -> ArtifactRecord:
        existing = self.session.scalar(
            select(ArtifactRow).where(ArtifactRow.asset_id == str(artifact.asset_id))
        )
        if existing is not None:
            return _artifact_record(existing)
        self.session.add(
            ArtifactRow(
                id=str(uuid4()),
                version_id=str(artifact.version_id),
                asset_id=str(artifact.asset_id),
                sha256=artifact.sha256,
                uri=artifact.uri,
                media_type=artifact.media_type,
                origin=artifact.origin.value,
                role=artifact.role,
                lineage=artifact.lineage,
                cost=artifact.cost,
                created_at=_now(),
            )
        )
        self.session.flush()
        return self.get_artifact(artifact.asset_id)

    def get_artifact(self, asset_id: UUID) -> ArtifactRecord:
        row = self.session.scalar(select(ArtifactRow).where(ArtifactRow.asset_id == str(asset_id)))
        if row is None:
            raise KeyError(asset_id)
        return _artifact_record(row)

    def save_attempt(self, attempt: AttemptWrite) -> AttemptRecord:
        attempt_id = uuid4()
        self.session.add(
            AttemptRow(
                id=str(attempt_id),
                version_id=str(attempt.version_id),
                idempotency_key=attempt.idempotency_key,
                stage=attempt.stage,
                target_id=attempt.target_id,
                provider_alias=attempt.provider_alias,
                external_task_id=attempt.external_task_id,
                status=attempt.status,
                cost=attempt.cost,
                created_at=_now(),
            )
        )
        self.session.flush()
        stored = self.get_attempt_by_key(attempt.idempotency_key)
        if stored is None:
            raise KeyError(attempt.idempotency_key)
        return stored

    def update_attempt(self, idempotency_key: str, *, status: str, cost: str | None = None) -> None:
        row = self.session.scalar(
            select(AttemptRow).where(AttemptRow.idempotency_key == idempotency_key)
        )
        if row is None:
            raise KeyError(idempotency_key)
        row.status = status
        if cost is not None:
            row.cost = cost
        self.session.flush()

    def list_attempts(self, version_id: UUID) -> list[AttemptRecord]:
        rows = self.session.scalars(
            select(AttemptRow).where(AttemptRow.version_id == str(version_id))
        ).all()
        return [
            AttemptRecord(
                attempt_id=UUID(row.id),
                idempotency_key=row.idempotency_key,
                stage=row.stage,
                target_id=row.target_id,
                provider_alias=row.provider_alias,
                external_task_id=row.external_task_id,
                status=row.status,
                cost=row.cost,
            )
            for row in rows
        ]

    def get_attempt_by_key(self, idempotency_key: str) -> AttemptRecord | None:
        row = self.session.scalar(
            select(AttemptRow).where(AttemptRow.idempotency_key == idempotency_key)
        )
        if row is None:
            return None
        return AttemptRecord(
            attempt_id=UUID(row.id),
            idempotency_key=row.idempotency_key,
            stage=row.stage,
            target_id=row.target_id,
            provider_alias=row.provider_alias,
            external_task_id=row.external_task_id,
            status=row.status,
            cost=row.cost,
        )


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(
        self,
        *,
        version_id: UUID,
        kind: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> UUID:
        existing = self.session.scalar(
            select(TaskRow).where(TaskRow.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return UUID(existing.id)
        task_id = uuid4()
        self.session.add(
            TaskRow(
                id=str(task_id),
                version_id=str(version_id),
                kind=kind,
                payload=payload,
                idempotency_key=idempotency_key,
                status=TaskStatus.pending.value,
                worker_id=None,
                lease_expires_at=None,
                created_at=_now(),
            )
        )
        self.session.flush()
        return task_id

    def list_tasks(self, version_id: UUID) -> list[TaskRecord]:
        rows = self.session.scalars(
            select(TaskRow)
            .where(TaskRow.version_id == str(version_id))
            .order_by(TaskRow.created_at, TaskRow.id)
        ).all()
        return [_task_record(row) for row in rows]

    def claim(self, worker_id: str, now: datetime) -> TaskRecord | None:
        candidate = self.session.scalar(
            select(TaskRow)
            .where(TaskRow.status == TaskStatus.pending.value)
            .order_by(TaskRow.created_at)
            .limit(1)
        )
        if candidate is None:
            return None
        result = self.session.execute(
            update(TaskRow)
            .where(TaskRow.id == candidate.id, TaskRow.status == TaskStatus.pending.value)
            .values(
                status=TaskStatus.leased.value,
                worker_id=worker_id,
                lease_expires_at=now + LEASE,
            )
        )
        if not isinstance(result, CursorResult) or result.rowcount != 1:
            return None
        self.session.flush()
        self.session.refresh(candidate)
        return _task_record(candidate)

    def complete(self, task_id: UUID) -> None:
        self.session.execute(
            update(TaskRow)
            .where(TaskRow.id == str(task_id))
            .values(status=TaskStatus.complete.value, lease_expires_at=None, worker_id=None)
        )
        self.session.flush()

    def release_expired(self, now: datetime) -> int:
        result = self.session.execute(
            update(TaskRow)
            .where(
                TaskRow.status == TaskStatus.leased.value,
                TaskRow.lease_expires_at.is_not(None),
                TaskRow.lease_expires_at < now,
            )
            .values(status=TaskStatus.pending.value, worker_id=None, lease_expires_at=None)
        )
        self.session.flush()
        if not isinstance(result, CursorResult):
            return 0
        return int(result.rowcount or 0)


def _artifact_record(row: ArtifactRow) -> ArtifactRecord:
    return ArtifactRecord(
        asset_id=UUID(row.asset_id),
        sha256=row.sha256,
        uri=row.uri,
        media_type=row.media_type,
        origin=AssetOrigin(row.origin),
        role=row.role,
        lineage=dict(row.lineage),
        cost=row.cost,
    )


def _task_record(row: TaskRow) -> TaskRecord:
    return TaskRecord(
        task_id=UUID(row.id),
        version_id=UUID(row.version_id),
        kind=row.kind,
        payload=dict(row.payload),
        idempotency_key=row.idempotency_key,
        status=TaskStatus(row.status),
    )
