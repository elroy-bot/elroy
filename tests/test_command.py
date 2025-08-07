import re

from elroy.cli.chat import process_and_deliver_msg
from elroy.core.constants import USER
from elroy.core.ctx import ElroyContext

from .utils import MockCliIO


def test_invalid_cmd(io: MockCliIO, ctx: ElroyContext):
    process_and_deliver_msg(
        io,
        USER,
        ctx,
        "/foo",
    )
    response = io.get_sys_messages()
    assert re.search(r"Invalid.*foo.*help", response) is not None
