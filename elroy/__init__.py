__version__ = "0.0.76"

import os
import logging

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

tracer_provider = register(
    project_name="elroy",
    auto_instrument=True,  # Default is 'default'  # See 'Trace all calls made to a library' below
    verbose=False,
)
