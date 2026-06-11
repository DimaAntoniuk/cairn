import pytest

pytest.importorskip("textual")

from textual.widgets import Input, RichLog

from cairn.tui.app.app__service import CairnApp
from cairn.tui.session import LLMChoice, SessionConfig


async def test_app_boots_seeds_and_handles_input() -> None:
    app = CairnApp(SessionConfig(llm=LLMChoice.MOCK, seed=True))
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()

        # on_mount built the session and seeded demo data into the sidebar.
        assert app._session is not None
        artifacts, entities = await app._session.snapshot()
        assert len(artifacts) == 3
        assert len(entities) == 3

        # Submitting a line drives the router and appends to the transcript.
        transcript = app.query_one("#transcript", RichLog)
        before = len(transcript.lines)
        app.query_one("#prompt", Input).value = "Germany healthcare outbound"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert len(transcript.lines) > before


async def test_unknown_command_does_not_crash_the_app() -> None:
    app = CairnApp(SessionConfig(llm=LLMChoice.MOCK))
    async with app.run_test() as pilot:
        app.query_one("#prompt", Input).value = "/definitely-not-a-command"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.is_running
