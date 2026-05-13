from pathlib import Path

from elroy.io.prompt_history import PromptHistoryStore


def test_prompt_history_filters_out_slash_commands(tmp_path: Path) -> None:
    history_path = tmp_path / "prompt_history.txt"
    history_path.write_text("+hello there\n+/set_assistant_name Jarvis\n+what next\n")

    store = PromptHistoryStore(history_path)

    assert store.load() == ["what next", "hello there"]


def test_prompt_history_does_not_persist_slash_commands(tmp_path: Path) -> None:
    history_path = tmp_path / "prompt_history.txt"
    store = PromptHistoryStore(history_path)

    store.append("/set_assistant_name Jarvis")
    store.append("hello there")

    assert history_path.read_text() == "+hello there\n"
