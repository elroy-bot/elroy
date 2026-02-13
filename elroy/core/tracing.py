import os
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, ParamSpec, TypeVar

from ..config.env_vars import is_tracing_enabled
from .logging import get_logger

T = TypeVar("T")
P = ParamSpec("P")

logger = get_logger()


class NoOpTracer:
    """A no-op tracer that mimics the Phoenix tracer interface but does nothing."""

    def chain(self, func: Callable[P, T]) -> Callable[P, T]:
        """No-op decorator that just returns the original function."""
        return func

    def agent(self, func: Callable[P, T]) -> Callable[P, T]:
        """No-op decorator that just returns the original function."""
        return func

    def tool(self, func: Callable[P, T]) -> Callable[P, T]:
        return func

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Return a no-op function for any attribute access."""

        def noop(*args: Any, **kwargs: Any) -> None:
            pass

        return noop


@contextmanager
def noop_using_user(user_token: str):
    """No-op context manager for user token."""
    yield user_token


if is_tracing_enabled():
    try:
        from openinference import instrumentation  # type: ignore
        from phoenix.otel import register  # type: ignore

        logger.info("Enabling tracing")
        tracer = register(
            project_name=os.environ.get("ELROY_TRACING_APP_NAME", "elroy"),
            protocol="http/protobuf",
            auto_instrument=False,
            verbose=False,
            set_global_tracer_provider=True,
        ).get_tracer(__name__)

        using_user = instrumentation.using_user
    except ImportError:
        logger.warning('Phoenix package not installed. Tracing will be disabled. To enable tracing: uv install "elroy[tracing]"')

        tracer = NoOpTracer()
        using_user = noop_using_user
else:
    tracer = NoOpTracer()
    using_user = noop_using_user
