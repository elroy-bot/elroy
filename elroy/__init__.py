__version__ = "0.0.76"

import os

from importlib_resources import files

PACKAGE_ROOT = files(__package__)

import warnings

# Pydantic warnings for some envs
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")

import litellm
import phoenix as px
from openinference.instrumentation.litellm import LiteLLMInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "http://localhost:6006"
from phoenix.otel import register

tracer_provider = register(
    project_name="elroy", auto_instrument=True  # Default is 'default'  # See 'Trace all calls made to a library' below
)
