import re
from collections.abc import Sequence

from cairn.domain import Artifact, AssembledContext, Entity, EvalIssue

from .render__consts import (
    ARTIFACT_ICONS,
    CONFIDENCE_STYLES,
    DEFAULT_ARTIFACT_ICON,
    DEFAULT_ENTITY_ICON,
    ENTITY_ICONS,
    ISSUE_LABELS,
    MAX_SIDEBAR_ITEMS,
    SEVERITY_STYLES,
)


def esc(text: str) -> str:
    """Escape Rich markup so arbitrary content renders literally in a RichLog."""
    return text.replace("[", r"\[")


_ESCAPED_BRACKET_SENTINEL = "\x00"
_MARKUP_TAG_RE = re.compile(r"\[[^\[\]]*\]")


def strip_markup(markup: str) -> str:
    """Plain-text rendering of markup produced by this module.

    Safe because ``esc()`` guarantees every literal ``[`` in content arrives as
    ``\\[``: protect those, drop the remaining ``[tag]`` spans, restore brackets.
    Hand-rolled so plain output never needs the optional ``rich`` dependency.
    """
    text = markup.replace(r"\[", _ESCAPED_BRACKET_SENTINEL)
    text = _MARKUP_TAG_RE.sub("", text)
    return text.replace(_ESCAPED_BRACKET_SENTINEL, "[")


def _style_for(value: float, styles: tuple[tuple[float, str], ...]) -> str:
    for threshold, style in styles:
        if value >= threshold:
            return style
    return styles[-1][1]


def _conf(score: float) -> str:
    return f"[{_style_for(score, CONFIDENCE_STYLES)}]conf {score:.2f}[/]"


def _sidebar_section(title: str, rows: list[tuple[str, str]]) -> str:
    if not rows:
        return f"[b]{title}[/b]\n[dim]none yet[/dim]"
    lines = [f"[b]{title}[/b] [dim]({len(rows)})[/dim]"]
    for icon, text in rows[:MAX_SIDEBAR_ITEMS]:
        lines.append(f"{icon} {esc(text)}")
    overflow = len(rows) - MAX_SIDEBAR_ITEMS
    if overflow > 0:
        lines.append(f"[dim]+{overflow} more[/dim]")
    return "\n".join(lines)


def format_sidebar_artifacts(artifacts: Sequence[Artifact]) -> str:
    rows = [
        (ARTIFACT_ICONS.get(a.artifact_type, DEFAULT_ARTIFACT_ICON), a.title) for a in artifacts
    ]
    return _sidebar_section("Artifacts", rows)


def format_sidebar_entities(entities: Sequence[Entity]) -> str:
    rows = [(ENTITY_ICONS.get(e.entity_type, DEFAULT_ENTITY_ICON), e.name) for e in entities]
    return _sidebar_section("Entities", rows)


def format_artifacts(artifacts: Sequence[Artifact]) -> str:
    if not artifacts:
        return "[dim]no artifacts — /ingest then /process, or /seed for demo data[/dim]"
    lines = [f"[b]{len(artifacts)} artifact(s)[/b]"]
    for art in artifacts:
        icon = ARTIFACT_ICONS.get(art.artifact_type, DEFAULT_ARTIFACT_ICON)
        lines.append(
            f"{icon} [b]{esc(art.title)}[/b]  {_conf(art.confidence.score)}\n"
            f"   [dim]{art.artifact_type.value} · {art.artifact_id}[/dim]"
        )
    return "\n".join(lines)


def format_artifact_detail(artifact: Artifact) -> str:
    icon = ARTIFACT_ICONS.get(artifact.artifact_type, DEFAULT_ARTIFACT_ICON)
    lines = [
        f"{icon} [b]{esc(artifact.title)}[/b]  {_conf(artifact.confidence.score)}",
        f"[dim]{artifact.artifact_type.value} · {artifact.artifact_id} · v{artifact.version}[/dim]",
        "",
        esc(artifact.summary),
    ]
    if artifact.content:
        lines.append("")
        for key, value in artifact.content.items():
            lines.append(f"[cyan]{esc(str(key))}[/]: {esc(str(value))}")
    if artifact.entity_refs:
        lines.append("")
        lines.append(f"[dim]entities:[/dim] {esc(', '.join(artifact.entity_refs))}")
    if artifact.source_refs:
        srcs = ", ".join(f"{r.system.value}:{r.external_id}" for r in artifact.source_refs)
        lines.append(f"[dim]sources:[/dim] {esc(srcs)}")
    return "\n".join(lines)


def format_entities(entities: Sequence[Entity]) -> str:
    if not entities:
        return "[dim]no entities — /ingest then /process, or /seed for demo data[/dim]"
    lines = [f"[b]{len(entities)} entit{'y' if len(entities) == 1 else 'ies'}[/b]"]
    for ent in entities:
        icon = ENTITY_ICONS.get(ent.entity_type, DEFAULT_ENTITY_ICON)
        alias = f"  [dim]({esc(', '.join(ent.aliases))})[/dim]" if ent.aliases else ""
        lines.append(f"{icon} [b]{esc(ent.name)}[/b] [dim]{ent.entity_type.value}[/dim]{alias}")
    return "\n".join(lines)


def format_context(ctx: AssembledContext, *, intent: str) -> str:
    head = (
        f"[b]context[/b] for [i]{esc(intent)}[/i]\n"
        f"[dim]{ctx.total_tokens} tok · {len(ctx.fragments)} fragment(s)"
    )
    if ctx.dropped_fragment_ids:
        head += f" · {len(ctx.dropped_fragment_ids)} dropped"
    head += "[/dim]"
    if not ctx.fragments:
        return head + "\n[dim](nothing matched — ingest & /process first, or /seed)[/dim]"
    blocks = [head]
    for frag in ctx.fragments:
        blocks.append(f"[dim]{'─' * 8} {_conf(frag.confidence.score)}[/dim]\n{esc(frag.text)}")
    return "\n".join(blocks)


def format_issues(issues: Sequence[EvalIssue]) -> str:
    if not issues:
        return "[green]✓ no evaluation issues[/green]"
    lines = [f"[b]{len(issues)} issue(s)[/b]"]
    for issue in issues:
        style = _style_for(issue.severity, SEVERITY_STYLES)
        label = ISSUE_LABELS.get(issue.kind, issue.kind.value)
        refs = f" [dim]{esc(', '.join(issue.artifact_ids))}[/dim]" if issue.artifact_ids else ""
        lines.append(f"[{style}]●[/] [b]{label}[/b] {issue.severity:.2f}{refs}\n   {esc(issue.description)}")
    return "\n".join(lines)


__all__ = [
    "esc",
    "format_artifact_detail",
    "format_artifacts",
    "format_context",
    "format_entities",
    "format_issues",
    "format_sidebar_artifacts",
    "format_sidebar_entities",
    "strip_markup",
]
