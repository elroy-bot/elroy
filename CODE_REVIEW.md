# Code Review Rules

This document defines the architectural and change-validation rules used during review.

## Role Vocabulary

Prefer these names over generic `*Service` names.

### `Store`

Responsible for:
- Persistence and retrieval for one domain entity or closely related entity set
- Domain-scoped queries
- Lightweight invariants tied directly to persisted state
- Mapping between DB/file representation and domain objects

Must not be responsible for:
- Multi-step workflows across domains
- Calling sibling components to coordinate side effects
- Background scheduling
- Prompt construction, summarization, or other transformation-heavy logic
- Embedding or recall index maintenance unless that index is the store's primary persisted state

### `Orchestrator`

Responsible for:
- End-to-end workflows involving multiple components
- Ordering of side effects
- Transaction or workflow boundaries
- Converting a user or system action into calls across stores, indexers, builders, and jobs

Must not be responsible for:
- Owning low-level persistence details
- Becoming a generic home for unrelated logic
- Re-implementing transformation logic that belongs in a builder
- Hiding unclear ownership behind vague helper methods

### `Indexer`

Responsible for:
- Maintaining derived search or retrieval state
- Embedding generation and update decisions
- Activating or deactivating index entries to match source state
- Translating domain objects into retrieval/index artifacts

Must not be responsible for:
- Primary persistence of the source entity
- Cross-domain workflow ownership
- Prompt construction
- General context lifecycle management unless narrowly scoped to indexing-related context projection

### `Builder`

Responsible for:
- Constructing derived artifacts from existing data
- Prompt assembly
- Summaries, refresh payloads, or other transformation-heavy outputs
- Pure or mostly pure read-oriented logic

Must not be responsible for:
- Persistence
- Workflow coordination
- Scheduling
- Mutating multiple systems as part of a larger action

## Dependency Rules

- `Orchestrator` may depend on `Store`, `Indexer`, `Builder`, and narrowly scoped job/scheduler components.
- `Store` must not depend on `Orchestrator`.
- `Store` should not depend on other `Store` components for workflow coordination. If coordination is needed, move it into an `Orchestrator`.
- `Indexer` must not depend on `Orchestrator`.
- `Builder` should be pure or read-only where possible.
- Bidirectional dependencies between categories are a design smell and should trigger review.
- If a component needs several siblings to complete one action, that logic likely belongs in an `Orchestrator`.
- Avoid generic `Service` naming unless the broader role is explicit and justified in review.

## Review Checks

Reviewers should check:
- Does the name match the actual responsibility?
- Is workflow logic living in an `Orchestrator` instead of a `Store`?
- Are persistence-heavy components staying narrow?
- Are indexing concerns separate from source-of-truth persistence?
- Are builders mostly pure and read-oriented?
- Are there any new bidirectional dependencies?
- Is a callback bundle being used where a clearer role boundary should exist instead?
- Is a generic `Service` name masking a more precise category?

## Change Validation

Every code change must be followed by:
- `just lint`
- `just typecheck`

If either command fails, the change is not ready for review.
