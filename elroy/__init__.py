__version__ = "0.0.76"


import os

from importlib_resources import files

from .config.logging import setup_logging

PACKAGE_ROOT = files(__package__)


# Pydantic warnings for some envs


setup_logging()

os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "http://localhost:6006"
# Set Phoenix to quiet mode to suppress startup logs
os.environ["PHOENIX_QUIET"] = "true"
from phoenix.otel import register

tracer = register(
    project_name="elroy",
    auto_instrument=True,  # Default is 'default'  # See 'Trace all calls made to a library' below
    verbose=False,
    set_global_tracer_provider=True,  # Prevent "Overriding of current TracerProvider is not allowed" error
).get_tracer(__name__)
