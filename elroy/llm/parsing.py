import logging
import re
from typing import Tuple


def extract_title_and_body(response: str) -> Tuple[str, str]:
    """Extract title and body from markdown formatted response.

    Supports various markdown title formats:
    - # Title
    - #Title
    - ## Title
    - ###Title
    etc.

    Args:
        response: Markdown formatted string with title and body

    Returns:
        Tuple of (title, body)

    Raises:
        ValueError: If no valid title format is found
    """
    lines = response.strip().split("\n")
    if not lines:
        raise ValueError("Empty response")

    # Find first non-empty line
    title_line = next((line for line in lines if line.strip()), "")

    # Match any number of #s followed by optional space and title text

    title_match = re.match(r"^#+\s*(.+)$", title_line)

    if not title_match:
        logging.info("No title Markdown formatting found for title, accepting first line as title.")
        title = title_line.strip()

    else:
        title = title_match.group(1).strip()
    body = "\n".join(line for line in lines[1:] if line.strip()).strip()

    return (title, body)
