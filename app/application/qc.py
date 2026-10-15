from dataclasses import dataclass
from uuid import UUID

LOW_CONFIDENCE_BELOW = 0.6


class NoValidCandidate(RuntimeError):
    """Every candidate failed a hard check."""


@dataclass(frozen=True)
class Candidate:
    shot_id: str
    asset_id: UUID
    hard_pass: bool
    soft_score: float
    fallback: bool = False


@dataclass(frozen=True)
class CandidateSelection:
    shot_id: str
    asset_id: UUID
    fallback: bool
    low_confidence: bool


def select_candidate(candidates: list[Candidate]) -> CandidateSelection:
    valid = [candidate for candidate in candidates if candidate.hard_pass]
    if not valid:
        raise NoValidCandidate("no technically valid candidate")
    best = max(valid, key=lambda candidate: candidate.soft_score)
    return CandidateSelection(
        shot_id=best.shot_id,
        asset_id=best.asset_id,
        fallback=best.fallback,
        low_confidence=best.soft_score < LOW_CONFIDENCE_BELOW,
    )
