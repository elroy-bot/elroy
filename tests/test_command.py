from elroy import __version__
from elroy.core.ctx import ElroyContext
from elroy.io.textual_app import main

from .utils import process_test_message


def test_invalid_cmd(ctx: ElroyContext):
    response = process_test_message(ctx, "/foo")
    assert response is not None


def test_version_command_prints_version_and_exits(capsys) -> None:
    main(["version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__
