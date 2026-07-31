import fnmatch
from dataclasses import dataclass, field
from typing import Any

TOOL_BASE_SCORE: dict[str, int] = {
    "repo_session_start": 25,
    "repo_session_end": 5,
    "repo_list_files": 5,
    "repo_read_file": 8,
    "repo_search_code": 10,
    "repo_git_status": 5,
    "repo_git_diff": 12,
    "repo_prepare_patch": 40,
    "repo_approve_patch": 60,
    "repo_apply_patch": 80,
    "repo_run_test": 65,
}


@dataclass
class RiskAssessment:
    score: int
    level: str
    factors: list[str] = field(default_factory=list)

    def to_audit_fields(self) -> dict[str, Any]:
        return {"risk_score": self.score, "risk": self.level, "risk_factors": self.factors}


class RiskScorer:
    def __init__(self, rules: dict[str, Any]) -> None:
        risk = rules.get("risk", {})
        self.block_threshold = int(risk.get("block_threshold", 90))
        self.high_threshold = int(risk.get("high_threshold", 70))
        self.sensitive_paths = risk.get(
            "sensitive_paths",
            [".github/workflows/**", "deploy/**", "terraform/**", ".env*"],
        )

    def _level(self, score: int) -> str:
        if score >= self.block_threshold:
            return "critical"
        if score >= self.high_threshold:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _sensitive_targets(self, targets: list[str]) -> list[str]:
        hits: list[str] = []
        for target in targets:
            normalized = target.replace("\\", "/")
            for pattern in self.sensitive_paths:
                if fnmatch.fnmatch(normalized, pattern):
                    hits.append(target)
                    break
        return hits

    def assess(
        self,
        tool: str,
        *,
        targets: list[str] | None = None,
        patch_bytes: int = 0,
        branch: str = "",
        user: str = "",
    ) -> RiskAssessment:
        score = TOOL_BASE_SCORE.get(tool, 15)
        factors: list[str] = [f"tool:{tool}"]

        if targets:
            if len(targets) > 5:
                score += 10
                factors.append("many_targets")
            sensitive = self._sensitive_targets(targets)
            if sensitive:
                score += 20 * min(len(sensitive), 3)
                factors.append(f"sensitive_paths:{','.join(sensitive[:3])}")

        if patch_bytes > 100_000:
            score += 15
            factors.append("large_patch")
        elif patch_bytes > 50_000:
            score += 8
            factors.append("medium_patch")

        if branch and not branch.startswith("agent/"):
            score += 50
            factors.append(f"non_agent_branch:{branch}")

        if user == "admin":
            score = max(0, score - 5)

        score = min(score, 100)
        return RiskAssessment(score=score, level=self._level(score), factors=factors)

    def require_acceptable(self, assessment: RiskAssessment) -> None:
        if assessment.score >= self.block_threshold:
            raise PermissionError(
                f"operation blocked by risk score {assessment.score} ({', '.join(assessment.factors)})"
            )
