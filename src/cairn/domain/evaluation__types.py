from dataclasses import dataclass, field
from enum import StrEnum


class IssueKind(StrEnum):
    STALE = "stale"
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTION = "contradiction"
    UNREFERENCED = "unreferenced"


@dataclass
class EvalIssue:
    kind: IssueKind
    artifact_ids: list[str]
    description: str
    severity: float
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = ["EvalIssue", "IssueKind"]
