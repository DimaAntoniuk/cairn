from typing import Any

from cairn.domain import Confidence, EntityType, RelationshipType


def _normalize_entity_type(raw: str) -> EntityType:
    try:
        return EntityType(raw.lower())
    except ValueError:
        return EntityType.GENERIC


def _normalize_relationship_type(raw: str) -> RelationshipType:
    try:
        return RelationshipType(raw.lower())
    except ValueError:
        return RelationshipType.RELATED_TO


def _confidence_from(payload: dict[str, Any]) -> Confidence:
    score = float(payload.get("confidence", 0.7))
    score = max(0.0, min(1.0, score))
    rationale = payload.get("confidence_rationale")
    return Confidence(score=score, rationale=rationale)
