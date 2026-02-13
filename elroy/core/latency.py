"""Latency tracking and performance instrumentation for Elroy."""

import functools
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .constants import allow_unused
from .logging import get_logger

logger = get_logger("latency")


@dataclass
class LatencyStats:
    """Statistics for a single operation."""

    operation: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    _timestamp: float = field(default_factory=time.time)  # For future use


@dataclass
class LatencyTracker:
    """Tracks latency across different operations in a request."""

    request_id: str
    stats: list[LatencyStats] = field(default_factory=list)
    start_time: float = field(default_factory=time.perf_counter)

    def track(self, operation: str, duration_ms: float, **metadata):
        """Record an operation's latency."""
        stat = LatencyStats(operation=operation, duration_ms=duration_ms, metadata=metadata)
        self.stats.append(stat)

        # Log if duration is significant (>100ms) or if configured
        if duration_ms > 100:
            logger.info(f"[{self.request_id}] {operation}: {duration_ms:.0f}ms {metadata}")
        else:
            logger.debug(f"[{self.request_id}] {operation}: {duration_ms:.0f}ms {metadata}")

    @contextmanager
    def measure(self, operation: str, **metadata):
        """Context manager to measure an operation."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.track(operation, duration_ms, **metadata)

    def get_total_duration_ms(self) -> float:
        """Get total duration since tracker creation."""
        return (time.perf_counter() - self.start_time) * 1000

    def summarize(self) -> str:
        """Generate a summary of all tracked operations."""
        total_ms = self.get_total_duration_ms()

        lines = [f"\n[{self.request_id}] Latency Summary (Total: {total_ms:.0f}ms)"]
        lines.append("=" * 80)

        # Group by operation type
        by_operation: dict[str, list[float]] = {}
        for stat in self.stats:
            if stat.operation not in by_operation:
                by_operation[stat.operation] = []
            by_operation[stat.operation].append(stat.duration_ms)

        # Sort by total time spent in each operation type
        sorted_ops = sorted(by_operation.items(), key=lambda x: sum(x[1]), reverse=True)

        for operation, durations in sorted_ops:
            count = len(durations)
            total = sum(durations)
            avg = total / count
            percentage = (total / total_ms * 100) if total_ms > 0 else 0

            lines.append(f"  {operation:30s} | count: {count:3d} | total: {total:6.0f}ms ({percentage:5.1f}%) | avg: {avg:6.0f}ms")

        lines.append("=" * 80)
        return "\n".join(lines)

    def log_summary(self):
        """Log the summary."""
        logger.info(self.summarize())


@allow_unused  # Utility function for future use
def track_latency(operation: str, **metadata):
    """Decorator to track function execution latency.

    Args:
        operation: Name of the operation being tracked
        **metadata: Additional metadata to log with the operation

    Example:
        @track_latency("db_query", table="memories")
        def get_memories():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000

                # Try to get tracker from context if available
                ctx = kwargs.get("ctx") or (args[0] if args and hasattr(args[0], "latency_tracker") else None)
                if ctx and hasattr(ctx, "latency_tracker") and ctx.latency_tracker:
                    ctx.latency_tracker.track(operation, duration_ms, **metadata)
                else:
                    # Fallback to direct logging
                    if duration_ms > 100:
                        logger.info(f"{operation}: {duration_ms:.0f}ms {metadata}")
                    else:
                        logger.debug(f"{operation}: {duration_ms:.0f}ms {metadata}")

                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(f"{operation}: {duration_ms:.0f}ms - Error: {str(e)}")
                raise

        return wrapper

    return decorator


@allow_unused  # Utility function for future use
def log_timing(operation: str):
    """Simple decorator that logs timing without context integration.

    Use this for quick timing measurements where you don't need
    full latency tracking integration.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info(f"{operation}: {duration_ms:.0f}ms")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(f"{operation}: {duration_ms:.0f}ms - Error: {str(e)}")
                raise

        return wrapper

    return decorator
