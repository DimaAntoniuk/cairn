import json

from cairn.domain import (
    Artifact,
    ArtifactType,
    AssembledContext,
    Confidence,
    ContextFragment,
    Entity,
    EntityType,
    EvalIssue,
    IssueKind,
    SourceRef,
    SourceSystem,
)
from cairn.tui.serialize import (
    DEFAULT_ARTIFACT_LIST_FIELDS,
    json_artifact,
    json_artifacts,
    json_context,
    json_entities,
    json_error,
    json_issues,
    json_message,
)


def _artifact() -> Artifact:
    return Artifact(
        artifact_type=ArtifactType.CAMPAIGN_STATE,
        title="Germany state",
        summary="paused pending legal",
        content={"status": "paused"},
        source_refs=[SourceRef(system=SourceSystem.MANUAL, external_id="demo")],
        confidence=Confidence(score=0.824999),
    )


def test_json_artifacts_is_compact_and_single_line() -> None:
    body = json_artifacts([_artifact()])
    assert "\n" not in body
    assert ": " not in body  # compact separators
    payload = json.loads(body)
    assert payload["ok"] is True
    assert payload["count"] == 1


def test_json_artifacts_projects_default_list_fields() -> None:
    item = json.loads(json_artifacts([_artifact()]))["items"][0]
    assert set(item) == set(DEFAULT_ARTIFACT_LIST_FIELDS)
    assert item["confidence"] == 0.825  # rounded


def test_json_artifact_honours_requested_fields() -> None:
    body = json_artifact(_artifact(), fields=("title", "sources"))
    payload = json.loads(body)["artifact"]
    assert set(payload) == {"title", "sources"}
    assert payload["sources"] == ["manual:demo"]


def test_json_entities_projects_fields() -> None:
    entity = Entity(entity_type=EntityType.REGION, name="Germany", aliases=["DE"])
    payload = json.loads(json_entities([entity], fields=("name", "aliases")))
    assert payload["items"] == [{"name": "Germany", "aliases": ["DE"]}]


def test_json_context_reports_budget_outcome() -> None:
    ctx = AssembledContext(
        fragments=[ContextFragment(text="Germany is paused", token_estimate=4)],
        total_tokens=4,
        dropped_fragment_ids=["frag_x"],
    )
    payload = json.loads(json_context(ctx, intent="state?"))
    assert payload["intent"] == "state?"
    assert payload["total_tokens"] == 4
    assert payload["dropped"] == 1
    assert payload["fragments"][0]["text"] == "Germany is paused"


def test_json_issues_serialises_dataclass_fields() -> None:
    issue = EvalIssue(
        kind=IssueKind.STALE,
        artifact_ids=["art_1"],
        description="older than 90 days",
        severity=0.8,
    )
    payload = json.loads(json_issues([issue]))
    assert payload["issues"] == [
        {
            "kind": "stale",
            "severity": 0.8,
            "artifact_ids": ["art_1"],
            "description": "older than 90 days",
        }
    ]


def test_json_message_and_error_envelopes() -> None:
    assert json.loads(json_message(True, "seeded", artifacts=3)) == {
        "ok": True,
        "message": "seeded",
        "artifacts": 3,
    }
    assert json.loads(json_error("boom")) == {"ok": False, "error": "boom"}
