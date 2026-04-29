from ...core.constants import tool
from ...core.ctx import ElroyContext
from ...utils.clock import utc_now
from .queries import (
    find_best_feature_request_match,
    get_feature_request,
)
from .queries import (
    list_feature_requests as list_feature_request_records,
)
from .store import update_feature_request, write_new_feature_request


def _build_supporting_context(ctx: ElroyContext, title: str, description: str, rationale: str | None) -> str:
    lines = [
        f"- Captured at: {utc_now().isoformat()}",
        f"- Requested title: {title}",
        f"- Description: {description.strip()}",
    ]
    if rationale:
        lines.append(f"- Rationale: {rationale.strip()}")
    lines.append(f"- User token: {ctx.user_token}")
    return "\n".join(lines)


def _merge_supporting_context(existing: str | None, new_context: str) -> str:
    if not existing:
        return new_context
    if new_context in existing:
        return existing
    return f"{existing.rstrip()}\n\n{new_context}"


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@tool
def list_feature_requests(ctx: ElroyContext) -> str:
    """List the current markdown-backed feature requests.

    Use this before creating a new feature request when you suspect the request may
    already exist. This helps avoid duplicate backlog entries by surfacing the
    canonical titles, aliases, statuses, and brief summaries of existing requests.

    Args:
        ctx (ElroyContext): Active Elroy context. Present for tool compatibility.

    Returns:
        str: A compact text listing of all current feature requests.
    """
    _ = ctx
    records = list_feature_request_records()
    if not records:
        return "No feature requests found."

    lines = [f"Feature requests ({len(records)}):", ""]
    for record in records:
        aliases = f" | aliases: {', '.join(record.aliases)}" if record.aliases else ""
        lines.append(f"- {record.title} [{record.status}] ({record.path.name}){aliases}")
        lines.append(f"  Summary: {record.summary}")
    return "\n".join(lines)


@tool
def edit_feature_request(
    ctx: ElroyContext,
    identifier: str,
    title: str | None = None,
    description: str | None = None,
    rationale: str | None = None,
    status: str | None = None,
) -> str:
    """Edit an existing markdown feature request.

    Use this when a feature request already exists and needs a better title,
    refined summary, updated rationale, or status change. Prefer this over creating
    a duplicate request for the same product need.

    Args:
        ctx (ElroyContext): Active Elroy context used to capture lightweight edit provenance.
        identifier (str): Existing request id, title, alias, or filename stem to update.
        title (str | None): Replacement canonical title.
        description (str | None): Replacement summary of the request.
        rationale (str | None): Replacement rationale for why it matters.
        status (str | None): Replacement status value such as `open` or `closed`.

    Returns:
        str: Confirmation describing the updated feature request.
    """
    record = get_feature_request(identifier.strip())
    if record is None:
        return f"Feature request '{identifier}' not found."

    cleaned_title = _normalize_optional(title)
    cleaned_description = _normalize_optional(description)
    cleaned_rationale = _normalize_optional(rationale)
    cleaned_status = _normalize_optional(status)
    updated_record = update_feature_request(
        record,
        title=cleaned_title,
        status=cleaned_status,
        summary=cleaned_description,
        rationale=cleaned_rationale,
        supporting_context=_merge_supporting_context(
            record.supporting_context,
            "\n".join(
                [
                    f"- Edited at: {utc_now().isoformat()}",
                    f"- Edited by user token: {ctx.user_token}",
                ]
            ),
        ),
    )
    return f"Updated feature request: {updated_record.title} ({updated_record.path.name})."


@tool
def make_feature_request(ctx: ElroyContext, title: str, description: str, rationale: str | None = None) -> str:
    """Create or merge a markdown feature request for future product work.

    Use this when the user asks for a net new capability, workflow, or product behavior
    that Elroy does not currently support. First consider calling `list_feature_requests`
    to inspect the existing backlog. This tool will also try to merge into an existing
    feature request when the request appears duplicative, to avoid backlog bloat.

    Args:
        ctx (ElroyContext): Active Elroy context used to capture lightweight request provenance.
        title (str): Short title describing the requested feature.
        description (str): What the new feature should do.
        rationale (str | None): Optional explanation of why the feature matters.

    Returns:
        str: Confirmation describing whether a request was created or merged.
    """

    cleaned_title = title.strip()
    cleaned_description = description.strip()
    cleaned_rationale = rationale.strip() if rationale else None
    supporting_context = _build_supporting_context(ctx, cleaned_title, cleaned_description, cleaned_rationale)

    if match := find_best_feature_request_match(cleaned_title, cleaned_description):
        aliases = sorted({*match.record.aliases, cleaned_title} - {match.record.title})
        updated_record = update_feature_request(
            match.record,
            aliases=aliases,
            supporting_context=_merge_supporting_context(match.record.supporting_context, supporting_context),
        )
        return f"Merged into existing feature request: {updated_record.title} ({updated_record.path.name}; match reason: {match.reason})."

    new_record = write_new_feature_request(
        title=cleaned_title,
        summary=cleaned_description,
        rationale=cleaned_rationale,
        supporting_context=supporting_context,
    )
    return f"Created feature request: {new_record.title} ({new_record.path.name})."
