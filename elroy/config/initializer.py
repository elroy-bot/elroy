import atexit
import io
import logging
import sys
import traceback
import uuid
from contextlib import contextmanager

from ..io.base import ElroyIO
from ..io.cli import CliIO
from .ctx import ElroyContext


class StdoutTracer(io.TextIOBase):
    def __init__(self, original, log_file_path):
        super().__init__()
        self.original = original
        self.log_file = open(log_file_path, "a")  # Open your log file in append mode
        
        # Register cleanup function to ensure log file is closed on exit
        atexit.register(self.close)

    def write(self, message):
        # Capture stack trace and get the latest frame where the print originated
        stack = traceback.extract_stack()
        # Adjust the index to get the correct frame (might be -3 or -4 based on the callstack)
        log_frame = stack[-3]

        # Get information from the frame
        filename = log_frame.filename
        lineno = log_frame.lineno
        function_name = log_frame.name

        # Format trace information
        trace_info = f"Trace from {filename}, line {lineno}, in {function_name}:{message.strip()}\n"

        # Write trace information to the log file
        self.log_file.write(trace_info)

        # Also write the message to the original stdout
        self.original.write(message)
        
        return len(message)

    def flush(self):
        self.original.flush()
        self.log_file.flush()

    def close(self):
        if not self.log_file.closed:
            self.log_file.close()

    def isatty(self):
        return self.original.isatty()
        
    def fileno(self):
        return self.original.fileno()
        
    def seekable(self):
        return self.original.seekable()
        
    def readable(self):
        return self.original.readable()
        
    def writable(self):
        return self.original.writable()
        
    def __getattr__(self, name):
        # Delegate any other methods to the original stdout
        return getattr(self.original, name)


# Set the tracer and specify your log file path
sys.stdout = StdoutTracer(sys.stdout, "stdout_trace.log")


@contextmanager
def init_elroy_session(ctx: ElroyContext, io: ElroyIO, check_db_migration: bool, should_onboard_interactive: bool):
    from ..cli.chat import onboard_interactive, onboard_non_interactive
    from ..repository.user.queries import get_user_id_if_exists
    from ..tools.inline_tools import verify_inline_tool_call_instruct_matches_ctx

    try:
        if check_db_migration:
            ctx.db_manager.check_connection()
            ctx.db_manager.migrate_if_needed()

        session_id = str(uuid.uuid4())
        logging.info(f"OpenTelemetry instrumentation enabled with session ID: {session_id}")
        from openinference.instrumentation import using_session

        with using_session(session_id=session_id):
            import litellm

            litellm.callbacks = ["otel"]  # noqa F841

            with ctx.db_manager.open_session() as dbsession:
                ctx.set_db_session(dbsession)

                if not get_user_id_if_exists(dbsession, ctx.user_token):
                    if should_onboard_interactive and isinstance(io, CliIO):
                        onboard_interactive(io, ctx)
                    else:
                        onboard_non_interactive(ctx)

                verify_inline_tool_call_instruct_matches_ctx(ctx)

                yield

    finally:
        ctx.unset_db_session()


@contextmanager
def dbsession(ctx: ElroyContext):
    if ctx.is_db_connected():
        yield
    else:
        with ctx.db_manager.open_session() as dbsession:
            try:
                ctx.set_db_session(dbsession)
                yield
            finally:
                ctx.unset_db_session()
