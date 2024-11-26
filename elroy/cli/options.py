from typing import Any, Optional

from typer import Option

from ..config.config import load_defaults


def ElroyOption(*args: Any, yaml_key: str, **kwargs: Any) -> Any:
    """
    Creates a typer Option that reads its default from defaults.yml
    """
    def get_default():
        defaults = load_defaults()
        return defaults.get(yaml_key)

    return Option(*args, default_factory=get_default, **kwargs)
