from pathlib import Path

from elroy.repository.feature_requests.queries import list_feature_requests
from elroy.repository.feature_requests.tools import (
    edit_feature_request,
    make_feature_request,
)
from elroy.repository.feature_requests.tools import (
    list_feature_requests as list_feature_requests_tool,
)


def test_make_feature_request_creates_markdown_file(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))

    response = make_feature_request(
        ctx,
        "Add calendar sync",
        "Allow Elroy to sync reminders with an external calendar provider.",
        "This would make reminders useful outside the terminal.",
    )

    feature_request_dir = Path(tmp_path) / "feature-requests"
    files = list(feature_request_dir.glob("*.md"))

    assert "Created feature request: Add calendar sync" in response
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "title: Add calendar sync" in content
    assert "## Summary" in content
    assert "## Why It Matters" in content
    assert "## Supporting Context" in content


def test_make_feature_request_merges_similar_requests(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))

    make_feature_request(
        ctx,
        "Add calendar sync",
        "Allow Elroy to sync reminders with external calendar providers.",
        "Useful for integrating reminders into existing workflows.",
    )
    response = make_feature_request(
        ctx,
        "Calendar syncing for reminders",
        "Allow reminders to appear in external calendar providers.",
        "Avoid maintaining the same reminder in two places.",
    )

    records = list_feature_requests()

    assert "Merged into existing feature request: Add calendar sync" in response
    assert len(records) == 1
    assert "Calendar syncing for reminders" in records[0].aliases
    assert "Avoid maintaining the same reminder in two places." in (records[0].supporting_context or "")


def test_list_feature_requests_tool_returns_compact_listing(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))

    make_feature_request(
        ctx,
        "Add calendar sync",
        "Allow Elroy to sync reminders with external calendar providers.",
        "Useful for integrating reminders into existing workflows.",
    )

    result = list_feature_requests_tool(ctx)

    assert "Feature requests (1):" in result
    assert "- Add calendar sync [open]" in result
    assert "Summary: Allow Elroy to sync reminders with external calendar providers." in result


def test_edit_feature_request_updates_existing_request(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))

    make_feature_request(
        ctx,
        "Add calendar sync",
        "Allow Elroy to sync reminders with external calendar providers.",
        "Useful for integrating reminders into existing workflows.",
    )

    response = edit_feature_request(
        ctx,
        "Add calendar sync",
        title="Add calendar integration",
        description="Allow Elroy reminders to sync with external calendars.",
        rationale="This would reduce duplicated reminder management.",
        status="planned",
    )
    records = list_feature_requests()

    assert "Updated feature request: Add calendar integration" in response
    assert len(records) == 1
    assert records[0].title == "Add calendar integration"
    assert records[0].summary == "Allow Elroy reminders to sync with external calendars."
    assert records[0].rationale == "This would reduce duplicated reminder management."
    assert records[0].status == "planned"
