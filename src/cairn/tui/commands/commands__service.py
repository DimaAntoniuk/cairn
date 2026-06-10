from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from cairn.domain import ArtifactType
from cairn.ingestion import ManualConnector
from cairn.tui.render import (
    esc,
    format_artifact_detail,
    format_artifacts,
    format_context,
    format_entities,
    format_issues,
)
from cairn.tui.session import CairnSession, seed_demo

from .commands__consts import ACTION_CLEAR, ACTION_QUIT, COMMANDS
from .commands__types import CommandResult

_PROCESS_DEFAULT = ArtifactType.ACCOUNT_INTELLIGENCE
_CONTRADICTION_FLAGS = {"contradictions", "contradiction", "all"}


class CommandRouter:
    """Parses a line of input and drives the ``KnowledgeLayer`` via the session.

    All behaviour delegates to ``session.layer`` — the router only parses, calls,
    and formats, so there is no second copy of the pipeline logic.
    """

    def __init__(self, session: CairnSession) -> None:
        self._session = session

    async def dispatch(self, text: str) -> CommandResult:
        text = text.strip()
        if not text:
            return CommandResult()
        if not text.startswith("/"):
            return await self._cmd_query(text)
        name, _, arg = text[1:].partition(" ")
        handler = cast(
            "Callable[[str], Awaitable[CommandResult]] | None",
            getattr(self, f"_cmd_{name}", None),
        )
        if handler is None:
            return CommandResult(
                f"[red]unknown command[/] /{esc(name)} — try [b]/help[/]", ok=False
            )
        try:
            return await handler(arg.strip())
        except Exception as exc:  # surface library errors in the transcript, never crash the UI
            return CommandResult(f"[red]error:[/] {esc(str(exc))}", ok=False)

    async def _cmd_help(self, arg: str) -> CommandResult:
        lines = ["[b]commands[/b] [dim](prefix /, or just type text to query)[/dim]"]
        for spec in COMMANDS:
            usage = f"/{spec.name} {spec.arg}".strip()
            lines.append(f"  [cyan]{usage:<24}[/] [dim]{spec.help}[/dim]")
        return CommandResult("\n".join(lines))

    async def _cmd_ingest(self, arg: str) -> CommandResult:
        if not arg:
            return CommandResult("[yellow]usage:[/] /ingest <text>", ok=False)
        n = await self._session.layer.ingest_from([ManualConnector.from_texts([arg])])
        return CommandResult(f"buffered [b]{n}[/b] document(s) — run [b]/process[/b]")

    async def _cmd_load(self, arg: str) -> CommandResult:
        if not arg:
            return CommandResult("[yellow]usage:[/] /load <path>", ok=False)
        path = Path(arg).expanduser()
        if not path.is_file():
            return CommandResult(f"[red]no such file:[/] {esc(str(path))}", ok=False)
        text = path.read_text(encoding="utf-8", errors="replace")
        await self._session.layer.ingest_from([ManualConnector.from_texts([text])])
        return CommandResult(
            f"buffered [b]{esc(path.name)}[/b] ({len(text)} chars) — run [b]/process[/b]"
        )

    async def _cmd_process(self, arg: str) -> CommandResult:
        artifact_type = _PROCESS_DEFAULT
        if arg:
            try:
                artifact_type = ArtifactType(arg)
            except ValueError:
                allowed = ", ".join(t.value for t in ArtifactType)
                return CommandResult(
                    f"[red]unknown artifact type[/] {esc(arg)}\n[dim]one of: {allowed}[/dim]",
                    ok=False,
                )
        result = await self._session.layer.process_buffer(artifact_type=artifact_type)
        if result.documents == 0:
            return CommandResult("[yellow]buffer empty[/] — /ingest or /load first", ok=False)
        return CommandResult(
            f"processed [b]{result.documents}[/b] doc(s) → "
            f"[b]{len(result.facts)}[/b] fact(s), "
            f"[b]{len(result.entities)}[/b] entity(ies), "
            f"[b]{len(result.artifacts)}[/b] artifact(s)",
            refresh_sidebar=True,
        )

    async def _cmd_query(self, arg: str) -> CommandResult:
        if not arg:
            return CommandResult("[yellow]usage:[/] /query <intent>", ok=False)
        ctx = await self._session.layer.query(arg, token_budget=self._session.token_budget)
        return CommandResult(format_context(ctx, intent=arg))

    async def _cmd_artifacts(self, arg: str) -> CommandResult:
        artifacts = await self._session.layer.artifact_store.list()
        return CommandResult(format_artifacts(artifacts))

    async def _cmd_artifact(self, arg: str) -> CommandResult:
        if not arg:
            return CommandResult("[yellow]usage:[/] /artifact <id>", ok=False)
        artifact = await self._session.layer.artifact_store.get(arg)
        if artifact is None:
            return CommandResult(f"[red]no artifact[/] {esc(arg)}", ok=False)
        return CommandResult(format_artifact_detail(artifact))

    async def _cmd_entities(self, arg: str) -> CommandResult:
        entities = await self._session.layer.graph_store.find_entities()
        return CommandResult(format_entities(entities))

    async def _cmd_wiki(self, arg: str) -> CommandResult:
        pages = await self._session.layer.refresh_wiki()
        return CommandResult(f"refreshed [b]{len(pages)}[/b] wiki page(s)", refresh_sidebar=True)

    async def _cmd_eval(self, arg: str) -> CommandResult:
        check = arg.lower() in _CONTRADICTION_FLAGS
        issues = await self._session.layer.evaluate(check_contradictions=check)
        return CommandResult(format_issues(issues))

    async def _cmd_seed(self, arg: str) -> CommandResult:
        n = await seed_demo(self._session)
        return CommandResult(f"seeded [b]{n}[/b] demo artifact(s)", refresh_sidebar=True)

    async def _cmd_clear(self, arg: str) -> CommandResult:
        return CommandResult(action=ACTION_CLEAR)

    async def _cmd_quit(self, arg: str) -> CommandResult:
        return CommandResult("bye 👋", action=ACTION_QUIT)


__all__ = ["CommandRouter"]
