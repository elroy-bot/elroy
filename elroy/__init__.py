__version__ = "0.0.76"

# > /ask the bad output is coming from this traceback: ESC[0m  /opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/threading.py(1030)_bootstrap()
# . -> self._bootstrap_inner()ESC[0m
# . ESC[0m  /opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/threading.py(1073)_bootstrap_inner()
# . -> self.run()ESC[0m
# . ESC[0m  /opt/homebrew/Cellar/python@3.12/3.12.4/Frameworks/Python.framework/Versions/3.12/lib/python3.12/threading.py(1010)run()
# . -> self._target(*self._args, **self._kwargs)ESC[0m
# . ESC[0m  /Users/tombedor/development/elroy/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/export/__init__.py(270)worker()
# . -> self._export(flush_request)ESC[0m
# . ESC[0m  /Users/tombedor/development/elroy/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/export/__init__.py(335)_export()
# . -> self._export_batch()ESC[0m
# . ESC[0m  /Users/tombedor/development/elroy/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/export/__init__.py(360)_export_batch()
# . -> self.span_exporter.export(self.spans_list[:idx])  # type: ignoreESC[0m
# . ESC[0m  /Users/tombedor/development/elroy/.venv/lib/python3.12/site-packages/opentelemetry/sdk/trace/export/__init__.py(512)export()
# . -> self.out.write(self.formatter(span))ESC[0m
# . ESC[0m> /Users/tombedor/development/elroy/elroy/__init__.py(31)write()
# . -> self.log_file.write(message)ESC[0m
# . ESC[0m


import sys
import io
import os
from pathlib import Path

# Create log directory
log_dir = Path.home() / ".cache" / "elroy" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# Create log files
stdout_log = open(log_dir / "stdout_capture.log", "a")
stderr_log = open(log_dir / "stderr_capture.log", "a")

# Save original stdout and stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

# Create custom stdout and stderr replacements
class TeeOutput:
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file

    def write(self, message):

        if "raw_gen_ai_request" in message:
            import pdb; pdb.set_trace()
        self.log_file.write(message)
        self.log_file.flush()
        # Optionally write to original too
        # self.original.write(message)

    def flush(self):
        self.log_file.flush()
        self.original.flush()

    def __getattr__(self, attr):
        return getattr(self.original, attr)

# # Replace stdout and stderr
# sys.stdout = TeeOutput(original_stdout, stdout_log)
# sys.stderr = TeeOutput(original_stderr, stderr_log)


import logging
import os

from importlib_resources import files

from .config.logging import setup_logging

PACKAGE_ROOT = files(__package__)

import warnings

# Pydantic warnings for some envs


setup_logging()

import litellm
import phoenix as px
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "http://localhost:6006"
# Set Phoenix to quiet mode to suppress startup logs
os.environ["PHOENIX_QUIET"] = "true"
from phoenix.otel import register

tracer = register(
    project_name="elroy",
    auto_instrument=True,  # Default is 'default'  # See 'Trace all calls made to a library' below
    verbose=False,
    set_global_tracer_provider=False,  # Prevent "Overriding of current TracerProvider is not allowed" error
).get_tracer(__name__)
