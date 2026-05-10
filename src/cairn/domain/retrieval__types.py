from dataclasses import dataclass, field

from .artifact__types import Artifact, ArtifactType


@dataclass(frozen=True)
class Query:
    intent: str
    entity_hints: tuple[str, ...] = ()
    artifact_types: tuple[ArtifactType, ...] = ()
    permissions: tuple[str, ...] = ()
    min_confidence: float = 0.0
    max_age_days: int | None = None
    top_k: int = 10
    graph_depth: int = 1


@dataclass
class RetrievalResult:
    artifact: Artifact
    score: float
    reasons: list[str] = field(default_factory=list)


__all__ = ["Query", "RetrievalResult"]
