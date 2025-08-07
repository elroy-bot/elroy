from docstring_parser import parse

from elroy.api.main import Elroy
from mcp.server.fastmcp import FastMCP

ai = Elroy()

mcp = FastMCP("Elroy")
for fn in [
    ai.create_memory,
    ai.query_memory,
]:
    mcp.add_tool(fn, description=parse(fn.__doc__).description)  # type: ignore


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    mcp.run(transport="stdio")
