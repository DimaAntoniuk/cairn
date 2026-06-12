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
)
from cairn.tui.render import (
    esc,
    format_artifact_detail,
    format_artifacts,
    format_context,
    format_entities,
    format_issues,
    format_sidebar_artifacts,
    strip_markup,
)


def _artifact(title: str = "Germany state", score: float = 0.82) -> Artifact:
    return Artifact(
        artifact_type=ArtifactType.CAMPAIGN_STATE,
        title=title,
        summary="paused pending legal",
        content={"status": "paused"},
        confidence=Confidence(score=score),
    )


def test_esc_neutralises_markup_brackets() -> None:
    assert esc("a [bold] tag") == r"a \[bold] tag"


def test_strip_markup_removes_tags() -> None:
    assert strip_markup("[b]3 artifact(s)[/b] [dim]hint[/dim]") == "3 artifact(s) hint"


def test_strip_markup_restores_escaped_content_brackets() -> None:
    assert strip_markup(esc("risk [P1] in json: [1,2]")) == "risk [P1] in json: [1,2]"


def test_strip_markup_round_trips_rendered_output() -> None:
    out = strip_markup(format_artifacts([_artifact(title="risk [P1]")]))
    assert "risk [P1]" in out
    assert "[b]" not in out


def test_format_artifacts_empty_hints_at_next_step() -> None:
    assert "/process" in format_artifacts([])


def test_format_artifacts_lists_titles_and_confidence() -> None:
    out = format_artifacts([_artifact()])
    assert "Germany state" in out
    assert "conf 0.82" in out


def test_format_artifact_detail_escapes_user_content() -> None:
    out = format_artifact_detail(_artifact(title="risk [P1]"))
    assert r"risk \[P1]" in out
    assert "status" in out


def test_format_sidebar_artifacts_uses_type_icon() -> None:
    out = format_sidebar_artifacts([_artifact()])
    assert "📣" in out
    assert "Germany state" in out


def test_format_entities_renders_type() -> None:
    out = format_entities([Entity(entity_type=EntityType.REGION, name="Germany")])
    assert "Germany" in out
    assert "region" in out


def test_format_context_reports_token_total() -> None:
    ctx = AssembledContext(
        fragments=[ContextFragment(text="Germany is paused", token_estimate=4)],
        total_tokens=4,
    )
    out = format_context(ctx, intent="state?")
    assert "4 tok" in out
    assert "Germany is paused" in out


def test_format_context_empty_is_graceful() -> None:
    ctx = AssembledContext(fragments=[], total_tokens=0)
    assert "nothing matched" in format_context(ctx, intent="x")


def test_format_issues_ok_when_empty() -> None:
    assert "no evaluation issues" in format_issues([])


def test_format_issues_lists_kind_and_severity() -> None:
    issue = EvalIssue(
        kind=IssueKind.STALE,
        artifact_ids=["art_1"],
        description="older than 90 days",
        severity=0.8,
    )
    out = format_issues([issue])
    assert "stale" in out
    assert "art_1" in out
