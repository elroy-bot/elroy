# PRD: Memory System

**Status**: Draft
**Date**: 2026-03-20

---

## Overview

Elroy's memory system automatically extracts facts from conversations, stores them as semantic embeddings, surfaces them in future conversations, and periodically consolidates redundant entries. This PRD describes known gaps and the improvements needed to make memories more useful, accurate, and maintainable.

---

## Known Issues

| # | Issue | Impact |
|---|-------|--------|
| 1 | Each memory's embedding is fetched in a separate DB call during consolidation | Slow consolidation on large memory sets |
| 2 | Several clustering and consolidation config parameters have different values in the config file vs. the in-code defaults | Unpredictable behavior when the config file is absent |
| 3 | The memory update path has no active test coverage | Regressions in update-memory behavior go undetected |
| 4 | The reflection word limit is hardcoded | Inflexible for long or complex memory sets |
| 5 | The consolidation prompt does not ask the model to resolve contradictions | Contradictory memories silently co-exist |

---

## Improvement Areas

### 1. Memory quality: synthesis over summary

**Problem**: The consolidation step reorganizes memories but does not resolve contradictions or synthesize deeper insights (e.g. inferring that two date-stamped events form a recurring pattern).

**Goal**: Consolidated memories should be richer than the sum of their parts — they should resolve conflicts and call out patterns.

**Changes**:
- The consolidation prompt should explicitly instruct the model to:
  - Flag and resolve contradictions (prefer the most recent memory when dates are present)
  - Note recurring patterns if events appear more than once
  - Produce a single synthesis, not a list

---

### 2. Memory freshness: recency weighting in recall

**Problem**: A memory created three years ago is retrieved with the same priority as one created yesterday. Stale memories can crowd out recent ones.

**Goal**: Recall should slightly prefer recent memories when relevance scores are otherwise close.

**Changes**:
- Add a `recency_weight` config parameter (default 0.0, disabled)
- When non-zero, apply a small age-based penalty to recall ranking so newer memories score higher when relevance is otherwise similar

---

### 3. Performance: batch-load embeddings in consolidation

**Problem**: During consolidation, each memory's embedding is fetched in a separate database round-trip.

**Goal**: Load all active memory embeddings for a user in a single query at the start of consolidation.

---

### 4. Configuration consistency: reconcile defaults

**Problem**: Several clustering and consolidation parameters have different values in the config file vs. the in-code defaults. The config file values win at runtime, making the in-code defaults misleading.

**Goal**: In-code defaults should match what users actually get out of the box.

**Changes**:
- Reconcile the four mismatched defaults so config file and in-code defaults agree:
  - Cluster similarity threshold: `0.85 → 0.21125`
  - Max cluster size: `10 → 5`
  - Min cluster size: `2 → 3`
  - Consolidation frequency: `5 → 4`
- Add a test verifying the config file and in-code defaults match for all four fields

---

### 5. Memory update: test coverage

**Problem**: The memory update tool has no active tests.

**Goal**: Full coverage for the update path.

**Tests should verify**:
- Updating a memory marks the original as inactive
- A new memory record is created with the updated text
- The new memory records its predecessor for traceability
- Attempting to update a non-existent memory surfaces a clear error

---

### 6. Reflection word limit: make configurable

**Problem**: The reflection word cap is hardcoded. For users with many short memories, a lower limit is wasteful; for complex topics, it truncates useful context.

**Goal**: Make the limit a config parameter.

**Changes**:
- Add a `memory_reflection_max_words` config parameter (default 100)

---

### 7. Memory archival housekeeping

**Problem**: Archived memories accumulate indefinitely. There is no mechanism to review or prune the archive.

**Goal**: Provide user-visible commands to inspect and optionally purge the archive.

**New capabilities**:
- **List archived memories**: Shows archived memories with name, archived date, and word count. Read-only.
- **Purge archived memories**: Deletes archived memories older than a configurable threshold (default 90 days). Returns count deleted. User-only; not accessible to the assistant.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | Consolidated memories resolve contradictions rather than carrying both sides; output is a single synthesis |
| 2 | With recency weighting disabled (default), recall ranking is unchanged; with weighting enabled, a 1-day-old memory ranks above a 365-day-old memory with equal relevance score |
| 3 | Consolidation fetches embeddings in a single DB call regardless of memory set size |
| 4 | All four reconciled config defaults match the config file values |
| 5 | The memory update path is fully tested: original deactivated, new record created, predecessor tracked, clear error on missing memory |
| 6 | A reduced reflection word limit in config visibly shortens reflection output |
| 7 | Listing archived memories returns a summary; purging deletes files and reports the count |
| 8 | All memory tests continue to pass |
