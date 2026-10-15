from datetime import UTC, datetime

from app.application.workflow import Services, execute_task, stage_key, submit_job

__all__ = ["Services", "execute_task", "run_once", "stage_key", "submit_job"]


def run_once(worker_id: str, *, services: Services) -> int:
    task = services.tasks.claim(worker_id, datetime.now(UTC))
    if task is None:
        return 0
    services.session.commit()
    try:
        execute_task(services, task)
        services.tasks.complete(task.task_id)
        services.session.commit()
    except Exception:
        services.session.rollback()
        raise
    return 1
