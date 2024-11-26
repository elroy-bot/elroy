import os
from enum import Enum
from typing import Any, Optional

from click import get_current_context
from typer import Option

from ..config.config import load_defaults


class OptionSource(Enum):
    CLI = "cli"
    ENV = "env"
    CONFIG = "config"
    DEFAULT = "default"


def get_option_value(param_name: str, env_var: Optional[str], yaml_key: str, default: Any = None) -> Any:
    """
    Gets option value following precedence:
    1. CLI flag
    2. Environment variable
    3. Config file
    4. defaults.yml
    """
    ctx = get_current_context()
    
    # Check if set via CLI flag
    param_source = ctx.get_parameter_source(param_name)
    if param_source == ctx.get_parameter_source.COMMANDLINE:
        return ctx.params.get(param_name)
        
    # Check environment variable
    if env_var and env_var in os.environ:
        return os.environ[env_var]
        
    # Check config file
    config_file = ctx.params.get("config_file")
    if config_file:
        # TODO: Implement config file loading
        pass
        
    # Finally check defaults
    defaults = load_defaults()
    return defaults.get(yaml_key, default)


def ElroyOption(*args: Any, yaml_key: str, envvar: Optional[str] = None, **kwargs: Any) -> Any:
    """
    Creates a typer Option with value priority:
    1. CLI provided value
    2. Environment variable value
    3. User config file value
    4. defaults.yml value
    """
    def get_default():
        return get_option_value(kwargs.get("param_name", ""), envvar, yaml_key)

    return Option(*args, default_factory=get_default, envvar=envvar, **kwargs)
