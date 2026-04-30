# Code Review Rules

This document defines the architectural and change-validation rules used during review.

## Role Vocabulary

Adopt a small vocabulary for application structure. Avoid introducing new
`*Service` names by default.

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
- Do not introduce new `*Service` names.
- If a role is genuinely broader than `Store`, `Orchestrator`, `Indexer`, or `Builder`, the broader name must be explicitly justified in review.

## Context And Session Boundaries

These rules describe the ideal end-state for request/session/config factoring.

### `ElroyConfig`

Responsible for:
- Long-lived application settings
- Model, UI, memory, tool, and runtime configuration
- Defaults that are stable across many requests/turns

Must not be responsible for:
- Holding a live `DbSession`
- User/session identity
- Per-turn request metadata
- Acting as a service locator for orchestrators, stores, or builders

### `ElroySession`

Responsible for:
- Long-lived user/session identity
- `user_id`
- `user_token` only if still operationally required
- Stable session identifiers for logging/tracing when needed

Must not be responsible for:
- Holding a live `DbSession`
- Scheduler/background job handles
- UI state
- Request/turn-local metadata
- Becoming a general-purpose container for shared services

### `TurnContext`

Responsible for:
- One request/turn/tool-execution scope
- Holding the active `DbSession`
- Holding per-turn metadata such as request id, latency tracker, or cancellation state
- Referring to the current `ElroySession` and relevant config/runtime inputs

Must not be responsible for:
- Becoming another broad catch-all object
- Owning app-global services
- Accumulating unrelated state across multiple turns

### Composition Objects

App-wide shared components such as `DbManager`, schedulers, model clients, and filesystem helpers may live in a broader composition object at the application boundary.

That object:
- Should stay at the edge of the system
- Should not be the default dependency passed into stores/orchestrators/builders
- Should not be named or treated like a general-purpose domain context

## Context Dependency Rules

- Inner persistence/query/orchestration code should not derive database access from a broad config object.
- Prefer passing `ElroySession`, `TurnContext`, `DbSession`, or similarly narrow typed dependencies over passing `ElroyConfig`.
- `ElroyConfig` should not become the default dependency carrier for DB-backed or workflow-heavy code.
- If a component only needs config, pass config instead of a broader context/session object.
- If a component touches persisted state, its dependency should make the transaction/session boundary explicit.
- Long-lived DB sessions are a design smell and should trigger review.
- Request-local state must not be stored on long-lived config/session objects.
- A new `*Context` type is only an improvement if it is narrower than the object it replaces and aligned to a real lifetime boundary.
- Mixed boundary signatures are not allowed. A function must not accept substantially different dependency shapes such as `ElroyConfig | TurnContext`, even as a convenience API.
- The boundary split must be explicit:
  - inner DB-backed code accepts `TurnContext` only
  - edge adapters accept `ElroyConfig` only, open a turn, and delegate immediately
- Adapters must stay thin. If an `ElroyConfig` wrapper starts doing substantive workflow logic before or after opening a turn, that is a design smell and should trigger review.
- Helper adapters like `do_*` or similarly explicit naming are preferred over ambiguous unions or overloaded signatures.
- Raw operating-config reads such as `ctx.*` are not allowed in inner helpers once a narrower runtime/config object exists for that slice.
- If a helper only needs a few config decisions such as model name, background-thread enablement, greeting thresholds, or inline-tool flags, extract a dedicated runtime/config object instead of reaching through a broad context.

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

## Package Export And File Organization Rules

- `__init__.py` should expose only stable package-level entry points.
- Module-specific types and helpers should usually be imported from their defining module, not re-exported through a package, unless that API is intentionally being promoted as public.
- Re-exports should be minimal and explicit. If a package curates a public surface, prefer defining `__all__`.
- Empty `__init__.py` files are preferred over broad convenience re-export hubs when a package does not need a curated public API.
- New modules should be split by responsibility boundary, not by arbitrary helper extraction or file-length discomfort alone.
- If a file needs several unrelated reasons to change, it likely wants to be split.
- If two modules are tightly coupled enough that callers must understand both to use either one, review whether they should be reorganized around a clearer boundary.
- Package structure should follow the architectural roles in this document where practical. Workflow code should not be hidden in vague utility modules or mixed into unrelated packages.
- Avoid introducing cross-package import patterns that make inner modules depend on broad package-level re-export surfaces instead of concrete owning modules.
- When a new package or module is introduced, its name should make its responsibility obvious and its placement should be consistent with adjacent packages.

## Review Checks

Reviewers should check:
- Does the name match the actual responsibility?
- Is workflow logic living in an `Orchestrator` instead of a `Store`?
- Are persistence-heavy components staying narrow?
- Are indexing concerns separate from source-of-truth persistence?
- Are builders mostly pure and read-oriented?
- Are there any new bidirectional dependencies?
- Is a callback bundle being used where a clearer role boundary should exist instead?
- Has a new `*Service` name been introduced where a more precise category should exist?
- If a broader non-role name remains, is that exception explicitly justified?
- Is `ElroyConfig` being used where a narrower session/request/runtime object should be passed instead?
- Is DB access derived from an explicit turn/session dependency, or is it still hidden behind a broad context object?
- Are long-lived identity/config objects staying free of live DB sessions and per-turn state?
- Is the app shell mostly wiring and coordination, or is it becoming a god object again?
- Are widgets emitting typed messages/results instead of directly driving domain workflows?
- Is UI decision logic testable as plain Python, or is it unnecessarily trapped in Textual event handlers?
- Are widget boundaries aligned to coherent UI areas rather than arbitrary helper extraction?
- Are package-level exports intentional, minimal, and stable?
- Is code being imported from the defining module unless the package surface is deliberately curated?
- Does the file and package placement match the code's actual responsibility?
- Has a vague helper or utility module become a dumping ground for workflow or domain logic?

## Change Validation

Every code change must be followed by:
- `just lint`
- `just typecheck`

If either command fails, the change is not ready for review.
