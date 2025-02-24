import inspect

from docstring_parser import parse

from elroy.api import Elroy
from elroy.config.ctx import ElroyContext


def test_api_docstrings(ctx: ElroyContext):
    """Test that all methods on Elroy class have complete parameter documentation."""
    elroy = Elroy(database_url=ctx.db.url)

    for name, func in inspect.getmembers(elroy, predicate=inspect.ismethod):
        # Skip private methods
        if name.startswith("_"):
            continue

        # Get the function's parameters
        sig = inspect.signature(func)
        param_names = set(sig.parameters.keys()) - {"self"}

        # Parse the docstring
        docstring = inspect.getdoc(func)
        if not docstring:
            raise AssertionError(f"Function {name} has no docstring")

        parsed = parse(docstring)
        documented_params = {p.arg_name for p in parsed.params}

        # Check for missing parameter documentation
        missing_docs = param_names - documented_params
        if missing_docs:
            raise AssertionError(f"Function {name} is missing documentation for parameters: {missing_docs}")

        # Check for extra documented parameters
        extra_docs = documented_params - param_names
        if extra_docs:
            raise AssertionError(f"Function {name} has documentation for non-existent parameters: {extra_docs}")


def test_tool_docstrings(ctx: ElroyContext):
    """Test that all tools have complete parameter documentation."""
    for name, tool in ctx.tool_registry.tools.items():
        # Get the function's parameters
        sig = inspect.signature(tool)
        param_names = set(sig.parameters.keys()) - {"ctx"}

        # Parse the docstring
        docstring = inspect.getdoc(tool)
        if not docstring:
            raise AssertionError(f"Tool {name} has no docstring")

        parsed = parse(docstring)
        documented_params = {p.arg_name for p in parsed.params}

        # Check for missing parameter documentation
        missing_docs = param_names - documented_params
        if missing_docs:
            raise AssertionError(f"Tool {name} is missing documentation for parameters: {missing_docs}")

        # Check for extra documented parameters
        extra_docs = documented_params - param_names
        if extra_docs:
            raise AssertionError(f"Tool {name} has documentation for non-existent parameters: {extra_docs}")
