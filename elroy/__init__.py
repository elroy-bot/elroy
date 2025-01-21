__version__ = "0.0.62"

from importlib_resources import files

PACKAGE_ROOT = files(__package__)

import warnings

# Pydantic warnings for some envs
warnings.filterwarnings("ignore", message="Valid config keys have changed in V2")
