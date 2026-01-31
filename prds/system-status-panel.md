# PRD: System Status in Live Panel

**Status:** Draft
**Created:** 2025-01-30
**Issue:** #475
**Author:** Claude (Elroy Agent)

## Overview

Expand the existing "Relevant Context" panel to include real-time system execution information, giving users visibility into Elroy's background operations like memory consolidation, context compression, and scheduled tasks.

## Background

### Current State

Elroy currently displays a "Relevant Context" panel that shows:
- Active memory titles (up to 10 memories)
- Count of additional memories if more than 10 exist
- Updates after each user message

**Implementation Details:**
- Location: `elroy/io/cli.py:112-122` (rendering)
- Data source: `elroy/repository/memories/queries.py:275-284`
- Display trigger: After greeting and after each message processing
- Styling: Rich Panel with user_input_color border (#FFE377)

### Problem Statement

Users have limited visibility into Elroy's background operations. When memory consolidation, context compression, or other system tasks are running, there's no indication in the UI. This can lead to:
- Confusion about system behavior
- Lack of transparency in what Elroy is doing
- Missed opportunities to understand system performance
- Difficulty debugging issues with background tasks

### Background Systems Available

**Active Background Processes:**
1. **Context Refresh** (`refresh_context_if_needed`) - Runs 5s after each message
2. **Memory Consolidation** (`consolidate_memories`) - Triggers after 4+ memories created
3. **Memory Creation** (`create_mem_from_current_context`) - Triggers after 20+ messages

**Infrastructure:**
- APScheduler with BackgroundScheduler (20 thread pool)
- MemoryOperationTracker (tracks counters: memories_since_consolidation, messages_since_memory)
- Rich library for terminal UI (supports Live displays, status indicators, progress bars)

## Goals

### Primary Goals
1. Provide real-time visibility into system background operations
2. Surface memory consolidation status and progress
3. Show pending/active scheduled tasks
4. Make system behavior more transparent and understandable

### Secondary Goals
1. Help users understand when Elroy is "thinking" vs idle
2. Enable debugging of background task issues
3. Build foundation for future system health monitoring
4. Maintain clean, uncluttered UI

### Non-Goals
1. Detailed performance metrics (use `/tail_elroy_logs` for that)
2. Historical task execution logs
3. Interactive task control (pause/cancel)
4. Real-time token usage or cost tracking

## User Stories

**As a user, I want to:**
1. See when memory consolidation is running so I understand what Elroy is doing
2. Know how many messages until the next memory creation so I can plan my workflow
3. View active background tasks so I can tell if the system is busy
4. Understand when context compression occurs so I know why some messages drop out

**As a developer, I want to:**
1. Debug background task scheduling issues without checking logs
2. Verify that consolidation triggers at the expected intervals
3. Monitor system health during development

## Requirements

### Functional Requirements

#### FR1: Dual Panel Display
- **Priority:** P0
- **Description:** Create a second panel alongside "Relevant Context" for system status
- **Acceptance Criteria:**
  - Two separate Rich Panels displayed (or one combined panel with sections)
  - System status panel updates independently of memory panel
  - Both panels respect existing color configuration

#### FR2: Background Task Status
- **Priority:** P0
- **Description:** Show currently active and pending scheduled tasks
- **Acceptance Criteria:**
  - Display active tasks from APScheduler.get_jobs()
  - Show task name and scheduled execution time
  - Update when tasks are added/removed
  - Maximum 5 tasks shown (with overflow count)

#### FR3: Memory Operation Counters
- **Priority:** P0
- **Description:** Display progress toward next memory consolidation and creation
- **Acceptance Criteria:**
  - Show "Memories since consolidation: X/4" (configurable threshold)
  - Show "Messages since memory: Y/20" (configurable threshold)
  - Query from MemoryOperationTracker
  - Update after each user message

#### FR4: Active Operations Indicator
- **Priority:** P1
- **Description:** Show when long-running operations are in progress
- **Acceptance Criteria:**
  - Indicate "Memory consolidation in progress" with timestamp
  - Indicate "Context refresh in progress" when running
  - Clear indicator when operation completes

#### FR5: Configuration Toggle
- **Priority:** P0
- **Description:** Allow users to enable/disable system status panel
- **Acceptance Criteria:**
  - New config option: `show_system_status_panel` (default: true)
  - Command-line flag: `--show-system-status-panel` / `--no-show-system-status-panel`
  - Respects existing `show_memory_panel` setting independently

### Non-Functional Requirements

#### NFR1: Performance
- Fetching system status should add < 10ms latency to panel rendering
- Should not block message processing
- Panel updates should not trigger unnecessary database queries

#### NFR2: UI/UX
- Panel should be visually distinct from "Relevant Context"
- Should use consistent Rich styling with rest of interface
- Should not overwhelm the display (keep concise)
- Should gracefully handle edge cases (no active tasks, etc.)

#### NFR3: Maintainability
- System status logic should be separate from memory panel logic
- Easy to add new status indicators in the future
- Should work with both CliIO and PlainIO (graceful degradation)

## Design

### UI Mockup (Terminal Output)

```
┌─ Relevant Context ────────────────────────┐
│ System: Project preferences               │
│ User: Authentication preferences          │
│ Session: Current task context             │
└───────────────────────────────────────────┘

┌─ System Status ───────────────────────────┐
│ Messages since memory: 12/20              │
│ Memories since consolidation: 2/4         │
│                                           │
│ Active Tasks:                             │
│  • Context refresh (in 3s)                │
└───────────────────────────────────────────┘
```

### Alternative: Combined Panel

```
┌─ Elroy Status ────────────────────────────┐
│ Relevant Context:                         │
│  • System: Project preferences            │
│  • User: Authentication preferences       │
│  • Session: Current task context          │
│                                           │
│ System:                                   │
│  • Messages until memory: 8               │
│  • Memories until consolidation: 2        │
│  • Context refresh scheduled (in 3s)      │
└───────────────────────────────────────────┘
```

### Technical Architecture

#### Component Structure

**New Files:**
- `elroy/io/system_status.py` - System status data fetching and formatting
  - `get_system_status_data(ctx: ElroyContext) -> SystemStatus`
  - `SystemStatus` dataclass with fields for tasks, counters, operations

**Modified Files:**
- `elroy/io/cli.py` - Add `print_system_status_panel()` method
- `elroy/cli/ui.py` - Add `print_system_status_panel()` function
- `elroy/cli/chat.py` - Call system status panel rendering
- `elroy/defaults.yml` - Add `show_system_status_panel: true`
- `elroy/config/models.py` - Add config field

#### Data Flow

```
User message processed
    ↓
chat.py calls print_system_status_panel()
    ↓
ui.py fetches system status
    ↓
system_status.py queries:
    - scheduler.get_jobs() → active tasks
    - get_or_create_memory_op_tracker() → counters
    - Check for active operations flags
    ↓
Format as SystemStatus dataclass
    ↓
cli.py.print_system_status_panel() renders Rich Panel
    ↓
Display to user
```

#### Status Data Structure

```python
@dataclass
class SystemStatus:
    """System status information for panel display"""

    # Counters
    messages_since_memory: int
    messages_between_memory: int
    memories_since_consolidation: int
    memories_between_consolidation: int

    # Active tasks
    scheduled_tasks: list[ScheduledTask]

    # Operations in progress
    consolidation_in_progress: bool
    context_refresh_in_progress: bool

@dataclass
class ScheduledTask:
    """Information about a scheduled background task"""
    name: str
    scheduled_time: datetime
    seconds_until_run: float
```

### Display Logic

**When to show each section:**

1. **Counters:** Always show (unless both are 0)
2. **Scheduled tasks:** Show if any exist (max 5)
3. **Active operations:** Show only while in progress

**Update frequency:**
- After each user message (same as memory panel)
- Could add real-time updates every 5s if in progress operations exist

### Configuration

**New settings in `defaults.yml`:**
```yaml
# UI Configuration
show_system_status_panel: true  # Show system execution status
system_status_panel_color: "#77DFD8"  # Color for system status panel border
```

**CLI flags:**
```bash
elroy chat --show-system-status-panel  # Enable
elroy chat --no-show-system-status-panel  # Disable
```

## Implementation Plan

### Phase 1: Foundation (P0)
1. Create `SystemStatus` dataclass and `system_status.py` module
2. Implement basic data fetching from scheduler and MemoryOperationTracker
3. Add configuration option and CLI flag
4. Write unit tests for data fetching

### Phase 2: UI Rendering (P0)
1. Add `print_system_status_panel()` to `cli.py`
2. Add panel rendering to `chat.py` after memory panel
3. Implement basic two-panel layout
4. Test with various screen sizes

### Phase 3: Task Display (P0)
1. Query APScheduler for active jobs
2. Format and display scheduled tasks with countdown
3. Handle edge cases (no tasks, many tasks)
4. Add truncation and overflow handling

### Phase 4: Active Operations (P1)
1. Add tracking for operations in progress
2. Display consolidation/refresh status
3. Clear indicators on completion
4. Add timestamp information

### Phase 5: Polish (P1)
1. Fine-tune colors and styling
2. Add comprehensive error handling
3. Optimize performance
4. Write integration tests
5. Update documentation

## Success Metrics

### Qualitative
- Users report better understanding of system behavior
- Reduced confusion about background operations
- Positive feedback on transparency

### Quantitative
- < 10ms overhead for panel rendering
- Zero crashes or errors from panel display
- 100% test coverage for system_status.py

## Open Questions

1. **Panel placement:** Should system status be above or below relevant context?
   - **Recommendation:** Below, as context is more frequently referenced

2. **Real-time updates:** Should the panel update in real-time during long operations?
   - **Recommendation:** Start with post-message updates, add real-time in Phase 4 if needed

3. **Visual style:** Separate panels or combined panel with sections?
   - **Recommendation:** Start with separate panels for cleaner separation

4. **Mobile/small terminals:** How to handle limited screen space?
   - **Recommendation:** Add `max_panel_width` config, or hide system status on narrow terminals

5. **Historical data:** Should we show recent completions (e.g., "Last consolidation: 2m ago")?
   - **Recommendation:** Phase 5 enhancement, not initial version

## Risks & Mitigations

### Risk 1: Performance Impact
**Impact:** Medium
**Probability:** Low
**Mitigation:**
- Cache scheduler job queries
- Use existing database queries without new joins
- Profile and optimize before release

### Risk 2: UI Clutter
**Impact:** Medium
**Probability:** Medium
**Mitigation:**
- Keep display minimal (5 items max per section)
- Make it easily toggleable
- Allow configuration of panel placement
- User testing before final design

### Risk 3: Stale Data
**Impact:** Low
**Probability:** Medium
**Mitigation:**
- Fetch fresh data on each render
- Add timestamps to show data freshness
- Document update frequency

### Risk 4: Breaking Changes
**Impact:** High
**Probability:** Low
**Mitigation:**
- Default to enabled but easily disabled
- Maintain backward compatibility with PlainIO
- Comprehensive testing across IO types

## Future Enhancements

**Post-MVP ideas:**
1. Embedding cache statistics (hit rate, size)
2. Token usage per session
3. Average response latency
4. Database query performance
5. Real-time Live display during long operations
6. Historical task execution (last 5 completions)
7. System health indicators (red/yellow/green)

## References

- **Issue:** #475
- **Current panel implementation:** `elroy/io/cli.py:112-122`
- **Memory operations:** `elroy/repository/memories/operations.py`
- **Scheduler:** `elroy/core/async_tasks.py`
- **Rich library docs:** https://rich.readthedocs.io/
- **Related issues:** #484 (test caching), #477 (embeddings cache)

## Appendix: Code References

**Key files to modify:**
- `elroy/io/cli.py:112-122` - Current panel rendering
- `elroy/cli/chat.py:148-150` - Panel display trigger
- `elroy/cli/ui.py:11-29` - Panel data fetching
- `elroy/core/async_tasks.py` - Scheduler access
- `elroy/repository/memories/operations.py` - Memory operation tracking
- `elroy/defaults.yml:60` - Configuration

**Background task locations:**
- Context refresh: `elroy/repository/context_messages/operations.py:226-229`
- Memory consolidation: `elroy/repository/memories/consolidation.py:112-135`
- Memory creation: `elroy/repository/memories/operations.py:38-45`
