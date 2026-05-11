# TODO

## Autonomous Self-Improvement Capabilities

### Async Codex Sessions with Agent Branch

#### 1. Background Execution

- Update `dispatch_codex_session` to return immediately with a session ID.
- Run the Codex process in the background so execution is non-blocking.
- Allow the assistant to continue the conversation while a Codex session is running.
- Preserve enough session state for restart/reload so in-flight Codex work can still complete cleanly.

#### 2. Per-Session Isolation

- Run each Codex coding session on its own isolated branch or worktree rather than directly on `main`.
- Prefer a per-session worktree/branch model over a shared mutable checkout so concurrent sessions do not conflict.
- Evaluate whether git worktrees are a better fit than subtrees for restart behavior and repo-local execution.
- Keep the isolation model compatible with async background sessions and later resumption.

#### 3. Agent Branch Strategy

- Merge successful Codex session output into a dedicated long-lived `agent` branch.
- Treat `agent` as the primary branch Elroy itself should run on for agent-driven improvements.
- Keep unapproved agent changes isolated from `main` by default.
- Make it easy for Tom to review diffs from `agent` and selectively merge useful changes back to `main`.

#### 4. Completion Notifications

- When a Codex session completes, automatically send a message back to the assistant.
- The completion notification should trigger a fresh assistant response, not merely update stored state.
- Target message format:
  - `"Codex session XYZ completed on agent branch. Changes: [summary]"`
- Include enough summary context for the assistant to review results and decide whether to iterate.

#### 5. Message Queue

- Implement a queue that can accept user messages while Codex sessions are running.
- Handle multiple dispatched sessions gracefully.
- Define how queued messages map to active, completed, or failed sessions.

#### 6. Review Workflow

- Provide an easy way to inspect what changed in the per-session branch/worktree and what has landed on `agent`.
- Add clear commands or helpers to merge approved `agent` branch changes into `main`.
- Add an option to discard per-session or `agent` branch changes when the results are not wanted.

### Benefits

- True autonomous self-improvement loop
- Non-blocking code changes
- Safe experimentation space via per-session isolation and an `agent` branch
- Clear review process before merging changes into `main`
