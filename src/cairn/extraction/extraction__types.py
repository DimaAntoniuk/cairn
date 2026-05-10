from pydantic import BaseModel


class EntityItem(BaseModel):
    name: str
    entity_type: str = "generic"
    aliases: list[str] = []
    confidence: float = 0.5
    quote: str = ""


class EntitiesResponse(BaseModel):
    entities: list[EntityItem]


class RelationshipItem(BaseModel):
    source: str
    target: str
    relationship_type: str = "related_to"
    confidence: float = 0.5
    quote: str = ""


class RelationshipsResponse(BaseModel):
    relationships: list[RelationshipItem]


class ClaimItem(BaseModel):
    subject: str
    kind: str = "attribute"
    statement: str = ""
    reason: str | None = None
    confidence: float = 0.5
    quote: str = ""


class ClaimsResponse(BaseModel):
    claims: list[ClaimItem]


class TagsResponse(BaseModel):
    tags: list[str]


__all__ = [
    "ClaimItem",
    "ClaimsResponse",
    "EntitiesResponse",
    "EntityItem",
    "RelationshipItem",
    "RelationshipsResponse",
    "TagsResponse",
]
