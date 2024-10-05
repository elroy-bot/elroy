from contextlib import contextmanager
from functools import partial
from time import time
from typing import Callable, ContextManager, Optional

from toolz import pipe

watermarks = {}


def get_watermark_seconds(watermark_key: str, user_id: int) -> int:
    global watermarks

    return pipe(
        user_id,
        lambda _: watermark_key + "/" + str(_),
        watermarks.get,
        lambda _: int(_) if _ is not None else 0,
    )


def set_watermark_seconds(watermark_key: str, user_id: int, value_seconds: Optional[int] = None) -> None:
    global watermarks

    key = watermark_key + "/" + str(user_id)
    watermarks[key] = value_seconds or int(time())


def epoch_sec_watermark(func: Callable[[int, int], object]) -> Callable[[int], ContextManager]:
    @contextmanager
    def wrapper(user_id: int):
        try:

            if "__name__" in dir(func):
                watermark_key = func.__name__
            elif "func" in dir(func):
                watermark_key = getattr(func, "func").__name__
            else:
                raise ValueError("func does not have a name")

            assert isinstance(watermark_key, str)

            new_watermark = int(time())
            watermark = get_watermark_seconds(watermark_key, user_id)

            assert isinstance(watermark, int)

            result = func(user_id, watermark)
            yield result
            set_watermark_seconds(watermark_key, user_id, new_watermark)

        finally:
            pass

    return wrapper


set_context_watermark_seconds = partial(set_watermark_seconds, "elroy_context_watermark")
get_context_watermark_seconds = partial(get_watermark_seconds, "elroy_context_watermark")
