from datetime import datetime

from pydantic import BaseModel, Field

from .entity__types import Confidence
from .shared__utils import _new_id, _utcnow
from .source__types import SourceRef


class ContextFragment(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("frag"))
    text: str
    token_estimate: int
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: Confidence = Field(default=Confidence(score=1.0))
    source_refs: list[SourceRef] = Field(default_factory=list)
    artifact_id: str | None = None
    entity_ids: list[str] = Field(default_factory=list)


class AssembledContext(BaseModel):
    fragments: list[ContextFragment]
    total_tokens: int
    dropped_fragment_ids: list[str] = Field(default_factory=list)
    assembled_at: datetime = Field(default_factory=_utcnow)

    def render(self, separator: str = "\n\n---\n\n") -> str:
        return separator.join(f.text for f in self.fragments)


__all__ = [
    "AssembledContext",
    "ContextFragment",
]
