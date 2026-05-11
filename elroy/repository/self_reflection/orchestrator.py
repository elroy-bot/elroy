from __future__ import annotations

from dataclasses import dataclass

from ...core.constants import USER
from ...repository.context_messages.data_models import ContextMessage
from ...repository.feature_requests.queries import find_best_feature_request_match, is_active_feature_request
from ...repository.feature_requests.store import FeatureRequestRecord, update_feature_request, write_new_feature_request
from ...utils.clock import utc_now

CORRECTION_PHRASES = (
    "you forgot",
    "that's wrong",
    "not quite",
    "reflect on that",
    "you should improve",
)


@dataclass(frozen=True)
class SelfReflectionConfig:
    messages_between_self_reflection: int


@dataclass(frozen=True)
class ReflectionProposal:
    title: str
    description: str
    rationale: str
    supporting_context: str
    feedback_excerpt: str


@dataclass(frozen=True)
class SelfReflectionResult:
    triggered: bool
    proposal: ReflectionProposal | None = None
    feature_request: FeatureRequestRecord | None = None


class SelfReflectionOrchestrator:
    def __init__(self, config: SelfReflectionConfig):
        self.config = config

    def run(self, context_messages: list[ContextMessage]) -> SelfReflectionResult:
        if not self._should_reflect(context_messages):
            return SelfReflectionResult(triggered=False)

        proposal = self._build_proposal(context_messages)
        if proposal is None:
            return SelfReflectionResult(triggered=False)

        return SelfReflectionResult(
            triggered=True,
            proposal=proposal,
            feature_request=self._persist_feature_request(proposal),
        )

    def _should_reflect(self, context_messages: list[ContextMessage]) -> bool:
        threshold = self.config.messages_between_self_reflection
        if threshold <= 0:
            return False

        user_message_count = len([msg for msg in context_messages if msg.role == USER and (msg.content or "").strip()])
        return user_message_count >= threshold and user_message_count % threshold == 0

    def _build_proposal(self, context_messages: list[ContextMessage]) -> ReflectionProposal | None:
        for message in reversed(context_messages):
            if message.role != USER or not message.content:
                continue

            normalized = message.content.lower()
            phrase = next((candidate for candidate in CORRECTION_PHRASES if candidate in normalized), None)
            if phrase is None:
                continue

            excerpt = " ".join(message.content.strip().split())
            if len(excerpt) > 240:
                excerpt = excerpt[:237].rstrip() + "..."

            return ReflectionProposal(
                title="Improve response handling after direct user corrections",
                description=(
                    "When the user gives explicit correction-like feedback, Elroy should treat it as a signal "
                    "to tighten response validation and recover more directly within the same conversation turn."
                ),
                rationale=(
                    f"Recent feedback included the phrase '{phrase}', which suggests the assistant gave an incomplete "
                    "or incorrect response and should adapt more reliably."
                ),
                supporting_context="\n".join(
                    [
                        f"- Reflected at: {utc_now().isoformat()}",
                        f"- Trigger phrase: {phrase}",
                        f"- Recent user feedback: {excerpt}",
                    ]
                ),
                feedback_excerpt=excerpt,
            )

        return None

    def _persist_feature_request(self, proposal: ReflectionProposal) -> FeatureRequestRecord:
        if match := find_best_feature_request_match(proposal.title, proposal.description):
            reopened_status = None
            if match.record.source == "self_reflection" and not is_active_feature_request(match.record):
                reopened_status = "open"

            if self._has_matching_feedback_excerpt(match.record.supporting_context, proposal.feedback_excerpt):
                if reopened_status is not None:
                    return update_feature_request(match.record, status=reopened_status)
                return match.record
            merged_supporting_context = self._merge_supporting_context(
                match.record.supporting_context,
                proposal.supporting_context,
            )
            return update_feature_request(
                match.record,
                status=reopened_status,
                aliases=sorted({*match.record.aliases, proposal.title} - {match.record.title}),
                supporting_context=merged_supporting_context,
            )

        return write_new_feature_request(
            title=proposal.title,
            summary=proposal.description,
            rationale=proposal.rationale,
            supporting_context=proposal.supporting_context,
            source="self_reflection",
        )

    def _merge_supporting_context(self, existing: str | None, new_context: str) -> str:
        if not existing:
            return new_context
        if new_context in existing:
            return existing
        return f"{existing.rstrip()}\n\n{new_context}"

    def _has_matching_feedback_excerpt(self, existing: str | None, feedback_excerpt: str) -> bool:
        if not existing:
            return False
        return f"- Recent user feedback: {feedback_excerpt}" in existing
