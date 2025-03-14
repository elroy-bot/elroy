import os
from typing import Any, Callable, TypeVar

from .constants import ELROY_ENABLE_TRACING
from .logging import get_logger

T = TypeVar("T")

logger = get_logger()


class NoOpTracer:
    """A no-op tracer that mimics the Phoenix tracer interface but does nothing."""

    def chain(self, func: Callable[..., T]) -> Callable[..., T]:
        """No-op decorator that just returns the original function."""
        return func

    def tool(self, func: Callable[..., T]) -> Callable[..., T]:
        return func

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Return a no-op function for any attribute access."""

        def noop(*args: Any, **kwargs: Any) -> None:
            pass

        return noop


if os.environ.get(ELROY_ENABLE_TRACING, "").lower() in ("1", "true", "yes"):
    from phoenix.otel import register

    logger.info("Enabling tracing")

    tracer = register(
        project_name=os.environ.get("ELROY_TRACING_APP_NAME", "elroy"),
        auto_instrument=True,
        verbose=False,
        set_global_tracer_provider=True,
    ).get_tracer(__name__)
else:
    tracer = NoOpTracer()
