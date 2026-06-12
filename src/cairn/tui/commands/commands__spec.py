import json

import pytest

from cairn.tui.commands import (
    ACTION_CLEAR,
    ACTION_QUIT,
    COMMANDS,
    CommandRouter,
    CommandSpec,
    CommandUsageError,
    OutputFormat,
)
from cairn.tui.commands.commands__utils import parse_args, peek_format
from cairn.tui.session import LLMChoice, SessionConfig, build_session


@pytest.fixture
def router() -> CommandRouter:
    return CommandRouter(build_session(SessionConfig(llm=LLMChoice.MOCK)))


def _spec(name: str) -> CommandSpec:
    return next(spec for spec in COMMANDS if spec.name == name)


# --- dispatch -----------------------------------------------------------


async def test_unknown_command_is_reported_not_raised(router: CommandRouter) -> None:
    result = await router.dispatch("/nope")
    assert result.ok is False
    assert "unknown command" in result.body


async def test_help_lists_the_command_surface(router: CommandRouter) -> None:
    result = await router.dispatch("/help")
    assert "/ingest" in result.body
    assert "/query" in result.body
    assert "--format" in result.body


async def test_help_for_one_command_details_flags(router: CommandRouter) -> None:
    result = await router.dispatch("/help query")
    assert "--budget" in result.body
    assert "--top-k" in result.body


async def test_help_json_is_a_machine_readable_schema(router: CommandRouter) -> None:
    result = await router.dispatch("/help --format json")
    assert result.markup is False
    schema = json.loads(result.body)
    assert schema["ok"] is True
    by_name = {c["name"]: c for c in schema["commands"]}
    flags = {f["name"] for f in by_name["artifacts"]["flags"]}
    assert {"type", "min-conf", "limit", "fields", "format"} <= flags


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
    processed = await router.dispatch("/process --type campaign_state")
    assert processed.refresh_sidebar is True
    assert "processed" in processed.body


async def test_bad_artifact_type_is_rejected(router: CommandRouter) -> None:
    await router.dispatch("/ingest something")
    result = await router.dispatch("/process --type not_a_type")
    assert result.ok is False
    assert "not_a_type" in result.body


async def test_old_positional_syntax_hints_at_flags(router: CommandRouter) -> None:
    result = await router.dispatch("/eval contradictions")
    assert result.ok is False
    assert "--flag" in result.body


async def test_missing_artifact_id_is_reported(router: CommandRouter) -> None:
    result = await router.dispatch("/artifact does_not_exist")
    assert result.ok is False


async def test_clear_and_quit_emit_actions(router: CommandRouter) -> None:
    assert (await router.dispatch("/clear")).action == ACTION_CLEAR
    assert (await router.dispatch("/quit")).action == ACTION_QUIT


# --- filters & selectors ------------------------------------------------


async def test_artifacts_filter_by_type(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts --type pricing_policy --format json")
    payload = json.loads(result.body)
    assert payload["count"] == 1
    assert payload["items"][0]["type"] == "pricing_policy"


async def test_artifacts_type_is_case_insensitive(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts --type PRICING_POLICY --format json")
    assert json.loads(result.body)["count"] == 1


async def test_artifacts_limit_and_fields(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts --limit 2 --fields id,title --format json")
    payload = json.loads(result.body)
    assert payload["count"] == 2
    assert set(payload["items"][0]) == {"id", "title"}


async def test_artifacts_filter_by_entity_name(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts --entity acme --format json")
    payload = json.loads(result.body)
    assert payload["count"] == 1
    assert "Acme" in payload["items"][0]["title"]


async def test_artifacts_unknown_entity_is_reported(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts --entity nobody")
    assert result.ok is False
    assert "no entity" in result.body


async def test_entities_filter_by_type_and_name(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/entities --type organization --format json")
    payload = json.loads(result.body)
    assert [item["name"] for item in payload["items"]] == ["Acme Corp"]

    result = await router.dispatch("/entities --name germ --format json")
    assert json.loads(result.body)["items"][0]["name"] == "Germany"


async def test_artifact_accepts_id_prefix(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    listed = json.loads((await router.dispatch("/artifacts --format json")).body)
    full_id = listed["items"][0]["id"]
    result = await router.dispatch(f"/artifact {full_id[:8]} --format json")
    assert result.ok is False  # flags must precede positional text

    result = await router.dispatch(f"/artifact --format json {full_id[:8]}")
    assert json.loads(result.body)["artifact"]["id"] == full_id


async def test_artifact_ambiguous_prefix_lists_candidates(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifact art_")
    assert result.ok is False
    assert "ambiguous" in result.body


async def test_query_flags_pass_through(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/query --top-k 1 --format json germany risks")
    payload = json.loads(result.body)
    assert payload["intent"] == "germany risks"
    assert len(payload["fragments"]) <= 1


async def test_unknown_flag_names_the_alternatives(router: CommandRouter) -> None:
    result = await router.dispatch("/artifacts --bogus 1")
    assert result.ok is False
    assert "--bogus" in result.body
    assert "--type" in result.body


async def test_parse_error_honours_requested_json_format(router: CommandRouter) -> None:
    result = await router.dispatch("/artifacts --bogus 1 --format json")
    assert result.ok is False
    payload = json.loads(result.body)
    assert payload["ok"] is False
    assert "--bogus" in payload["error"]


# --- output formats -----------------------------------------------------


async def test_json_bodies_are_compact_envelopes(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    for command in ("/artifacts", "/entities", "/eval", "/help"):
        result = await router.dispatch(f"{command} --format json")
        assert result.markup is False
        assert "\n" not in result.body
        assert json.loads(result.body)["ok"] is True


async def test_plain_format_strips_markup(router: CommandRouter) -> None:
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts --format plain")
    assert result.markup is False
    assert "[b]" not in result.body
    assert "Germany healthcare outbound" in result.body


async def test_default_format_is_injected_by_router() -> None:
    router = CommandRouter(
        build_session(SessionConfig(llm=LLMChoice.MOCK)),
        default_format=OutputFormat.PLAIN,
    )
    await router.dispatch("/seed")
    result = await router.dispatch("/artifacts")
    assert result.markup is False
    assert "[b]" not in result.body


# --- parser unit tests --------------------------------------------------


def test_parse_args_splits_flags_from_raw_tail() -> None:
    args = parse_args(
        _spec("query"), "--top-k 3 what are the risks", default_format=OutputFormat.RICH
    )
    assert args.values["top_k"] == 3
    assert args.positional == "what are the risks"


def test_parse_args_double_dash_ends_flag_mode() -> None:
    args = parse_args(
        _spec("query"), "-- --top-k looks like a flag", default_format=OutputFormat.RICH
    )
    assert args.positional == "--top-k looks like a flag"
    assert args.values["top_k"] == 10  # default untouched


def test_parse_args_preserves_interior_whitespace() -> None:
    args = parse_args(_spec("ingest"), "two  spaces  kept", default_format=OutputFormat.RICH)
    assert args.positional == "two  spaces  kept"


def test_parse_args_quoted_csv_value() -> None:
    args = parse_args(
        _spec("query"), '--hints "Acme Corp,Legal" intent', default_format=OutputFormat.RICH
    )
    assert args.values["hints"] == ("Acme Corp", "Legal")
    assert args.positional == "intent"


def test_parse_args_bool_flag_takes_no_value() -> None:
    args = parse_args(
        _spec("eval"), "--contradictions --min-severity 0.5", default_format=OutputFormat.RICH
    )
    assert args.values["contradictions"] is True
    assert args.values["min_severity"] == 0.5


def test_parse_args_missing_value_is_an_error() -> None:
    with pytest.raises(CommandUsageError, match="requires a value"):
        parse_args(_spec("artifacts"), "--limit", default_format=OutputFormat.RICH)


def test_parse_args_bad_int_is_an_error() -> None:
    with pytest.raises(CommandUsageError, match="integer"):
        parse_args(_spec("artifacts"), "--limit five", default_format=OutputFormat.RICH)


def test_parse_args_validates_field_choices() -> None:
    with pytest.raises(CommandUsageError, match="--fields"):
        parse_args(_spec("artifacts"), "--fields id,bogus", default_format=OutputFormat.RICH)


def test_peek_format_finds_format_after_parse_failure() -> None:
    assert peek_format("--bogus x --format json", OutputFormat.RICH) is OutputFormat.JSON
    assert peek_format("no format here", OutputFormat.PLAIN) is OutputFormat.PLAIN
