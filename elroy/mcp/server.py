from docstring_parser import parse

from elroy.api import Elroy
from mcp.server.fastmcp import FastMCP

ai = Elroy()

mcp = FastMCP("Elroy")
for fn in [
    ai.create_memory,
    ai.query_memory,
    ai.create_goal,
    ai.add_goal_status_update,
    ai.mark_goal_completed,
    # fetching of goals more closely resembles the resource spec, but that seems pretty buggy.
    ai.get_active_goal_names,
    ai.get_goal_by_name,
]:
    mcp.add_tool(fn, description=parse(fn.__doc__).description)  # type: ignore


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    mcp.run(transport="stdio")
