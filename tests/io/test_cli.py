from tests.utils import MockCliIO

from elroy.io.cli import CliIO
from elroy.llm.stream_parser import SystemInfo


def test_empty_output(rich_formatter):
    io = CliIO(rich_formatter, show_internal_thought=False, show_memory_panel=True)
    io.print_stream(iter([]))


def test_non_empty_output(io: MockCliIO):
    io.print_stream(iter([SystemInfo(content="Hello, world!")]))
    assert io.get_sys_messages() == "Hello, world!"
