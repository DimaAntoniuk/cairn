import pytest

from cairn.tui.commands import ACTION_CLEAR, ACTION_QUIT, CommandRouter
from cairn.tui.session import LLMChoice, SessionConfig, build_session


@pytest.fixture
def router() -> CommandRouter:
    return CommandRouter(build_session(SessionConfig(llm=LLMChoice.MOCK)))


async def test_unknown_command_is_reported_not_raised(router: CommandRouter) -> None:
    result = await router.dispatch("/nope")
    assert result.ok is False
    assert "unknown command" in result.body


async def test_help_lists_the_command_surface(router: CommandRouter) -> None:
    result = await router.dispatch("/help")
    assert "/ingest" in result.body
    assert "/query" in result.body


async def test_empty_input_is_a_noop(router: CommandRouter) -> None:
    result = await router.dispatch("   ")
    assert result.body == ""
    assert result.action is None


async def test_process_on_empty_buffer_warns(router: CommandRouter) -> None:
    result = await router.dispatch("/process")
    assert result.ok is False
    assert "buffer empty" in result.body


async def test_seed_then_artifacts_lists_demo_titles(router: CommandRouter) -> None:
    seeded = await router.dispatch("/seed")
    assert seeded.refresh_sidebar is True

    listed = await router.dispatch("/artifacts")
    assert "Germany healthcare outbound" in listed.body


async def test_bare_text_is_routed_to_query(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("Germany healthcare outbound")
    assert "context" in result.body
    assert "Germany" in result.body


async def test_ingest_then_process_runs_the_pipeline(router: CommandRouter) -> None:
    buffered = await router.dispatch("/ingest pause Germany outbound until legal approves")
    assert "buffered" in buffered.body
    processed = await router.dispatch("/process campaign_state")
    assert processed.refresh_sidebar is True
    assert "processed" in processed.body


async def test_bad_artifact_type_is_rejected(router: CommandRouter) -> None:
    await router.dispatch("/ingest something")
    result = await router.dispatch("/process not_a_type")
    assert result.ok is False
    assert "unknown artifact type" in result.body


async def test_missing_artifact_id_is_reported(router: CommandRouter) -> None:
    result = await router.dispatch("/artifact does_not_exist")
    assert result.ok is False


async def test_clear_and_quit_emit_actions(router: CommandRouter) -> None:
    assert (await router.dispatch("/clear")).action == ACTION_CLEAR
    assert (await router.dispatch("/quit")).action == ACTION_QUIT
