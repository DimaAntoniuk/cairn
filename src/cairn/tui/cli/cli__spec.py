import json

import pytest

from cairn.tui.cli.cli__service import _parse_args, main


def test_parse_args_collects_repeated_exec_commands() -> None:
    config, commands = _parse_args(["--llm", "mock", "--exec", "/seed", "--exec", "/artifacts"])
    assert commands == ["/seed", "/artifacts"]
    assert config.seed is False


def test_parse_args_without_exec_returns_none() -> None:
    _, commands = _parse_args(["--llm", "mock"])
    assert commands is None


def test_exec_mode_prints_json_lines(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--llm",
            "mock",
            "--seed",
            "--exec",
            "/artifacts --format json",
            "--exec",
            "/entities --format json",
        ]
    )
    assert code == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)
        assert payload["ok"] is True
        assert payload["count"] == 3


def test_exec_mode_defaults_to_plain_output(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--llm", "mock", "--seed", "--exec", "/artifacts"])
    assert code == 0
    out = capsys.readouterr().out
    assert "[b]" not in out
    assert "Germany healthcare outbound" in out


def test_exec_mode_failure_sets_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--llm", "mock", "--exec", "/artifact nope"])
    assert code == 1
    assert "no artifact" in capsys.readouterr().out


def test_exec_mode_quit_stops_the_batch(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--llm", "mock", "--exec", "/quit", "--exec", "/seed"])
    assert code == 0
    out = capsys.readouterr().out
    assert "bye" in out
    assert "seeded" not in out
