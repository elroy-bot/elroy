import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from elroy import __version__
from elroy.core.ctx import ElroyConfig
from elroy.ui.app import RESTART_RESUME_MESSAGE_ENV, AppRestartRequest, main

from .utils import process_test_message


def test_invalid_cmd(ctx: ElroyConfig):
    response = process_test_message(ctx, "/foo")
    assert response is not None


def test_version_command_prints_version_and_exits(capsys) -> None:
    main(["version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__


def test_main_reexecs_process_when_app_requests_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    params = {
        "system_message_color": "blue",
        "assistant_color": "green",
        "user_input_color": "yellow",
        "warning_color": "red",
        "internal_thought_color": "magenta",
        "enable_assistant_greeting": False,
        "show_internal_thought": False,
    }
    exec_call: dict[str, Any] = {}

    @contextmanager
    def fake_init_elroy_session(ctx, *args, **kwargs):
        del ctx, args, kwargs
        yield object()

    class FakeApp:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def run(self):
            return AppRestartRequest("Restarted successfully. Ready to continue.")

    def fake_execvpe(path: str, argv: list[str], env: dict[str, str]) -> None:
        exec_call["path"] = path
        exec_call["argv"] = argv
        exec_call["env"] = env

    monkeypatch.setattr("elroy.core.logging.setup_file_logging", lambda: None)
    monkeypatch.setattr("elroy.cli.options.get_resolved_params", lambda: params)
    monkeypatch.setattr("elroy.core.ctx.ElroyConfig.init", lambda **_kwargs: object())
    monkeypatch.setattr("elroy.core.session.init_elroy_session", fake_init_elroy_session)
    monkeypatch.setattr("elroy.ui.app.ElroyApp", FakeApp)
    monkeypatch.setattr("elroy.ui.app._should_restart_as_module", lambda: True)
    monkeypatch.setattr("elroy.ui.app._source_tree_root", lambda: None)
    monkeypatch.setattr("elroy.ui.app._editable_install_root", lambda: None)
    monkeypatch.setattr("os.execvpe", fake_execvpe)
    monkeypatch.setattr("sys.orig_argv", ["python", "-m", "elroy", "--flag"], raising=False)
    monkeypatch.setattr("sys.argv", ["elroy", "--flag"])
    monkeypatch.setenv(RESTART_RESUME_MESSAGE_ENV, "stale message")

    main([])

    assert exec_call["path"] == sys.executable
    assert exec_call["argv"] == [sys.executable, "-m", "elroy", "--flag"]
    restart_env = exec_call["env"]
    assert isinstance(restart_env, dict)
    assert restart_env[RESTART_RESUME_MESSAGE_ENV] == "Restarted successfully. Ready to continue."


def test_main_reexecs_process_with_restart_pythonpath_from_source_root(monkeypatch: pytest.MonkeyPatch) -> None:
    params = {
        "system_message_color": "blue",
        "assistant_color": "green",
        "user_input_color": "yellow",
        "warning_color": "red",
        "internal_thought_color": "magenta",
        "enable_assistant_greeting": False,
        "show_internal_thought": False,
    }
    exec_call: dict[str, Any] = {}

    @contextmanager
    def fake_init_elroy_session(ctx, *args, **kwargs):
        del ctx, args, kwargs
        yield object()

    class FakeApp:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def run(self):
            return AppRestartRequest("Restarted successfully. Ready to continue.")

    def fake_execvpe(path: str, argv: list[str], env: dict[str, str]) -> None:
        exec_call["path"] = path
        exec_call["argv"] = argv
        exec_call["env"] = env

    monkeypatch.setattr("elroy.core.logging.setup_file_logging", lambda: None)
    monkeypatch.setattr("elroy.cli.options.get_resolved_params", lambda: params)
    monkeypatch.setattr("elroy.core.ctx.ElroyConfig.init", lambda **_kwargs: object())
    monkeypatch.setattr("elroy.core.session.init_elroy_session", fake_init_elroy_session)
    monkeypatch.setattr("elroy.ui.app.ElroyApp", FakeApp)
    monkeypatch.setattr("elroy.ui.app._should_restart_as_module", lambda: True)
    monkeypatch.setattr("elroy.ui.app._source_tree_root", lambda: None)
    monkeypatch.setattr("elroy.ui.app._editable_install_root", lambda: Path("/tmp/elroy-src"))
    monkeypatch.setattr("os.execvpe", fake_execvpe)
    monkeypatch.setattr("sys.orig_argv", ["python", "-m", "elroy"], raising=False)
    monkeypatch.setattr("sys.argv", ["elroy"])
    monkeypatch.setenv("PYTHONPATH", "/tmp/already-there")

    main([])

    restart_env = exec_call["env"]
    assert isinstance(restart_env, dict)
    assert restart_env["PYTHONPATH"] == f"/tmp/elroy-src{os.pathsep}/tmp/already-there"


def test_main_reexecs_process_with_installed_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    params = {
        "system_message_color": "blue",
        "assistant_color": "green",
        "user_input_color": "yellow",
        "warning_color": "red",
        "internal_thought_color": "magenta",
        "enable_assistant_greeting": False,
        "show_internal_thought": False,
    }
    exec_call: dict[str, Any] = {}

    @contextmanager
    def fake_init_elroy_session(ctx, *args, **kwargs):
        del ctx, args, kwargs
        yield object()

    class FakeApp:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def run(self):
            return AppRestartRequest("Restarted successfully. Ready to continue.")

    def fake_execvpe(path: str, argv: list[str], env: dict[str, str]) -> None:
        exec_call["path"] = path
        exec_call["argv"] = argv
        exec_call["env"] = env

    monkeypatch.setattr("elroy.core.logging.setup_file_logging", lambda: None)
    monkeypatch.setattr("elroy.cli.options.get_resolved_params", lambda: params)
    monkeypatch.setattr("elroy.core.ctx.ElroyConfig.init", lambda **_kwargs: object())
    monkeypatch.setattr("elroy.core.session.init_elroy_session", fake_init_elroy_session)
    monkeypatch.setattr("elroy.ui.app.ElroyApp", FakeApp)
    monkeypatch.setattr("elroy.ui.app._should_restart_as_module", lambda: False)
    monkeypatch.setattr("elroy.ui.app._source_tree_root", lambda: None)
    monkeypatch.setattr("elroy.ui.app._editable_install_root", lambda: None)
    monkeypatch.setattr("os.execvpe", fake_execvpe)
    monkeypatch.setattr("sys.orig_argv", ["elroy", "--flag", "--debug"], raising=False)
    monkeypatch.setattr("sys.argv", ["elroy", "--flag", "--debug"])
    monkeypatch.setenv(RESTART_RESUME_MESSAGE_ENV, "stale message")

    main([])

    assert exec_call["path"] == "elroy"
    assert exec_call["argv"] == ["elroy", "--flag", "--debug"]
    restart_env = exec_call["env"]
    assert isinstance(restart_env, dict)
    assert restart_env[RESTART_RESUME_MESSAGE_ENV] == "Restarted successfully. Ready to continue."
