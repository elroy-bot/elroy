# PRD: Memory System

**Status**: Draft
**Date**: 2026-03-20

---

## Overview

Elroy's memory system automatically extracts facts from conversations, stores them as semantic embeddings, surfaces them in future conversations, and periodically consolidates redundant entries. This PRD describes known gaps and the improvements needed to make memories more useful, accurate, and maintainable.

---

## Known Issues

| # | Issue | File / Line | Impact |
|---|-------|-------------|--------|
| 1 | N+1 query in consolidation: each memory's embedding is fetched in a separate DB call | `consolidation.py:161` | Slow consolidation on large memory sets |
| 2 | Default YAML values for `memory_cluster_similarity_threshold`, `max_memory_cluster_size`, `min_memory_cluster_size`, `memories_between_consolidation` differ from in-code dataclass defaults | `defaults.yml` vs `configs.py:48–68` | Unpredictable behavior when defaults.yml is absent |
| 3 | `test_update_memory_relationship_status` is skipped with a TODO | `test_update_memory.py` | No test coverage for the update-memory path |
| 4 | Reflection word limit is hardcoded at 100 | `queries.py:248` | Inflexible for long or complex memory sets |
| 5 | No conflict resolution in consolidation prompt | `consolidation.py`, `prompts.py` | Contradictory memories silently co-exist |

---

## Improvement Areas

### 1. Memory quality: synthesis over summary

**Problem**: The consolidation prompt asks the LLM to reorganize memories but does not ask it to resolve contradictions or synthesize deeper insights (e.g. inferring that two date-stamped events form a recurring pattern).

**Goal**: Consolidated memories should be richer than the sum of their parts — they should resolve conflicts and call out patterns.

**Changes**:
- Update `prompts.py` consolidation prompt to explicitly instruct the model to:
  - Flag and resolve contradictions (prefer the most recent memory when dates are present)
  - Note recurring patterns if events appear more than once
  - Produce a single synthesis, not a list

---

### 2. Memory freshness: recency weighting in recall

**Problem**: A memory created three years ago is retrieved with the same priority as one created yesterday. Stale memories can crowd out recent ones.

**Goal**: Recall should slightly prefer recent memories when relevance scores are otherwise close.

**Changes**:
- Add `recency_weight` config parameter (default 0.0, disabled)
- When non-zero, adjust the L2 distance score by `recency_weight * age_in_days / 365` before ranking
- Expose via `MemoryConfig`

---

### 3. Performance: batch-load embeddings in consolidation

**Problem**: `consolidation.py:161` fetches each memory embedding in a separate DB round-trip (N+1 pattern acknowledged in a TODO comment).

**Goal**: Single query loads all active memory embeddings for the user.

**Changes**:
- Add `get_all_embeddings_for_user(session, user_id)` to `recall/queries.py`
- Replace the per-memory fetch loop in `consolidation.py` with a single call + dict lookup

---

### 4. Configuration consistency: reconcile defaults

**Problem**: `MemoryConfig` dataclass and `defaults.yml` have different values for four fields. The YAML values win at runtime (via `from_config_file`), making the dataclass defaults misleading.

**Goal**: The dataclass defaults should match what users actually get out of the box.

**Changes**:
- Update `configs.py` `MemoryConfig` dataclass defaults to match `defaults.yml`:
  - `memory_cluster_similarity_threshold: 0.85 → 0.21125`
  - `max_memory_cluster_size: 10 → 5`
  - `min_memory_cluster_size: 2 → 3`
  - `memories_between_consolidation: 5 → 4`
- Add a unit test that loads the defaults file and asserts each value matches the dataclass default

---

### 5. Memory update: test coverage

**Problem**: The `update_outdated_or_incorrect_memory` tool has no active tests. The existing test file skips the only test with a TODO.

**Goal**: Full coverage for the update path.

**New tests** (`tests/repository/memories/test_update_memory.py`):
- `test_update_marks_old_inactive` — call update, verify original `is_active=False`
- `test_update_creates_new_memory` — new memory record created with updated text
- `test_update_source_tracks_predecessor` — new memory's `source_metadata` references old memory id
- `test_update_nonexistent_raises` — raises `RecoverableToolError` when name not found

---

### 6. Reflection word limit: make configurable

**Problem**: The 100-word reflection cap is hardcoded in `queries.py:248`. For users with many short memories, a lower limit is wasteful; for complex topics, it truncates useful context.

**Goal**: Make the limit a config parameter.

**Changes**:
- Add `memory_reflection_max_words: int = 100` to `MemoryConfig`
- Replace hardcoded value in `queries.py` with `ctx.config.memory_reflection_max_words`

---

### 7. Memory archival housekeeping

**Problem**: Archived memories accumulate in `~/.elroy/memories/archive/` indefinitely. There is no mechanism to review or prune the archive.

**Goal**: Provide a user-visible command to inspect and optionally purge the archive.

**New user-only tool**: `list_archived_memories(ctx, limit=50) -> Table`
- Lists archived memories with name, archived date, and word count
- Does not restore or delete — read-only

**New user-only tool**: `purge_archived_memories(ctx, older_than_days=90) -> str`
- Deletes archive files older than threshold
- Returns count of files deleted
- Requires explicit user invocation (not assistant-visible)

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | Consolidation prompt explicitly addresses contradictions; consolidated memory text differs meaningfully from a naive concatenation when tested with conflicting source memories |
| 2 | `recency_weight=0` (default) produces identical ranking to unweighted; `recency_weight=0.5` demonstrably ranks a 1-day-old memory above a 365-day-old memory with equal cosine distance |
| 3 | Consolidation for a user with 100 memories makes exactly 1 DB call for embeddings (verified by query count in tests) |
| 4 | `python -c "from elroy.core.configs import MemoryConfig; import yaml; ..."` assert passes: all four reconciled fields match |
| 5 | All four new update-memory tests pass |
| 6 | `memory_reflection_max_words: 50` in config causes reflection output to be ≤ 50 words |
| 7 | `list_archived_memories` returns a table; `purge_archived_memories(older_than_days=0)` deletes all archive files and returns the correct count |
| 8 | All existing memory tests continue to pass |
