from typing import Any, Optional

from typer import Option

from ..config.config import DEFAULT_CONFIG


def ElroyOption(*args: Any, yaml_key: str, envvar: Optional[str] = None, **kwargs: Any) -> Any:
    """
    Creates a typer Option that reads its default from defaults.yml
    """

    if not envvar:
        envvar = "ELROY_" + yaml_key.upper()

    return Option(*args, default=DEFAULT_CONFIG.get(yaml_key), envvar=envvar, show_default=True, **kwargs)
