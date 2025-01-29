import inspect
import os
import shutil
import subprocess
import sys
from typing import Any, Dict

from toolz import pipe
from toolz.curried import assoc, dissoc, itemfilter, keymap, valfilter, valmap

from ..api import Elroy
from ..cli.options import get_env_var_name
from ..config.ctx import ElroyContext
from ..config.paths import get_home_dir


def get_mcp_config(local: bool, ctx: ElroyContext) -> Dict[str, Any]:
    args = ["run", "--with", "elroy", "--with", "mcp"]
    if local:
        args += ["--python", sys.executable]
    args += ["elroy_mcp"]

    return pipe(
        ctx,
        lambda ctx: vars(ctx.params),
        valfilter(lambda v: v is not None),
        keymap(get_env_var_name),
        itemfilter(lambda x: os.environ.get(x[0]) == x[1]),  # only include those env vars that are actually set in the user env
        lambda d: assoc(d, "ELROY_HOME", str(get_home_dir())),
        lambda d: dissoc(d, "ELROY_DEFAULT_PERSONA"),
        valmap(str),
        lambda d: {
            "mcpServers": {
                "elroy": {
                    "command": "uv",
                    "args": args,
                    "disabled": False,
                    "autoApprove": [t[0] for t in inspect.getmembers(Elroy, predicate=inspect.isfunction) if not t[0].startswith("_")],
                    "env": d,
                },
            },
        },
    )


def is_uv_installed():
    # Method 1: Check if uv exists in PATH
    uv_in_path = shutil.which("uv") is not None

    # Method 2: Try running uv --version
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        uv_runs = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        uv_runs = False

    return uv_in_path and uv_runs
