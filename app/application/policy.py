from decimal import Decimal
from enum import StrEnum

from app.infrastructure.repositories import JobRecord


class RetryAction(StrEnum):
    retry = "retry"
    fallback = "fallback"
    accept = "accept"


class BudgetPolicy:
    def can_start_attempt(self, job: JobRecord, estimate: str) -> bool:
        if job.budget_cap is None:
            return True
        return Decimal(job.spent) + Decimal(estimate) <= Decimal(job.budget_cap)


class RetryPolicy:
    def __init__(self, max_attempts: int) -> None:
        self.max_attempts = max_attempts

    def next_action(self, *, attempts_started: int, last_hard_pass: bool) -> RetryAction:
        if last_hard_pass:
            return RetryAction.accept
        if attempts_started >= self.max_attempts:
            return RetryAction.fallback
        return RetryAction.retry
