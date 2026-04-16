# TODO

## Status

This refactor is functionally complete.

Current repo status:
- The explicit refactor targets below have been implemented.
- Repo scan shows no remaining `*Service`, `*OperationService`, or `*QueryService` class names in `elroy/` or `tests/`.
- Repo scan shows no remaining repository `operations.py` compatibility facades in `elroy/repository/`.
- Internal and test imports now target the role-specific modules directly (`factory.py`, `store.py`, `queries.py`, `tools.py`, and the orchestrator/indexer modules) rather than facade modules.
- The active vocabulary in the codebase now centers on `Store`, `Orchestrator`, `Indexer`, and `Builder`.
- `CODE_REVIEW.md` reflects the same architectural rules used here.

## Architecture Roles

Adopt a small vocabulary for application structure. Avoid introducing new `*Service` names by default.

### `Store`

Responsible for:
- Persistence and retrieval for one domain entity or closely related entity set
- Domain-scoped queries
- Lightweight invariants tied directly to persisted state
- Mapping between DB/file representation and domain objects

Not responsible for:
- Multi-step workflows across domains
- Calling sibling components to coordinate side effects
- Background scheduling
- Prompt construction, summarization, or other transformation-heavy logic
- Embedding or recall index maintenance unless that index is the store's primary persisted state

Examples:
- `ContextMessageStore`
- `MemoryStore`
- `TaskStore`
- `UserPreferenceStore`

### `Orchestrator`

Responsible for:
- End-to-end workflows involving multiple components
- Ordering of side effects
- Transaction or workflow boundaries
- Converting a user or system action into calls across stores, indexers, builders, and jobs

Not responsible for:
- Owning low-level persistence details
- Becoming a grab bag for unrelated business logic
- Re-implementing transformation logic that belongs in a builder
- Hiding unclear ownership behind generic helper methods

Examples:
- `ConversationOrchestrator`
- `MemoryLifecycleOrchestrator`
- `ContextRefreshOrchestrator`
- `ReminderOrchestrator`

### `Indexer`

Responsible for:
- Maintaining derived search or retrieval state
- Embedding generation and update decisions
- Activating or deactivating index entries to match source state
- Translating domain objects into retrieval/index artifacts

Not responsible for:
- Primary persistence of the source entity
- Cross-domain workflow ownership
- Prompt construction
- General context lifecycle management unless narrowly scoped to indexing-related context projection

Examples:
- `RecallIndexer`
- `EmbeddingIndexer`

### `Builder`

Responsible for:
- Constructing derived artifacts from existing data
- Prompt assembly
- Summaries, refresh payloads, or other transformation-heavy outputs
- Pure or mostly pure read-oriented logic

Not responsible for:
- Persistence
- Workflow coordination
- Scheduling
- Mutating multiple systems as part of a larger action

Examples:
- `SystemPromptBuilder`
- `MemorySummarizer`
- `ContextSummaryBuilder`

## Dependency Rules

- `Orchestrator` may depend on `Store`, `Indexer`, `Builder`, and narrowly scoped job/scheduler components.
- `Store` must not depend on `Orchestrator`.
- `Store` should not depend on other `Store` components for workflow coordination. If coordination is needed, move it into an `Orchestrator`.
- `Indexer` must not depend on `Orchestrator`.
- `Builder` should be pure or read-only where possible.
- Bidirectional dependencies between categories are a design smell and should trigger review.
- If a component needs several siblings to complete one action, that logic likely belongs in an `Orchestrator`.
- Avoid generic `Service` naming unless the role is genuinely broader than the categories above and that breadth is justified in review.

## Refactor Direction

Completed:
- `ConversationService` -> `ConversationOrchestrator`
- Split `ContextMessageOperationService` into:
  - `ContextMessageStore`
  - `ContextRefreshOrchestrator`
  - `SystemPromptBuilder`
- Split `MemoryOperationService` into:
  - `MemoryStore`
  - `MemoryLifecycleOrchestrator`
  - `MemorySummarizer`
- `RecallOperationService` -> `RecallIndexer` plus `RecallContextBridge`
- `TaskOperationService` -> `TaskStore`
- `ReminderOperationService` -> `ReminderOrchestrator`
- Renamed remaining generic helper/query classes to role-aligned names where appropriate:
  - `ContextMessageReadStore`
  - `MemoryReadStore`
  - `RecallReadStore`
  - `CompletionsBuilder`
  - `MemoryFileSyncOrchestrator`
  - `UserPreferenceOrchestrator`
- Removed repository facade modules after migrating all remaining callers to explicit role-specific imports:
  - `context_messages/operations.py`
  - `memories/operations.py`
  - `recall/operations.py`
  - `reminders/operations.py`
  - `tasks/operations.py`
  - `user/operations.py`

No open refactor items remain from this architecture pass.

Possible future follow-up:
- Continue enforcing the vocabulary during new feature work so generic `*Service` naming does not return.
- Optionally reduce broad function-level `ElroyContext` usage by pushing more call sites toward explicit role objects when that materially improves testability and dependency clarity.

## Performance Optimizations

✅ **Completed**: Add classifier early in message cycle to help latency of responses
   - Implemented two-stage hybrid classifier (heuristics + fast_llm)
   - Integrated at messenger.py:51 (replaced TODO comment)
   - Uses fast_model infrastructure for efficient classification
   - Configurable via `memory_recall_classifier_enabled` and `memory_recall_classifier_window`
   - Current validation status: `just lint`, `just typecheck`, and `just test` all pass
   - Latest full suite result: 119 passed, 3 skipped
