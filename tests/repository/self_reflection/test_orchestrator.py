from elroy.core.constants import ASSISTANT, USER
from elroy.core.ctx import ElroyConfig
from elroy.core.session import open_turn_context
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.factory import build_context_refresh_orchestrator
from elroy.repository.context_messages.session import build_context_message_session
from elroy.repository.feature_requests.queries import list_feature_requests
from elroy.repository.feature_requests.store import update_feature_request


def _persist_messages(ctx: ElroyConfig, messages: list[ContextMessage]) -> None:
    with open_turn_context(ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(messages)


def test_self_reflection_no_feature_request_without_correction_feedback(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 2

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Can you summarize the plan?", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Here is the summary.", chat_model=None),
            ContextMessage(role=USER, content="Thanks, now make it shorter.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Shorter version.", chat_model=None),
        ],
    )

    assert list_feature_requests() == []


def test_self_reflection_creates_feature_request_when_threshold_and_correction_hit(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 2

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Draft a reply to this message.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Here is a draft.", chat_model=None),
            ContextMessage(role=USER, content="That's wrong. You forgot the main deadline.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="I will revise it.", chat_model=None),
        ],
    )

    records = list_feature_requests()

    assert len(records) == 1
    assert records[0].title == "Improve response handling after direct user corrections"
    assert records[0].source == "self_reflection"
    assert "tighten response validation" in records[0].summary
    assert "you forgot" in (records[0].rationale or "").lower()
    assert "You forgot the main deadline." in (records[0].supporting_context or "")


def test_self_reflection_skips_when_cadence_threshold_not_hit(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 2

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="That's wrong, you forgot the dependency note.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="I will fix it.", chat_model=None),
        ],
    )

    assert list_feature_requests() == []


def test_self_reflection_dedupes_repeated_triggers(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 2

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Give me the release checklist.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Checklist draft.", chat_model=None),
            ContextMessage(role=USER, content="Not quite, you forgot the rollback step.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="I will add it.", chat_model=None),
        ],
    )
    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Now shorten it.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Short version.", chat_model=None),
            ContextMessage(role=USER, content="You should improve how you handle corrections like this.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Understood.", chat_model=None),
        ],
    )

    records = list_feature_requests()

    assert len(records) == 1
    supporting_context = records[0].supporting_context or ""
    assert "rollback step" in supporting_context
    assert "handle corrections like this" in supporting_context


def test_self_reflection_does_not_repeat_same_feedback_on_later_thresholds(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 2

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Show me the release steps.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Here are the steps.", chat_model=None),
            ContextMessage(role=USER, content="Not quite, you forgot the rollback step.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="I will revise it.", chat_model=None),
        ],
    )
    first_record = list_feature_requests()[0]
    first_supporting_context = first_record.supporting_context

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Shorten the checklist.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Shorter checklist.", chat_model=None),
            ContextMessage(role=USER, content="Make it one sentence.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="One sentence version.", chat_model=None),
        ],
    )

    records = list_feature_requests()

    assert len(records) == 1
    assert records[0].supporting_context == first_supporting_context


def test_self_reflection_can_be_disabled_with_explicit_zero(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 0

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Draft a reply to this message.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Here is a draft.", chat_model=None),
            ContextMessage(role=USER, content="That's wrong. You forgot the main deadline.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="I will revise it.", chat_model=None),
        ],
    )

    assert list_feature_requests() == []


def test_self_reflection_reopens_closed_matching_feature_request(ctx, monkeypatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    ctx.use_background_threads = False
    ctx.messages_between_self_reflection = 2

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Give me the release checklist.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Checklist draft.", chat_model=None),
            ContextMessage(role=USER, content="Not quite, you forgot the rollback step.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="I will add it.", chat_model=None),
        ],
    )

    closed_record = update_feature_request(list_feature_requests()[0], status="closed")
    assert closed_record.status == "closed"

    _persist_messages(
        ctx,
        [
            ContextMessage(role=USER, content="Now shorten it.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Short version.", chat_model=None),
            ContextMessage(role=USER, content="You should improve how you handle corrections like this.", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Understood.", chat_model=None),
        ],
    )

    records = list_feature_requests()

    assert len(records) == 1
    assert records[0].status == "open"
    supporting_context = records[0].supporting_context or ""
    assert "rollback step" in supporting_context
    assert "handle corrections like this" in supporting_context
