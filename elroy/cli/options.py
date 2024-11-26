from typing import Any

from typer import Option

from ..config.config import DEFAULT_CONFIG


def ElroyOption(*args: Any, yaml_key: str, **kwargs: Any) -> Any:
    """
    Creates a typer Option that reads its default from defaults.yml
    """

    return Option(*args, default=DEFAULT_CONFIG.get(yaml_key), show_default=True, **kwargs)
