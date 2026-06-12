import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, RichLog, Static

from cairn.domain import ConfigError
from cairn.tui.commands import ACTION_CLEAR, ACTION_QUIT, CommandResult, CommandRouter
from cairn.tui.render import esc, format_sidebar_artifacts, format_sidebar_entities
from cairn.tui.session import CairnSession, SessionConfig, build_session, seed_demo
from cairn.tui.session.session__consts import APP_SUBTITLE, APP_TITLE, SIDEBAR_WIDTH

from .app__consts import BINDINGS, CSS, INTRO, PROMPT_PLACEHOLDER

_WORKING = "⠿ working…"


class CairnApp(App[None]):
    """A Claude-Code-style terminal client for the cairn knowledge layer.

    The app is a thin shell: it owns widgets and input plumbing, then hands every
    line to a ``CommandRouter`` that drives the shared ``KnowledgeLayer``.
    """

    CSS = CSS
    BINDINGS = BINDINGS
    TITLE = APP_TITLE
    SUB_TITLE = APP_SUBTITLE

    def __init__(self, config: SessionConfig) -> None:
        super().__init__()
        self._config = config
        self._session: CairnSession | None = None
        self._router: CommandRouter | None = None
        # Serializes command workers in submission order. A lock (rather than
        # `run_worker(exclusive=True)`) so a rapid second submit queues instead
        # of cancelling the in-flight command mid-side-effect.
        self._command_gate = asyncio.Lock()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield RichLog(id="transcript", wrap=True, markup=True, auto_scroll=True)
            with VerticalScroll(id="sidebar"):
                yield Static(format_sidebar_artifacts([]), id="artifacts")
                yield Static(format_sidebar_entities([]), id="entities")
        yield Input(placeholder=PROMPT_PLACEHOLDER, id="prompt")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#sidebar").styles.width = SIDEBAR_WIDTH
        self.query_one("#prompt", Input).focus()
        self._write(INTRO)
        try:
            self._session = build_session(self._config)
        except ConfigError as exc:
            self._write(f"[red]config error:[/] {esc(str(exc))}")
            return
        except Exception as exc:  # keep the UI alive; render the failure instead
            self._write(f"[red]startup error:[/] {esc(str(exc))}")
            return
        self._router = CommandRouter(self._session)
        self._write(
            f"[dim]llm:[/dim] [b]{esc(self._session.llm_label)}[/b]   "
            "[dim]/help for commands[/dim]"
        )
        if self._config.seed:
            count = await seed_demo(self._session)
            self._write(f"[dim]seeded {count} demo artifact(s)[/dim]")
        await self._refresh_sidebar()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value
        event.input.value = ""
        if not text.strip() or self._router is None:
            return
        self._echo(text)
        self.run_worker(self._dispatch(text), group="command")

    async def _dispatch(self, text: str) -> None:
        assert self._router is not None
        async with self._command_gate:
            self.sub_title = _WORKING
            try:
                result = await self._router.dispatch(text)
            finally:
                self.sub_title = APP_SUBTITLE
            await self._apply(result)

    async def _apply(self, result: CommandResult) -> None:
        # Plain/JSON bodies (markup=False) are escaped so brackets render
        # literally instead of being parsed as Rich tags by the RichLog.
        body = result.body if result.markup else esc(result.body)
        if result.action == ACTION_QUIT:
            if body:
                self._write(body)
            self.exit()
            return
        if result.action == ACTION_CLEAR:
            self.action_clear()
            return
        if body:
            self._write(body)
        if result.refresh_sidebar:
            await self._refresh_sidebar()

    async def _refresh_sidebar(self) -> None:
        if self._session is None:
            return
        artifacts, entities = await self._session.snapshot()
        self.query_one("#artifacts", Static).update(format_sidebar_artifacts(artifacts))
        self.query_one("#entities", Static).update(format_sidebar_entities(entities))

    def _echo(self, text: str) -> None:
        self._write(f"[b green]›[/] {esc(text)}")  # noqa: RUF001 — prompt glyph, not '>'

    def _write(self, markup: str) -> None:
        log = self.query_one("#transcript", RichLog)
        log.write(markup)
        log.write("")

    def action_clear(self) -> None:
        self.query_one("#transcript", RichLog).clear()


__all__ = ["CairnApp"]
