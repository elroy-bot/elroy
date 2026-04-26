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

## UI Structural Rules

These rules apply to Textual UI code and any future interactive surfaces.

### `App` / Shell

Responsible for:
- Composing the top-level layout
- Wiring widgets, controllers, and state objects together
- Launching screens and modal flows
- Translating high-level intents into UI effects

Must not be responsible for:
- Owning large amounts of pure decision logic
- Acting as the default home for every widget event
- Encoding key maps, focus policy, selection policy, and status derivation inline when those can live in plain state/controller objects
- Reaching deep into the widget tree for routine behavior that should belong to a dedicated widget

### Widget

Responsible for:
- Rendering one coherent area of the UI
- Handling widget-local events and bindings
- Emitting typed messages or dismiss results that describe user intent
- Owning local presentation details such as highlight rendering, list population, and small reactive behaviors

Must not be responsible for:
- Cross-domain workflows
- Calling persistence or orchestration layers directly
- Hiding app-level control flow behind callback bundles when a message or typed result would be clearer

### State Model

Responsible for:
- Pure UI decision logic
- Key-to-intent mapping
- Selection, browse-mode, focus-target, and status derivation rules
- Returning typed actions or targets that can be unit tested without booting Textual

Must not be responsible for:
- Touching widgets directly
- Performing IO or background work
- Owning screen-launching behavior

### Controller

Responsible for:
- Coordinating side effects for one UI slice or session lifecycle
- Bridging typed UI intents to orchestrators, stores, workers, or timers
- Owning workflow-heavy behavior that is not purely presentational

Must not be responsible for:
- Rendering widgets directly when a widget can own that concern
- Becoming a second god object beside the app shell

## UI Dependency Rules

- Widgets should communicate upward with typed `Message`s or typed modal/screen results, not ad hoc callback closures.
- Plain state objects must not depend on Textual widgets.
- The app shell may depend on widgets, state models, and controllers.
- Widgets may depend on plain render models and lightweight state, but should not depend on domain orchestrators or stores for workflow execution.
- If a behavior can be expressed as a pure state transition or intent mapping, prefer putting it in a state model and unit testing it there.
- If a widget repeatedly requires `query_one()` from the app shell for normal operation, that is a design smell and should trigger review.
- If raw low-level widget events are repeatedly translated in the app shell, prefer moving that translation into the widget and emitting a higher-level message.
- Avoid stringly typed UI identifiers as behavioral keys when a typed ref or typed action model is practical.

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
- Is the app shell mostly wiring and coordination, or is it becoming a god object again?
- Are widgets emitting typed messages/results instead of directly driving domain workflows?
- Is UI decision logic testable as plain Python, or is it unnecessarily trapped in Textual event handlers?
- Are widget boundaries aligned to coherent UI areas rather than arbitrary helper extraction?

## Change Validation

Every code change must be followed by:
- `just lint`
- `just typecheck`

If either command fails, the change is not ready for review.
