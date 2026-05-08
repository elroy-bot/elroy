# TODO

## Autonomous Self-Improvement Capabilities

### Async Codex Sessions with Agent Branch

#### 1. Background Execution

- Update `dispatch_codex_session` to return immediately with a session ID.
- Run the Codex process in the background so execution is non-blocking.
- Allow the assistant to continue the conversation while the agent session is running.

#### 2. Agent Branch Strategy

- Route all Codex-generated commits to a dedicated `agent` or `codex-agent` branch.
- Keep agent changes isolated from `main` by default.
- Make it easy for Tom to review diffs and selectively merge useful changes back to `main`.

#### 3. Completion Notifications

- When a Codex session completes, automatically send a message back to the assistant.
- Target message format:
  - `"Codex session XYZ completed on agent branch. Changes: [summary]"`
- Include enough summary context for the assistant to review results and decide whether to iterate.

#### 4. Message Queue

- Implement a queue that can accept user messages while an agent session is busy.
- Handle multiple dispatched sessions gracefully.
- Define how queued messages map to active or completed sessions.

#### 5. Review Workflow

- Provide an easy way to inspect what changed on the agent branch.
- Add clear commands or helpers to merge agent branch changes into `main`.
- Add an option to discard agent branch changes when the results are not wanted.

### Benefits

- True autonomous self-improvement loop
- Non-blocking code changes
- Safe experimentation space via an agent branch
- Clear review process before merging changes
