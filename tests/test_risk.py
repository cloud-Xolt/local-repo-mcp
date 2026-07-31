import pytest

from security.risk import RiskScorer


@pytest.fixture
def scorer() -> RiskScorer:
    rules = {
        "risk": {
            "block_threshold": 90,
            "high_threshold": 70,
            "sensitive_paths": [".github/workflows/**", "deploy/**"],
        }
    }
    return RiskScorer(rules)


def test_read_is_low_risk(scorer: RiskScorer) -> None:
    assessment = scorer.assess("repo_read_file")
    assert assessment.level == "low"
    assert assessment.score < 40


def test_apply_patch_is_high_risk(scorer: RiskScorer) -> None:
    assessment = scorer.assess("repo_apply_patch", targets=["src/a.py"])
    assert assessment.score >= 70


def test_sensitive_targets_increase_score(scorer: RiskScorer) -> None:
    base = scorer.assess("repo_prepare_patch", targets=["src/a.py"]).score
    sensitive = scorer.assess(
        "repo_prepare_patch",
        targets=[".github/workflows/ci.yml"],
    ).score
    assert sensitive > base


def test_non_agent_branch_blocked(scorer: RiskScorer) -> None:
    assessment = scorer.assess("repo_apply_patch", branch="master")
    with pytest.raises(PermissionError):
        scorer.require_acceptable(assessment)


def test_block_threshold(scorer: RiskScorer) -> None:
    assessment = scorer.assess(
        "repo_apply_patch",
        targets=[".github/workflows/ci.yml", "deploy/x.yml"],
        patch_bytes=120_000,
        branch="master",
    )
    assert assessment.score >= 90
    with pytest.raises(PermissionError):
        scorer.require_acceptable(assessment)
