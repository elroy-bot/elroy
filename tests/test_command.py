from elroy.core.ctx import ElroyContext

from .utils import process_test_message


def test_invalid_cmd(ctx: ElroyContext):
    response = process_test_message(ctx, "/foo")
    assert response is not None
