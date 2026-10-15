from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobVersionRow(Base):
    __tablename__ = "job_versions"
    __table_args__ = (UniqueConstraint("job_id", "version_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    recipe_id: Mapped[str] = mapped_column(String(120))
    recipe_hash: Mapped[str] = mapped_column(String(128))
    brief: Mapped[str] = mapped_column(Text)
    budget_cap: Mapped[str | None] = mapped_column(String(32), nullable=True)
    spent: Mapped[str] = mapped_column(String(32), default="0")
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("job_versions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("job_versions.id"), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    uri: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(80))
    origin: Mapped[str] = mapped_column(String(40))
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lineage: Mapped[dict[str, object]] = mapped_column(JSON)
    cost: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AttemptRow(Base):
    __tablename__ = "generation_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("job_versions.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    stage: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(80))
    provider_alias: Mapped[str] = mapped_column(String(80))
    external_task_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    cost: Mapped[str] = mapped_column(String(32), default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskRow(Base):
    __tablename__ = "durable_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("job_versions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
