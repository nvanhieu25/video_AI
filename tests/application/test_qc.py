from uuid import uuid4

import pytest

from app.application.qc import Candidate, NoValidCandidate, select_candidate


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
