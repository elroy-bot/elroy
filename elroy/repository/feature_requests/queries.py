from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .store import FeatureRequestRecord, feature_requests_dir, load_feature_request

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class FeatureRequestMatch:
    record: FeatureRequestRecord
    score: float
    reason: str


def list_feature_requests() -> list[FeatureRequestRecord]:
    return [load_feature_request(path) for path in sorted(feature_requests_dir().glob("*.md"))]


def get_feature_request(identifier: str) -> FeatureRequestRecord | None:
    normalized_identifier = _normalize(identifier)
    for record in list_feature_requests():
        candidates = {
            record.request_id,
            record.title,
            record.path.stem,
            *record.aliases,
        }
        if normalized_identifier in {_normalize(candidate) for candidate in candidates}:
            return record
    return None


def _normalize(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _title_score(candidate: str, existing: str) -> float:
    return SequenceMatcher(None, _normalize(candidate), _normalize(existing)).ratio()


def _token_overlap(candidate: str, existing: str) -> float:
    candidate_tokens = _token_set(candidate)
    existing_tokens = _token_set(existing)
    if not candidate_tokens or not existing_tokens:
        return 0.0
    intersection = len(candidate_tokens & existing_tokens)
    return intersection / max(len(candidate_tokens), len(existing_tokens))


def _score_match(title: str, description: str, record: FeatureRequestRecord) -> FeatureRequestMatch:
    existing_titles = [record.title, *record.aliases]
    title_scores = [_title_score(title, existing_title) for existing_title in existing_titles]
    best_title_score = max(title_scores, default=0.0)
    summary_score = _title_score(description, record.summary)
    overlap_score = max((_token_overlap(title, existing_title) for existing_title in existing_titles), default=0.0)
    combined = max(best_title_score, (best_title_score * 0.7) + (summary_score * 0.15) + (overlap_score * 0.15))
    if best_title_score >= 0.995:
        reason = "exact title match"
    elif best_title_score >= 0.92:
        reason = "very similar title"
    elif best_title_score >= 0.8 and overlap_score >= 0.6:
        reason = "strong title overlap"
    else:
        reason = "weak match"
    return FeatureRequestMatch(record=record, score=combined, reason=reason)


def find_best_feature_request_match(title: str, description: str) -> FeatureRequestMatch | None:
    matches = [_score_match(title, description, record) for record in list_feature_requests()]
    if not matches:
        return None
    best_match = max(matches, key=lambda match: match.score)
    if best_match.score >= 0.92:
        return best_match
    if best_match.score >= 0.82 and best_match.reason == "strong title overlap":
        return best_match
    description_similarity = _title_score(description, best_match.record.summary)
    title_overlap = _token_overlap(title, best_match.record.title)
    if description_similarity >= 0.72 and title_overlap >= 0.25:
        return FeatureRequestMatch(
            record=best_match.record,
            score=best_match.score,
            reason="similar behavior description",
        )
    return None
