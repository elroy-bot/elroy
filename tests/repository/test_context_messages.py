from functools import partial

from toolz import pipe
from toolz.curried import map, tail

from elroy.config.ctx import ElroyContext
from elroy.repository.context_messages.operations import add_context_message
from elroy.repository.context_messages.queries import get_context_messages
from elroy.utils.utils import run_in_background


def test_context_messages(george_ctx: ElroyContext):
    msgs = list(get_context_messages(george_ctx))

    # rm_1 = msgs[-1]
    # rm_2 = msgs[-2]
    # rm_3 = msgs[-3]

    # thread1 = run_in_background(add_context_message, george_ctx, msgs[-1])
    # thread2 = run_in_background(add_context_message, george_ctx, msgs[-2])
    # thread3 = run_in_background(add_context_message, george_ctx, msgs[-3])

    x = pipe(
        msgs,
        tail(3),
        map(partial(run_in_background, add_context_message, george_ctx)),
        list,
    )

    print(x)
