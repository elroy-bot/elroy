from pathlib import Path

from elroy.tools.filesystem import read_file


def test_read_file_coerces_string_line_numbers(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\ndelta")

    result = read_file("sample.txt", start_line="2", end_line="3")

    assert result.start_line == 2
    assert result.end_line == 3
    assert result.total_lines == 4
    assert result.truncated is True
    assert result.content == "2: beta\n3: gamma"
