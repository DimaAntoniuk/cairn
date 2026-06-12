import json
from collections.abc import Callable, Sequence
from typing import Any

from cairn.domain import Artifact, AssembledContext, Entity, EvalIssue

from .serialize__consts import (
    ARTIFACT_FIELDS,
    DEFAULT_ARTIFACT_DETAIL_FIELDS,
    DEFAULT_ARTIFACT_LIST_FIELDS,
    DEFAULT_ENTITY_LIST_FIELDS,
    ENTITY_FIELDS,
)

# Envelope rule: every JSON body is one compact single-line object carrying
# "ok", so agents can json.loads any command output (or exec-mode stdout line).


def dumps(obj: object) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str, ensure_ascii=False)


def _project[T](
    item: T, fields: Sequence[str], getters: dict[str, Callable[[T], object]]
) -> dict[str, object]:
    return {name: getters[name](item) for name in fields}


def json_artifacts(
    artifacts: Sequence[Artifact], fields: Sequence[str] = DEFAULT_ARTIFACT_LIST_FIELDS
) -> str:
    items = [_project(a, fields, ARTIFACT_FIELDS) for a in artifacts]
    return dumps({"ok": True, "count": len(items), "items": items})


def json_artifact(
    artifact: Artifact, fields: Sequence[str] = DEFAULT_ARTIFACT_DETAIL_FIELDS
) -> str:
    return dumps({"ok": True, "artifact": _project(artifact, fields, ARTIFACT_FIELDS)})


def json_entities(
    entities: Sequence[Entity], fields: Sequence[str] = DEFAULT_ENTITY_LIST_FIELDS
) -> str:
    items = [_project(e, fields, ENTITY_FIELDS) for e in entities]
    return dumps({"ok": True, "count": len(items), "items": items})


def json_context(ctx: AssembledContext, *, intent: str) -> str:
    fragments = [
        {
            "text": f.text,
            "confidence": round(f.confidence.score, 3),
            "artifact_id": f.artifact_id,
        }
        for f in ctx.fragments
    ]
    return dumps(
        {
            "ok": True,
            "intent": intent,
            "total_tokens": ctx.total_tokens,
            "dropped": len(ctx.dropped_fragment_ids),
            "fragments": fragments,
        }
    )


def json_issues(issues: Sequence[EvalIssue]) -> str:
    items = [
        {
            "kind": i.kind.value,
            "severity": i.severity,
            "artifact_ids": i.artifact_ids,
            "description": i.description,
        }
        for i in issues
    ]
    return dumps({"ok": True, "count": len(items), "issues": items})


def json_message(ok: bool, message: str, **extra: Any) -> str:
    return dumps({"ok": ok, "message": message, **extra})


def json_error(message: str) -> str:
    return dumps({"ok": False, "error": message})


__all__ = [
    "dumps",
    "json_artifact",
    "json_artifacts",
    "json_context",
    "json_entities",
    "json_error",
    "json_issues",
    "json_message",
]
