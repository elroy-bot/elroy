import os
from pathlib import Path

import pytest
from tests import fixtures
from tests.utils import process_test_message

from elroy.config.ctx import ElroyContext
from elroy.repository.context_messages.operations import reset_messages
from elroy.repository.documents.operations import (
    DocIngestResult,
    do_ingest,
    do_ingest_dir,
)
from elroy.repository.documents.queries import get_source_docs
from elroy.repository.documents.tools import ingest_doc


def test_ingest_doc(ctx: ElroyContext, midnight_garden_md_path: str):
    ingest_doc(ctx, midnight_garden_md_path)
    reset_messages(ctx)

    response = process_test_message(ctx, "In the Midnight Garden, what was the name of the main character?")
    assert "clara" in response.lower()

    response = process_test_message(ctx, "What was the last sentence of the story, The Midnight Garden?")

    try:

        assert (
            """She knew that somewhere, perhaps even in her small town, there was another soul who would see the magic in her midnight garden and ensure its secrets would continue to flourish under the watchful eye of the moon."""
            in response
        )
    except AssertionError:
        print(response)
        raise


def test_ingest_doc_duplicate(ctx: ElroyContext, midnight_garden_md_path: Path):
    assert do_ingest(ctx, midnight_garden_md_path, False) == DocIngestResult.SUCCESS
    assert do_ingest(ctx, midnight_garden_md_path, False) == DocIngestResult.UNCHANGED
    assert do_ingest(ctx, midnight_garden_md_path, True) == DocIngestResult.UPDATED


def test_large_doc(ctx: ElroyContext, very_large_document_path: Path):
    assert do_ingest(ctx, very_large_document_path, False) == DocIngestResult.TOO_LONG


def test_recursive_dir_ingest(ctx: ElroyContext, test_docs_dir: Path):
    # Test recursive ingestion
    results = do_ingest_dir(ctx, test_docs_dir, force_refresh=False, recursive=True, include=["*.md"], exclude=["*.log"])

    # Should find all 3 markdown files (2 in root, 1 in subdir)
    assert results[DocIngestResult.SUCCESS] == 3

    # Verify txt file was not included due to include pattern
    assert not any(doc.address.endswith(".txt") for doc in get_source_docs(ctx))

    # Verify log file was excluded
    assert not any(doc.address.endswith(".log") for doc in get_source_docs(ctx))


def test_non_recursive_dir_ingest(ctx: ElroyContext, test_docs_dir: Path):
    # Test non-recursive ingestion
    results = do_ingest_dir(ctx, test_docs_dir, force_refresh=False, recursive=False, include=["*.md"], exclude=[])

    # Should only find 2 markdown files in root dir
    assert results[DocIngestResult.SUCCESS] == 2

    # Verify no files from subdirectory were ingested
    assert not any("subdir" in doc.address for doc in get_source_docs(ctx))


def test_dir_ingest_exclude_patterns(ctx: ElroyContext, test_docs_dir: Path):
    # Test exclude patterns
    results = do_ingest_dir(
        ctx,
        test_docs_dir,
        force_refresh=False,
        recursive=True,
        include=[],  # No include filter
        exclude=["**/subdir/*", "*.txt"],  # Exclude subdir and txt files
    )

    # Should only find 2 markdown files from root
    assert results[DocIngestResult.SUCCESS] == 2

    # Verify excluded patterns worked
    docs = list(get_source_docs(ctx))
    assert not any("subdir" in doc.address for doc in docs)
    assert not any(doc.address.endswith(".txt") for doc in docs)


@pytest.fixture
def test_docs_dir(tmpdir: str) -> Path:
    """Create a temporary directory with test documents"""
    docs_dir = Path(os.path.join(tmpdir, "test_docs"))
    docs_dir.mkdir(exist_ok=True)

    # Create some markdown files
    (docs_dir / "doc1.md").write_text("# Test Document 1\nThis is a test document.")
    (docs_dir / "doc2.md").write_text("# Test Document 2\nThis is another test document.")

    # Create a text file
    (docs_dir / "notes.txt").write_text("Some plain text notes\nMore notes here.")

    # Create a subdirectory with more files
    subdir = docs_dir / "subdir"
    subdir.mkdir(exist_ok=True)
    (subdir / "doc3.md").write_text("# Test Document 3\nThis is in a subdirectory.")
    (subdir / "excluded.log").write_text("This should be excluded")

    return docs_dir


@pytest.fixture(scope="session")
def very_large_document_path(tmpdir: str) -> Path:
    # Create a temporary directory for our large document
    file_path = os.path.join(tmpdir, "large_document.txt")

    # Create content that will exceed 8k tokens
    paragraphs = []
    topics = ["AI", "Machine Learning", "Data Science", "Programming", "Software Engineering"]

    for i in range(100):  # Generate 100 variations of paragraphs
        for topic in topics:
            paragraph = f"""
            Chapter {i+1}: Advanced {topic} Concepts

            In the evolving landscape of {topic.lower()}, practitioners must constantly adapt to new methodologies
            and frameworks. The fundamental principles of {topic.lower()} remain consistent, yet their applications
            continue to expand in unexpected ways. Recent developments in {topic.lower()} have shown promising
            results in various domains, from healthcare to finance.

            Key considerations for {topic.lower()} implementation include:
            1. Scalability and performance optimization
            2. Robust error handling mechanisms
            3. Comprehensive testing strategies
            4. Documentation and knowledge sharing
            5. Security and privacy concerns

            The integration of {topic.lower()} with existing systems presents unique challenges that require
            careful planning and execution. Success in {topic.lower()} projects often depends on finding the
            right balance between innovation and stability.
            """
            paragraphs.append(paragraph)

    # Write content to file
    with open(file_path, "w") as f:
        f.write("\n".join(paragraphs))

    return Path(file_path)


@pytest.fixture(scope="session")
def midnight_garden_md_path(fixtures_dir: str) -> Path:
    return Path(os.path.join(fixtures_dir, "the_midnight_garden.md"))


@pytest.fixture(scope="session")
def fixtures_dir() -> str:
    return os.path.dirname(fixtures.__file__)


@pytest.fixture(scope="session")
def tmpdir(tmp_path_factory) -> str:
    return str(tmp_path_factory.mktemp("elroy"))
