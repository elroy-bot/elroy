import re

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from pydantic import BaseModel

from ..core.constants import RecoverableToolError, tool

DEFAULT_MAX_SEARCH_RESULTS = 5
DEFAULT_MAX_PAGE_CHARS = 8000
_REQUEST_TIMEOUT = 15


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchResults(BaseModel):
    query: str
    results: list[SearchResult]


class PageContent(BaseModel):
    url: str
    title: str
    text: str
    truncated: bool


@tool
def web_search(query: str, max_results: int = DEFAULT_MAX_SEARCH_RESULTS) -> SearchResults:
    """Search the web using DuckDuckGo and return a list of results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5, max 20).
    """
    if not query.strip():
        raise RecoverableToolError("query must not be empty")
    max_results = min(max(1, max_results), 20)
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        raise RecoverableToolError(f"Search failed: {e}") from e

    results = [SearchResult(title=r.get("title", ""), url=r.get("href", ""), snippet=r.get("body", "")) for r in raw]
    return SearchResults(query=query, results=results)


@tool
def fetch_page(url: str, max_chars: int = DEFAULT_MAX_PAGE_CHARS) -> PageContent:
    """Fetch a web page and return its readable text content.

    Args:
        url: The URL to fetch.
        max_chars: Maximum number of characters to return (default 8000).
    """
    if not url.strip():
        raise RecoverableToolError("url must not be empty")
    max_chars = min(max(100, max_chars), 50_000)
    try:
        resp = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Elroy/1.0)"},
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout as e:
        raise RecoverableToolError(f"Request timed out: {url}") from e
    except requests.exceptions.HTTPError as e:
        raise RecoverableToolError(f"HTTP error {e.response.status_code}: {url}") from e
    except requests.exceptions.RequestException as e:
        raise RecoverableToolError(f"Failed to fetch {url}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    truncated = len(text) > max_chars
    return PageContent(url=url, title=title, text=text[:max_chars], truncated=truncated)
