from pydantic import BaseModel


class ArtifactContent(BaseModel):
    current_state: str = ""
    decisions: list[str] = []
    constraints: list[str] = []
    risks: list[str] = []
    open_questions: list[str] = []


class ConflictItem(BaseModel):
    description: str
    fact_ids: list[str] = []


class CompiledArtifactResponse(BaseModel):
    title: str
    summary: str
    content: ArtifactContent
    confidence: float = 0.7
    conflicts: list[ConflictItem] = []


__all__ = [
    "ArtifactContent",
    "CompiledArtifactResponse",
    "ConflictItem",
]
