from unittest.mock import MagicMock, patch

import pytest
import requests

from elroy.core.constants import RecoverableToolError
from elroy.tools.web import PageContent, SearchResult, SearchResults, fetch_page, web_search

_FAKE_SEARCH_RESULTS = [
    {"title": "Example Site", "href": "https://example.com", "body": "An example site."},
    {"title": "Another Site", "href": "https://another.com", "body": "Another site snippet."},
]


def _make_mock_ddgs(results=_FAKE_SEARCH_RESULTS):
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = MagicMock(return_value=results)
    return mock_ddgs


def _make_mock_response(text: str, status_code: int = 200, title: str = "Test Page"):
    html = f"<html><head><title>{title}</title></head><body><p>{text}</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# --- web_search ---


def test_web_search_returns_results():
    mock_ddgs = _make_mock_ddgs()
    with patch("elroy.tools.web.DDGS", return_value=mock_ddgs):
        result = web_search("python testing")

    assert isinstance(result, SearchResults)
    assert result.query == "python testing"
    assert len(result.results) == 2
    assert isinstance(result.results[0], SearchResult)
    assert result.results[0].title == "Example Site"
    assert result.results[0].url == "https://example.com"
    assert result.results[0].snippet == "An example site."


def test_web_search_passes_max_results_to_ddgs():
    mock_ddgs = _make_mock_ddgs(results=[_FAKE_SEARCH_RESULTS[0]])
    with patch("elroy.tools.web.DDGS", return_value=mock_ddgs):
        web_search("python", max_results=3)

    mock_ddgs.text.assert_called_once_with("python", max_results=3)


def test_web_search_clamps_max_results_to_20():
    mock_ddgs = _make_mock_ddgs(results=[])
    with patch("elroy.tools.web.DDGS", return_value=mock_ddgs):
        web_search("python", max_results=100)

    mock_ddgs.text.assert_called_once_with("python", max_results=20)


def test_web_search_clamps_max_results_minimum_to_1():
    mock_ddgs = _make_mock_ddgs(results=[])
    with patch("elroy.tools.web.DDGS", return_value=mock_ddgs):
        web_search("python", max_results=0)

    mock_ddgs.text.assert_called_once_with("python", max_results=1)


def test_web_search_empty_query_raises():
    with pytest.raises(RecoverableToolError, match="query must not be empty"):
        web_search("   ")


def test_web_search_ddgs_error_raises_recoverable():
    mock_ddgs = _make_mock_ddgs()
    mock_ddgs.text.side_effect = RuntimeError("rate limited")
    with patch("elroy.tools.web.DDGS", return_value=mock_ddgs), pytest.raises(RecoverableToolError, match="Search failed"):
        web_search("python")


def test_web_search_handles_empty_results():
    mock_ddgs = _make_mock_ddgs(results=[])
    with patch("elroy.tools.web.DDGS", return_value=mock_ddgs):
        result = web_search("xyzzy obscure query")

    assert result.results == []


# --- fetch_page ---


def test_fetch_page_returns_text():
    with patch("elroy.tools.web.requests.get", return_value=_make_mock_response("Hello world")):
        result = fetch_page("https://example.com")

    assert isinstance(result, PageContent)
    assert result.url == "https://example.com"
    assert result.title == "Test Page"
    assert "Hello world" in result.text
    assert result.truncated is False


def test_fetch_page_strips_script_and_style_tags():
    html = (
        "<html><head><title>T</title><style>body{color:red}</style></head><body><script>alert(1)</script><p>Real content</p></body></html>"
    )
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("elroy.tools.web.requests.get", return_value=mock_resp):
        result = fetch_page("https://example.com")

    assert "alert" not in result.text
    assert "color:red" not in result.text
    assert "Real content" in result.text


def test_fetch_page_truncates_at_max_chars():
    long_text = "word " * 10_000
    mock_resp = MagicMock()
    mock_resp.text = f"<html><head><title>T</title></head><body><p>{long_text}</p></body></html>"
    mock_resp.raise_for_status = MagicMock()

    with patch("elroy.tools.web.requests.get", return_value=mock_resp):
        result = fetch_page("https://example.com", max_chars=500)

    assert len(result.text) <= 500
    assert result.truncated is True


def test_fetch_page_not_truncated_when_short():
    with patch("elroy.tools.web.requests.get", return_value=_make_mock_response("Short")):
        result = fetch_page("https://example.com", max_chars=8000)

    assert result.truncated is False


def test_fetch_page_empty_url_raises():
    with pytest.raises(RecoverableToolError, match="url must not be empty"):
        fetch_page("   ")


def test_fetch_page_timeout_raises_recoverable():
    with (
        patch("elroy.tools.web.requests.get", side_effect=requests.exceptions.Timeout()),
        pytest.raises(RecoverableToolError, match="Request timed out"),
    ):
        fetch_page("https://example.com")


def test_fetch_page_http_error_raises_recoverable():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    http_err = requests.exceptions.HTTPError(response=mock_resp)
    with patch("elroy.tools.web.requests.get", side_effect=http_err), pytest.raises(RecoverableToolError, match="HTTP error 404"):
        fetch_page("https://example.com")


def test_fetch_page_connection_error_raises_recoverable():
    with (
        patch("elroy.tools.web.requests.get", side_effect=requests.exceptions.ConnectionError("refused")),
        pytest.raises(RecoverableToolError, match="Failed to fetch"),
    ):
        fetch_page("https://example.com")


def test_fetch_page_title_empty_when_missing():
    html = "<html><body><p>No title here</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("elroy.tools.web.requests.get", return_value=mock_resp):
        result = fetch_page("https://example.com")

    assert result.title == ""
