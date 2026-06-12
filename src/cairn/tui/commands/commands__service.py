from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from cairn.domain import ArtifactType, EntityType, IssueKind, iter_active_artifacts
from cairn.ingestion import ManualConnector
from cairn.tui.render import (
    esc,
    format_artifact_detail,
    format_artifacts,
    format_context,
    format_entities,
    format_issues,
    strip_markup,
)
from cairn.tui.serialize import (
    DEFAULT_ARTIFACT_DETAIL_FIELDS,
    DEFAULT_ARTIFACT_LIST_FIELDS,
    DEFAULT_ENTITY_LIST_FIELDS,
    json_artifact,
    json_artifacts,
    json_context,
    json_entities,
    json_error,
    json_issues,
    json_message,
)
from cairn.tui.session import CairnSession, seed_demo

from .commands__consts import ACTION_CLEAR, ACTION_QUIT, COMMANDS
from .commands__types import (
    CommandResult,
    CommandSpec,
    CommandUsageError,
    OutputFormat,
    ParsedArgs,
)
from .commands__utils import (
    FORMAT_FLAG,
    coerce_enum,
    default_values,
    json_help,
    parse_args,
    peek_format,
)


class CommandRouter:
    """Parses a line of input and drives the ``KnowledgeLayer`` via the session.

    All behaviour delegates to ``session.layer`` — the router only parses, calls,
    and formats, so there is no second copy of the pipeline logic. Every command
    accepts ``--format rich|plain|json``; ``default_format`` sets the fallback
    (RICH in the TUI, PLAIN in exec mode).
    """

    def __init__(
        self, session: CairnSession, *, default_format: OutputFormat = OutputFormat.RICH
    ) -> None:
        self._session = session
        self._default_format = default_format
        self._specs: dict[str, CommandSpec] = {spec.name: spec for spec in COMMANDS}
        # Bind handlers from the COMMANDS registry so a spec without a matching
        # _cmd_ method fails at construction instead of drifting silently.
        self._handlers: dict[str, Callable[[ParsedArgs], Awaitable[CommandResult]]] = {
            spec.name: getattr(self, f"_cmd_{spec.name}") for spec in COMMANDS
        }

    async def dispatch(self, text: str) -> CommandResult:
        text = text.strip()
        if not text:
            return CommandResult()
        if not text.startswith("/"):
            spec = self._specs["query"]
            args = ParsedArgs(
                positional=text, format=self._default_format, values=default_values(spec)
            )
            return await self._run(self._cmd_query, args)
        name, _, arg = text[1:].partition(" ")
        arg = arg.strip()
        fmt = peek_format(arg, self._default_format)
        named_spec = self._specs.get(name)
        if named_spec is None:
            return self._error(f"unknown command /{name} — try /help", fmt)
        spec = named_spec
        try:
            args = parse_args(spec, arg, default_format=self._default_format)
        except CommandUsageError as exc:
            return self._error(str(exc), fmt)
        return await self._run(self._handlers[name], args)

    async def _run(
        self, handler: Callable[[ParsedArgs], Awaitable[CommandResult]], args: ParsedArgs
    ) -> CommandResult:
        try:
            return await handler(args)
        except CommandUsageError as exc:
            return self._error(str(exc), args.format)
        except Exception as exc:  # surface library errors in the transcript, never crash the UI
            return self._error(str(exc), args.format)

    def _error(self, message: str, fmt: OutputFormat) -> CommandResult:
        if fmt is OutputFormat.JSON:
            return CommandResult(json_error(message), ok=False, markup=False)
        if fmt is OutputFormat.PLAIN:
            return CommandResult(f"error: {message}", ok=False, markup=False)
        return CommandResult(f"[red]error:[/] {esc(message)}", ok=False)

    def _emit(
        self,
        args: ParsedArgs,
        rich_body: str,
        json_body: str,
        *,
        refresh_sidebar: bool = False,
        action: str | None = None,
    ) -> CommandResult:
        if args.format is OutputFormat.JSON:
            return CommandResult(
                json_body, refresh_sidebar=refresh_sidebar, action=action, markup=False
            )
        if args.format is OutputFormat.PLAIN:
            return CommandResult(
                strip_markup(rich_body),
                refresh_sidebar=refresh_sidebar,
                action=action,
                markup=False,
            )
        return CommandResult(rich_body, refresh_sidebar=refresh_sidebar, action=action)

    async def _cmd_help(self, args: ParsedArgs) -> CommandResult:
        if args.positional:
            name = args.positional.lstrip("/").split()[0]
            spec = self._specs.get(name)
            if spec is None:
                raise CommandUsageError(f"unknown command /{name} — try /help")
            return self._emit(args, _help_detail(spec), json_help((spec,)))
        return self._emit(args, _help_overview(), json_help(COMMANDS))

    async def _cmd_ingest(self, args: ParsedArgs) -> CommandResult:
        if not args.positional:
            raise CommandUsageError("usage: /ingest <text>")
        n = await self._session.layer.ingest_from([ManualConnector.from_texts([args.positional])])
        return self._emit(
            args,
            f"buffered [b]{n}[/b] document(s) — run [b]/process[/b]",
            json_message(True, "buffered", documents=n),
        )

    async def _cmd_load(self, args: ParsedArgs) -> CommandResult:
        if not args.positional:
            raise CommandUsageError("usage: /load <path>")
        path = Path(args.positional).expanduser()
        if not path.is_file():
            raise CommandUsageError(f"no such file: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        await self._session.layer.ingest_from([ManualConnector.from_texts([text])])
        return self._emit(
            args,
            f"buffered [b]{esc(path.name)}[/b] ({len(text)} chars) — run [b]/process[/b]",
            json_message(True, "buffered", file=path.name, chars=len(text)),
        )

    async def _cmd_process(self, args: ParsedArgs) -> CommandResult:
        artifact_type = coerce_enum(ArtifactType, cast(str, args.values["type"]))
        result = await self._session.layer.process_buffer(artifact_type=artifact_type)
        if result.documents == 0:
            return self._error("buffer empty — /ingest or /load first", args.format)
        return self._emit(
            args,
            f"processed [b]{result.documents}[/b] doc(s) → "
            f"[b]{len(result.facts)}[/b] fact(s), "
            f"[b]{len(result.entities)}[/b] entity(ies), "
            f"[b]{len(result.artifacts)}[/b] artifact(s)",
            json_message(
                True,
                "processed",
                documents=result.documents,
                facts=len(result.facts),
                entities=len(result.entities),
                artifacts=[a.artifact_id for a in result.artifacts],
            ),
            refresh_sidebar=True,
        )

    async def _cmd_query(self, args: ParsedArgs) -> CommandResult:
        intent = args.positional
        if not intent:
            raise CommandUsageError("usage: /query [--flags] <intent>")
        v = args.values
        budget = cast(int | None, v["budget"]) or self._session.token_budget
        types = tuple(coerce_enum(ArtifactType, t) for t in cast(tuple[str, ...], v["types"]))
        ctx = await self._session.layer.query(
            intent,
            token_budget=budget,
            entity_hints=cast(tuple[str, ...], v["hints"]),
            artifact_types=types,
            min_confidence=cast(float, v["min_conf"]),
            max_age_days=cast(int | None, v["max_age"]),
            top_k=cast(int, v["top_k"]),
            graph_depth=cast(int, v["depth"]),
        )
        return self._emit(
            args, format_context(ctx, intent=intent), json_context(ctx, intent=intent)
        )

    async def _cmd_artifacts(self, args: ParsedArgs) -> CommandResult:
        v = args.values
        raw_type = cast(str | None, v["type"])
        artifact_type = coerce_enum(ArtifactType, raw_type) if raw_type else None
        raw_entity = cast(str | None, v["entity"])
        entity_ref = await self._resolve_entity_ref(raw_entity) if raw_entity else None
        artifacts = await self._session.layer.artifact_store.list(
            artifact_type=artifact_type, entity_ref=entity_ref
        )
        if not v["all"]:
            artifacts = iter_active_artifacts(artifacts)
        min_conf = cast(float, v["min_conf"])
        if min_conf:
            artifacts = [a for a in artifacts if a.confidence.score >= min_conf]
        limit = cast(int | None, v["limit"])
        if limit is not None:
            artifacts = artifacts[:limit]
        fields = cast(tuple[str, ...], v["fields"]) or DEFAULT_ARTIFACT_LIST_FIELDS
        return self._emit(args, format_artifacts(artifacts), json_artifacts(artifacts, fields))

    async def _cmd_artifact(self, args: ParsedArgs) -> CommandResult:
        ident = args.positional
        if not ident:
            raise CommandUsageError("usage: /artifact <id>")
        store = self._session.layer.artifact_store
        artifact = await store.get(ident)
        if artifact is None:
            candidates = [a for a in await store.list() if a.artifact_id.startswith(ident)]
            if len(candidates) > 1:
                ids = ", ".join(a.artifact_id for a in candidates)
                raise CommandUsageError(f"ambiguous id {ident!r}: {ids}")
            if not candidates:
                raise CommandUsageError(f"no artifact {ident}")
            artifact = candidates[0]
        fields = cast(tuple[str, ...], args.values["fields"]) or DEFAULT_ARTIFACT_DETAIL_FIELDS
        return self._emit(args, format_artifact_detail(artifact), json_artifact(artifact, fields))

    async def _cmd_entities(self, args: ParsedArgs) -> CommandResult:
        v = args.values
        raw_type = cast(str | None, v["type"])
        entity_type = coerce_enum(EntityType, raw_type) if raw_type else None
        entities = await self._session.layer.graph_store.find_entities(
            name=cast(str | None, v["name"]), entity_type=entity_type
        )
        limit = cast(int | None, v["limit"])
        if limit is not None:
            entities = entities[:limit]
        fields = cast(tuple[str, ...], v["fields"]) or DEFAULT_ENTITY_LIST_FIELDS
        return self._emit(args, format_entities(entities), json_entities(entities, fields))

    async def _cmd_wiki(self, args: ParsedArgs) -> CommandResult:
        pages = await self._session.layer.refresh_wiki()
        return self._emit(
            args,
            f"refreshed [b]{len(pages)}[/b] wiki page(s)",
            json_message(True, "wiki refreshed", pages=len(pages)),
            refresh_sidebar=True,
        )

    async def _cmd_eval(self, args: ParsedArgs) -> CommandResult:
        v = args.values
        issues = await self._session.layer.evaluate(
            check_contradictions=cast(bool, v["contradictions"])
        )
        raw_kind = cast(str | None, v["kind"])
        if raw_kind:
            kind = coerce_enum(IssueKind, raw_kind)
            issues = [i for i in issues if i.kind is kind]
        min_severity = cast(float, v["min_severity"])
        if min_severity:
            issues = [i for i in issues if i.severity >= min_severity]
        return self._emit(args, format_issues(issues), json_issues(issues))

    async def _cmd_seed(self, args: ParsedArgs) -> CommandResult:
        n = await seed_demo(self._session)
        return self._emit(
            args,
            f"seeded [b]{n}[/b] demo artifact(s)",
            json_message(True, "seeded", artifacts=n),
            refresh_sidebar=True,
        )

    async def _cmd_clear(self, args: ParsedArgs) -> CommandResult:
        return CommandResult(action=ACTION_CLEAR)

    async def _cmd_quit(self, args: ParsedArgs) -> CommandResult:
        return self._emit(args, "bye 👋", json_message(True, "bye"), action=ACTION_QUIT)

    async def _resolve_entity_ref(self, raw: str) -> str:
        """Accept an entity id as-is; resolve anything else by name lookup."""
        if raw.startswith("ent_"):
            return raw
        matches = await self._session.layer.graph_store.find_entities(name=raw)
        if not matches:
            raise CommandUsageError(f"no entity matching {raw!r}")
        return matches[0].id


def _help_overview() -> str:
    lines = [
        "[b]commands[/b] [dim](prefix /, or just type text to query · "
        "every command takes --format rich|plain|json · /help <command> for flag detail)[/dim]"
    ]
    for spec in COMMANDS:
        usage = f"/{spec.name} {spec.arg}".strip()
        lines.append(f"  [cyan]{usage:<24}[/] [dim]{spec.help}[/dim]")
        if spec.flags:
            flag_names = " ".join(f"--{flag.name}" for flag in spec.flags)
            lines.append(f"  {'':<24}  [dim]{flag_names}[/dim]")
    return "\n".join(lines)


def _help_detail(spec: CommandSpec) -> str:
    usage = f"/{spec.name} {spec.arg}".strip()
    lines = [f"[b]{usage}[/b] — {spec.help}"]
    for flag in (*spec.flags, FORMAT_FLAG):
        line = f"  [cyan]--{flag.name}[/] [dim]{flag.type.value}[/dim]  {flag.help}"
        if flag.default not in (None, (), False):
            line += f" [dim](default {flag.default})[/dim]"
        if flag.choices:
            line += f"\n  {'':<{len(flag.name) + 4}}[dim]one of: {', '.join(flag.choices)}[/dim]"
        lines.append(line)
    return "\n".join(lines)


__all__ = ["CommandRouter"]
