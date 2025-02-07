import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Generator, Iterator, List, Optional
from urllib.parse import urlparse, urlunparse

from sqlmodel import select

from ..memories.operations import do_create_memory

from ...config.constants import ASSISTANT, USER, tool
from ...config.ctx import ElroyContext
from ...config.llm import ChatModel
from ...db.db_models import DocumentExcerpt, SourceDocument
from ...llm.client import query_llm
from ...utils.clock import get_utc_now
from ..embeddings import upsert_embedding_if_needed
from .web_scraper import Scraper

CONVERT_TO_TEXT_PRIMER = [
    {
        "role": USER,
        "content": """<!---
Copyright 2024 The HuggingFace Team. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
<p align="center">
    <!-- Uncomment when CircleCI is set up
    <a href="https://circleci.com/gh/huggingface/accelerate"><img alt="Build" src="https://img.shields.io/circleci/build/github/huggingface/transformers/master"></a>
    -->
    <a href="https://github.com/huggingface/smolagents/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/huggingface/smolagents.svg?color=blue"></a>
    <a href="https://huggingface.co/docs/smolagents"><img alt="Documentation" src="https://img.shields.io/website/http/huggingface.co/docs/smolagents/index.html.svg?down_color=red&down_message=offline&up_message=online"></a>
    <a href="https://github.com/huggingface/smolagents/releases"><img alt="GitHub release" src="https://img.shields.io/github/release/huggingface/smolagents.svg"></a>
    <a href="https://github.com/huggingface/smolagents/blob/main/CODE_OF_CONDUCT.md"><img alt="Contributor Covenant" src="https://img.shields.io/badge/Contributor%20Covenant-v2.0%20adopted-ff69b4.svg"></a>
</p>

<h3 align="center">
  <div style="display:flex;flex-direction:row;">
    <img src="https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/smolagents/mascot.png" alt="Hugging Face mascot as James Bond" width=100px>
    <p>smolagents - a smol library to build great agents!</p>
  </div>
</h3>

`smolagents` is a library that enables you to run powerful agents in a few lines of code. It offers:

✨ **Simplicity**: the logic for agents fits in 1,000 lines of code (see [agents.py](https://github.com/huggingface/smolagents/blob/main/src/smolagents/agents.py)). We kept abstractions to their minimal shape above raw code!

🧑‍💻 **First-class support for Code Agents**. Our [`CodeAgent`](https://huggingface.co/docs/smolagents/reference/agents#smolagents.CodeAgent) writes its actions in code (as opposed to "agents being used to write code"). To make it secure, we support executing in sandboxed environments via [E2B](https://e2b.dev/).

🤗 **Hub integrations**: you can [share/pull tools to/from the Hub](https://huggingface.co/docs/smolagents/reference/tools#smolagents.Tool.from_hub), and more is to come!""",
    },
    {
        "role": ASSISTANT,
        "content": """smolagents - a smol library to build great agents!

Key features:
1. Simplicity: The entire agents logic is contained in 1,000 lines of code (in agents.py)
2. First-class support for Code Agents: Uses CodeAgent that writes actions in code, with secure execution support via E2B sandboxed environments
3. Hub integrations: Ability to share and pull tools to/from the Hub

The library is:
- Licensed under Apache License 2.0
- Has documentation available at huggingface.co/docs/smolagents
- Follows the Contributor Covenant v2.0
- Available on GitHub at huggingface/smolagents""",
    },
]


@dataclass
class DocumentChunk:
    address: str
    content: str
    chunk_index: int


def convert_to_text(chat_model: ChatModel, content: str) -> str:
    return query_llm(
        system="Your task is to convert the following text into plain text. You should NOT summarize content, "
        "but rather convert it into plain text. That is, the information in the output should be the same as the information in the input.",
        model=chat_model,
        prompt=content,
        primer_messages=CONVERT_TO_TEXT_PRIMER,
    )


def get_title(chat_model: ChatModel, content: str) -> str:
    return query_llm(
        system="Given a text excerpt from a document, your task is to come up with a title for the document."
        "If the title mentions dates, it should be specific dates rather than relative ones."
        "The title should be in plain text, without any Markdown or HTML formatting.",
        model=chat_model,
        prompt=content,
    )


@tool
def scrape_doc(ctx: ElroyContext, address: str) -> str:
    """Downloads the url, and extracts content from it into memory

    Args:
        address (str): The URL to scrape
    """
    if is_github_repo_file(address):
        parse_result = urlparse(address)

        address = urlunparse(
            (
                parse_result.scheme,
                "raw.githubusercontent.com",
                parse_result.path.replace("blob", "refs/heads"),
                parse_result.params,
                parse_result.query,
                parse_result.fragment,
            )
        )

    source_doc = get_source_doc_by_address(ctx, address)

    try:
        error = None
        content = Scraper().scrape(address)
        assert content
        content_md5 = hashlib.md5(content.encode()).hexdigest()

    except Exception as e:
        error = str(e)
        content = None
        content_md5 = None

    if source_doc and source_doc.content_md5 == content_md5:
        logging.info("Content has not changed, skipping")

    source_doc = get_source_doc_by_address(ctx, address)
    if source_doc:
        source_doc.content = content
        source_doc.extraction_error = error
        source_doc.extracted_at = get_utc_now()
        source_doc.content_md5 = content_md5
    else:
        source_doc = SourceDocument(
            user_id=ctx.user_id,
            address=address,
            name=address,
            content=content,
            extraction_error=error,
            content_md5=content_md5,
            extracted_at=get_utc_now(),
        )

    ctx.db.add(source_doc)

    ctx.db.commit()

    if error:
        return f"Error extracting content from {address}: {error}"
    if not content:
        return f"Content not found at {address}"

    for excerpt in get_document_excerpts(ctx, source_doc):
        excerpt.is_active = False
        ctx.db.add(excerpt)

    chunk_count = 0

    for chunk in chunk_doc(address, content):
        chunk_count += 1
        if not chunk.content:
            continue
        content = convert_to_text(ctx.chat_model, chunk.content)
        content_md5 = hashlib.md5(content.encode()).hexdigest()
        source_doc_id = source_doc.id
        assert source_doc_id

        doc_excerpt = DocumentExcerpt(
            source_document_id=source_doc_id,
            name=get_title(ctx.chat_model, content),
            user_id=ctx.user_id,
            content=content,
            content_md5=content_md5,
            chunk_index=chunk.chunk_index,
            is_active=True,
        )
        ctx.db.add(doc_excerpt)
        ctx.db.commit()
        ctx.db.refresh(doc_excerpt)
        upsert_embedding_if_needed(ctx, doc_excerpt)

        do_create_memory(ctx, doc_excerpt.name, doc_excerpt.content, [doc_excerpt])
    return f"Ingested doc with {chunk_count} chunks"


def get_source_doc_by_address(ctx: ElroyContext, address: str) -> Optional[SourceDocument]:
    ctx.db.exec(select(SourceDocument).where(SourceDocument.address == address)).one_or_none()


def get_document_excerpts(ctx: ElroyContext, source_doc: SourceDocument) -> List[DocumentExcerpt]:
    return list(
        ctx.db.exec(
            select(DocumentExcerpt).where(DocumentExcerpt.source_document_id == source_doc.id).where(DocumentExcerpt.is_active == True)
        ).all()
    )


def chunk_doc(address: str, content: str) -> Generator[DocumentChunk, Any, None]:
    if is_markdown(address):
        yield from chunk_markdown(address, content)
    else:
        raise NotImplementedError


def is_github_repo_file(url: str) -> bool:
    return "github.com" in url and "blob" in url


def is_markdown(url: str) -> bool:
    return url.endswith(".md") or url.endswith(".markdown")


def chunk_markdown(address: str, content: str, max_chars: int = 3000, overlap: int = 200) -> Iterator[DocumentChunk]:
    # Split on markdown headers or double newlines
    splits = re.split(r"(#{1,6}\s.*?\n|(?:\n\n))", content)

    last_emitted_chunk = None

    current_chunk = ""

    for split in splits:
        if len(current_chunk) + len(split) < max_chars:
            current_chunk += split
        else:
            if last_emitted_chunk and overlap:
                current_chunk = last_emitted_chunk.content[:-overlap] + current_chunk
            last_emitted_chunk = DocumentChunk(address, current_chunk, last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0)
            yield last_emitted_chunk
            current_chunk = ""
    if current_chunk and overlap and last_emitted_chunk:
        current_chunk = last_emitted_chunk.content[-overlap:] + current_chunk
    yield DocumentChunk(address, current_chunk, last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0)


def resolve(url):
    if is_github_repo_file(url):
        # return URL
        url = "https://raw.githubusercontent.com/" + url.split("/blob/")[1]
    return url
