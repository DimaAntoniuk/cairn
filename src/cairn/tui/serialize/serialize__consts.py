from collections.abc import Callable

from cairn.domain import Artifact, Entity

# Field-getter maps: the keys double as the legal ``--fields`` choices, so the
# parser, /help, and the JSON projection can never drift apart.
ARTIFACT_FIELDS: dict[str, Callable[[Artifact], object]] = {
    "id": lambda a: a.artifact_id,
    "type": lambda a: a.artifact_type.value,
    "title": lambda a: a.title,
    "summary": lambda a: a.summary,
    "confidence": lambda a: round(a.confidence.score, 3),
    "version": lambda a: a.version,
    "entities": lambda a: a.entity_refs,
    "sources": lambda a: [f"{r.system.value}:{r.external_id}" for r in a.source_refs],
    "content": lambda a: a.content,
    "created_at": lambda a: a.created_at.isoformat(),
    "updated_at": lambda a: a.updated_at.isoformat(),
}

ENTITY_FIELDS: dict[str, Callable[[Entity], object]] = {
    "id": lambda e: e.id,
    "type": lambda e: e.entity_type.value,
    "name": lambda e: e.name,
    "aliases": lambda e: e.aliases,
    "attributes": lambda e: e.attributes,
    "confidence": lambda e: round(e.confidence.score, 3),
}

# Token-lean defaults: list views project identifiers only; the detail view
# adds everything except sources (opt in via --fields sources).
DEFAULT_ARTIFACT_LIST_FIELDS = ("id", "type", "title", "confidence")
DEFAULT_ARTIFACT_DETAIL_FIELDS = (
    "id",
    "type",
    "title",
    "summary",
    "confidence",
    "version",
    "entities",
    "content",
)
DEFAULT_ENTITY_LIST_FIELDS = ("id", "type", "name")

__all__ = [
    "ARTIFACT_FIELDS",
    "DEFAULT_ARTIFACT_DETAIL_FIELDS",
    "DEFAULT_ARTIFACT_LIST_FIELDS",
    "DEFAULT_ENTITY_LIST_FIELDS",
    "ENTITY_FIELDS",
]
