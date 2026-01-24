# Elroy Feature Proposals - Complexity & Implementation Analysis

This document evaluates six proposed features for Elroy, analyzing their complexity, relationship to the current codebase, and implementation requirements.

## Table of Contents
1. [Memory Consolidation/Cleanup](#1-memory-consolidationcleanup)
2. [Proactive Context Surfacing](#2-proactive-context-surfacing)
3. [Goal/Project Tracking](#3-goalproject-tracking)
4. [Better Update/Correction Flow](#4-better-updatecorrection-flow)
5. [Conversation Threading](#5-conversation-threading)
6. [Smart Reminder Completion](#6-smart-reminder-completion)
7. [Summary Comparison](#summary-comparison)
8. [Recommended Implementation Order](#recommended-implementation-order)

---

## 1. Memory Consolidation/Cleanup

### Complexity: 🟡 Medium
### Current State: ✅ Partially Exists

### Problem Statement
Memory fragmentation occurs through multiple corrections and updates (e.g., the Bernadette memory example). Users need better tools to consolidate related memories, detect contradictions, and manage outdated information without losing history.

### What Already Exists
- **Automatic background consolidation** using semantic clustering
  - Location: `/repository/memories/consolidation.py`
  - Triggers after 5 new memories (`memories_between_consolidation`)
  - Uses cosine distance threshold of 0.85
  - Merges similar memories automatically on background thread
- **Soft delete support** via `is_active` flag
  - Allows archiving without permanent deletion
  - Tracked in `Memory` table
- **Memory update tracking** via `updated_at` timestamp

### What's Missing
- Manual consolidation trigger for specific memories
- Contradiction detection between memories
- Historical versioning and change tracking
- UI to view/restore archived memories
- Consolidation preview before merging

### Implementation Approach

#### New Tools Needed
```python
@tool
def consolidate_related_memories(
    ctx: ElroyContext,
    memory_names: list[str]
) -> str:
    """Manually consolidate a set of related memories into one."""
    # Validate all memories exist
    # Use LLM to create merged version
    # Archive old memories with reference to merged one
    # Create new consolidated memory

@tool
def detect_memory_conflicts(ctx: ElroyContext) -> str:
    """Scan memories for contradictory information."""
    # Use embeddings to find similar memories
    # LLM analysis to detect contradictions
    # Return report with conflicting pairs

@tool
def archive_memory(
    ctx: ElroyContext,
    name: str,
    reason: str
) -> str:
    """Archive a memory with reason (vs hard delete)."""
    # Set is_active = False
    # Store reason in new archive_reason field

@tool
def view_archived_memories(ctx: ElroyContext) -> str:
    """List all archived memories with archive reasons."""
```

#### Database Changes
```python
# Add to Memory model:
class Memory(SQLModel):
    # ... existing fields ...
    archive_reason: Optional[str] = None
    consolidated_into_id: Optional[int] = None  # FK to replacement memory
```

#### Key Files to Modify
- `/repository/memories/tools.py` - Add new tools
- `/repository/memories/consolidation.py` - Enhance consolidation logic
- `/db/db_models.py` - Update Memory model

### Technical Challenges
- **Contradiction detection** requires expensive LLM-based reasoning
- **Memory lineage tracking** needs thoughtful schema design
- **Preview UI** for consolidation results before committing
- **Balancing automatic vs manual** consolidation workflows

### Estimated Effort
- **LOC:** ~200 new lines
- **DB Changes:** Minor (1-2 new fields, 1 optional table for lineage)
- **Risk Level:** Low

---

## 2. Proactive Context Surfacing

### Complexity: 🟠 Medium-High
### Current State: ❌ Doesn't Exist

### Problem Statement
Currently, memories are only recalled at session start or when explicitly searched. Relevant context could surface organically during conversation (e.g., "this reminds me of when you talked about X").

### What Already Exists
- **Semantic memory search** via `get_relevant_memories_and_reminders()`
  - Location: `/repository/recall/recall.py`
  - Uses L2 distance threshold of 0.7
  - Returns memories based on query embedding
- **Memory recall classifier** (fast heuristics + LLM)
  - Location: `/repository/recall/recall_classifier.py`
  - Decides when to skip memory retrieval
  - Two-stage: fast checks then LLM classification
- **Synthetic tool call injection** for adding memories to context
  - Memories added via `to_fast_recall_tool_call()`

### What's Missing
- Mid-conversation memory triggering
- Proactive "association detected" interjections
- Confidence thresholds for interruption
- User preference controls for proactivity level

### Implementation Approach

#### New Component
```python
class ProactiveRecallMonitor:
    """Monitors conversation for strong memory associations."""

    def __init__(self, config: ProactiveRecallConfig):
        self.relevance_threshold = config.relevance_threshold  # e.g., 0.85
        self.enabled = config.enabled
        self.cooldown_messages = config.cooldown  # Avoid spam

    async def analyze_message(
        self,
        message: str,
        current_context_memory_ids: set[int]
    ) -> Optional[ProactiveRecallSuggestion]:
        """Check if message strongly relates to any memory."""
        # Generate embedding for message
        embedding = await self.embed(message)

        # Query vector store with higher threshold
        memories = query_vector(
            embedding,
            threshold=self.relevance_threshold,
            exclude_ids=current_context_memory_ids
        )

        if not memories:
            return None

        # LLM verification: "Is this memory worth mentioning now?"
        suggestion = await self.verify_relevance(message, memories[0])
        return suggestion
```

#### Integration Points
```python
# In messenger/messenger.py chat loop:
async def chat(self, user_input: str):
    # After user message, before LLM call:
    if self.proactive_recall_enabled:
        suggestion = await self.proactive_monitor.analyze_message(
            user_input,
            self.current_memory_ids
        )

        if suggestion and suggestion.confidence > 0.8:
            # Inject as system message or assistant interjection
            self.inject_proactive_recall(suggestion.memory, suggestion.reason)
```

#### New Configuration
```python
class ProactiveRecallConfig:
    enabled: bool = False  # Opt-in feature
    relevance_threshold: float = 0.85  # Higher than regular recall
    cooldown_messages: int = 5  # Don't trigger every message
    confidence_threshold: float = 0.8  # LLM verification threshold
```

#### Key Files to Modify
- `/repository/recall/` - New `proactive_recall.py` module
- `/messenger/messenger.py` - Integration into chat loop
- `/core/configs.py` - Add ProactiveRecallConfig

### Technical Challenges
- **Latency impact** - Adds embedding + query to every user message
  - Mitigation: Cache recent embeddings, use fast embedding model
- **Over-triggering risk** - Could become annoying
  - Mitigation: Cooldown period, high confidence threshold, user controls
- **UX design** - How to present proactive recalls naturally
  - Option 1: Synthetic system message before LLM response
  - Option 2: LLM tool that can be called mid-response
  - Option 3: Subtle annotation in UI
- **Context window pressure** - Proactive recalls consume tokens

### Estimated Effort
- **LOC:** ~300 new lines
- **DB Changes:** None
- **Risk Level:** Medium (UX risk, performance risk)

---

## 3. Goal/Project Tracking

### Complexity: 🔴 High
### Current State: ❌ Doesn't Exist

### Problem Statement
Users brainstorm goals and projects (job search, planning leave, etc.) but these live in scattered memories. A structured goal system with sub-tasks, progress tracking, and check-ins would provide better organization.

### What Already Exists
- **Reminders** with status tracking
  - Location: `/repository/reminders/`
  - Status: "created", "completed", "deleted"
  - Context-based and timed triggers
- **Memory system** stores unstructured goal information
  - Can search and recall goal-related conversations

### What's Missing
- Structured goal hierarchy (goals → milestones → tasks)
- Progress tracking over time
- Automated check-in scheduling
- Decision timeline/audit trail
- Goal relationships and dependencies

### Implementation Approach

#### New Data Models
```python
class Goal(SQLModel, table=True):
    """Structured goals with hierarchy support."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    description: str
    status: GoalStatus  # "active", "completed", "abandoned", "blocked"
    parent_goal_id: Optional[int] = Field(default=None, foreign_key="goal.id")
    target_date: Optional[datetime] = None
    priority: int = Field(default=0)  # For ordering

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Relationships
    sub_goals: list["Goal"] = Relationship(back_populates="parent_goal")
    updates: list["GoalUpdate"] = Relationship(back_populates="goal")


class GoalUpdate(SQLModel, table=True):
    """Progress updates and notes on goals."""
    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goal.id")
    update_text: str
    progress_percentage: Optional[float] = None  # 0-100

    created_at: datetime = Field(default_factory=datetime.utcnow)

    goal: Goal = Relationship(back_populates="updates")


class GoalCheckin(SQLModel, table=True):
    """Scheduled check-ins for goals."""
    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goal.id")
    interval_days: int  # How often to check in
    last_checkin: datetime
    next_checkin: datetime
    reminder_id: Optional[int] = Field(foreign_key="reminder.id")
```

#### New Tools
```python
@tool
def create_goal(
    ctx: ElroyContext,
    name: str,
    description: str,
    parent_goal: Optional[str] = None,
    target_date: Optional[str] = None
) -> str:
    """Create a new goal, optionally as a sub-goal."""

@tool
def update_goal_progress(
    ctx: ElroyContext,
    goal_name: str,
    update_text: str,
    progress_percentage: Optional[float] = None
) -> str:
    """Add a progress update to a goal."""

@tool
def complete_goal(
    ctx: ElroyContext,
    goal_name: str,
    completion_notes: Optional[str] = None
) -> str:
    """Mark a goal as completed."""

@tool
def list_active_goals(
    ctx: ElroyContext,
    show_hierarchy: bool = True
) -> str:
    """List all active goals, optionally showing sub-goal structure."""

@tool
def schedule_goal_checkin(
    ctx: ElroyContext,
    goal_name: str,
    interval_days: int
) -> str:
    """Schedule periodic check-ins for a goal."""
    # Creates a recurring reminder linked to goal

@tool
def view_goal_timeline(
    ctx: ElroyContext,
    goal_name: str
) -> str:
    """Show update history and timeline for a goal."""
```

#### Repository Layer
```python
# /repository/goals/operations.py
def create_goal(...) -> Goal
def get_goal_by_name(...) -> Optional[Goal]
def update_goal_progress(...) -> GoalUpdate
def get_goal_hierarchy(...) -> dict  # Nested structure
def get_blocked_goals(...) -> list[Goal]
def schedule_checkin_reminder(...) -> Reminder

# /repository/goals/queries.py
def get_active_goals(...) -> list[Goal]
def get_overdue_goals(...) -> list[Goal]
def get_goal_completion_rate(...) -> float
```

#### Key Files to Create
- `/repository/goals/` - New module
  - `operations.py` - CRUD operations
  - `queries.py` - Complex queries
  - `tools.py` - Tool definitions
  - `models.py` - Data models (or add to db_models.py)

### Technical Challenges
- **Schema complexity** - Three new tables with relationships
- **Migration path** - How to convert existing goal-related memories?
- **Reminder integration** - Check-ins create reminders; need clean integration
- **Progress metrics** - Defining meaningful progress measurements
- **UI complexity** - Hierarchical display requires careful formatting
- **Overlap with reminders** - When to use goals vs reminders?

### Estimated Effort
- **LOC:** ~500 new lines
- **DB Changes:** Major (3 new tables)
- **Risk Level:** High (significant architectural addition)

---

## 4. Better Update/Correction Flow

### Complexity: 🟢 Low-Medium
### Current State: ⚠️ Suboptimal

### Problem Statement
When updating memories (like the Bernadette date correction), information gets appended rather than replaced, leading to confusion about what's current vs historical.

### What Already Exists
- **Update tool** via `update_outdated_or_incorrect_memory()`
  - Location: `/repository/memories/tools.py:246`
  - Appends correction to memory text
  - Updates `updated_at` timestamp
  - Regenerates embeddings
- **Timestamp tracking** of when memories were updated

### What's Missing
- Replace vs append modes
- Visual distinction between current and historical info
- Structured change log per memory
- Preview of updated memory before saving

### Implementation Approach

#### Enhanced Update Tool
```python
@tool
def update_memory(
    ctx: ElroyContext,
    name: str,
    correction: str,
    mode: Literal["append", "replace"] = "append",
    track_history: bool = True
) -> str:
    """Update a memory with append or replace mode.

    Args:
        name: Memory name to update
        correction: New or corrected information
        mode: "append" adds to existing text, "replace" overwrites it
        track_history: If True, saves old version to history
    """
    memory = get_memory_by_name(ctx, name)

    if track_history:
        # Save edit to history
        create_memory_edit(
            memory_id=memory.id,
            previous_text=memory.text,
            new_text=correction,
            edit_mode=mode,
            reason=f"Updated via {mode} mode"
        )

    if mode == "replace":
        memory.text = correction
    else:  # append
        timestamp = ctx.clock.now().strftime("%Y-%m-%d")
        memory.text += f"\n\n[Updated {timestamp}]: {correction}"

    memory.updated_at = ctx.clock.now()
    save_memory(memory)
    update_memory_embedding(memory)

    return f"Memory '{name}' updated via {mode} mode."
```

#### New Data Model for History
```python
class MemoryEdit(SQLModel, table=True):
    """Track history of edits to memories."""
    id: Optional[int] = Field(default=None, primary_key=True)
    memory_id: int = Field(foreign_key="memory.id")
    previous_text: str
    new_text: str
    edit_mode: str  # "append" or "replace"
    edit_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    memory: Memory = Relationship(back_populates="edit_history")

# Add to Memory model:
class Memory(SQLModel, table=True):
    # ... existing fields ...
    edit_history: list[MemoryEdit] = Relationship(back_populates="memory")
```

#### New Tool for History
```python
@tool
def view_memory_history(
    ctx: ElroyContext,
    name: str
) -> str:
    """View the edit history of a memory."""
    memory = get_memory_by_name(ctx, name)
    edits = get_memory_edits(memory.id)

    # Format chronological change log
    output = f"Edit history for '{name}':\n\n"
    for edit in edits:
        output += f"[{edit.created_at}] {edit.edit_mode.upper()}\n"
        if edit.edit_mode == "replace":
            output += f"  Previous: {truncate(edit.previous_text)}\n"
        output += f"  New: {truncate(edit.new_text)}\n\n"

    return output
```

#### Key Files to Modify
- `/repository/memories/tools.py` - Enhance update_outdated_or_incorrect_memory()
- `/db/db_models.py` - Add MemoryEdit model
- `/repository/memories/operations.py` - Add history tracking functions
- Create migration for new MemoryEdit table

### Technical Challenges
- **Storage overhead** - Edit history could grow large for frequently updated memories
  - Mitigation: Optional history tracking, retention limits
- **Intent detection** - Auto-detecting when to replace vs append
  - Mitigation: Explicit mode parameter, default to append for safety
- **Display formatting** - Multi-version memories need clear presentation
- **Migration** - No history for existing memories (acceptable)

### Estimated Effort
- **LOC:** ~150 new lines
- **DB Changes:** Minor (1 new table)
- **Risk Level:** Low

---

## 5. Conversation Threading

### Complexity: 🟠 Medium-High
### Current State: ❌ Doesn't Exist

### Problem Statement
Ongoing conversations (like the December 16 anger management discussion) lack structure for follow-up. Users need a way to mark conversations as ongoing, resume them later, and schedule check-ins.

### What Already Exists
- **Message persistence** via `Message` table
  - Location: `/db/db_models.py`
  - Stores all conversation history
- **Context message sets** via `ContextMessageSet`
  - Groups messages for context management
  - Tracks active context set
- **Context compression** and summarization
  - Location: `/repository/context_messages/operations.py`
  - Creates summaries of old messages
- **Memory system** captures conversation outcomes

### What's Missing
- Explicit conversation threads with status
- Thread resumption/continuation
- Scheduled follow-ups on threads
- Thread resolution tracking
- Thread-specific context loading

### Implementation Approach

#### New Data Model
```python
class ConversationThread(SQLModel, table=True):
    """Structured conversation threads with status tracking."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    description: str
    status: ThreadStatus  # "active", "resolved", "paused"

    # Message tracking
    context_message_set_ids: str = Field(default="[]")  # JSON list
    first_message_id: int = Field(foreign_key="message.id")
    last_message_id: Optional[int] = Field(foreign_key="message.id")

    # Temporal tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_discussed: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    # Follow-up reminder
    followup_reminder_id: Optional[int] = Field(foreign_key="reminder.id")

    # Tags for categorization
    tags: str = Field(default="[]")  # JSON list of strings


class ThreadStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    PAUSED = "paused"
```

#### New Tools
```python
@tool
def start_thread(
    ctx: ElroyContext,
    name: str,
    description: str,
    tags: Optional[list[str]] = None
) -> str:
    """Start a new conversation thread to track ongoing discussions."""

@tool
def mark_thread_resolved(
    ctx: ElroyContext,
    thread_name: str,
    resolution_summary: Optional[str] = None
) -> str:
    """Mark a conversation thread as resolved."""
    # Update status
    # Create memory with resolution summary if provided

@tool
def continue_thread(
    ctx: ElroyContext,
    thread_name: str
) -> str:
    """Resume a previous conversation thread.

    Loads relevant context from the thread's history into current context.
    """
    # Load thread's message sets
    # Add summary to context
    # Update last_discussed timestamp

@tool
def schedule_thread_followup(
    ctx: ElroyContext,
    thread_name: str,
    days_until: int,
    followup_prompt: str
) -> str:
    """Schedule a reminder to follow up on a thread."""
    # Create timed reminder
    # Link to thread
    # Update thread.followup_reminder_id

@tool
def list_threads(
    ctx: ElroyContext,
    status: Optional[ThreadStatus] = None,
    tags: Optional[list[str]] = None
) -> str:
    """List conversation threads, optionally filtered by status or tags."""

@tool
def pause_thread(
    ctx: ElroyContext,
    thread_name: str
) -> str:
    """Pause an active thread (neither active nor resolved)."""
```

#### Session Start Integration
```python
# In messenger/messenger.py or session initialization:
async def check_active_threads(ctx: ElroyContext) -> Optional[str]:
    """Check for active threads at session start."""
    active_threads = get_threads_by_status(ctx, ThreadStatus.ACTIVE)

    if active_threads:
        thread_list = "\n".join([f"- {t.name}" for t in active_threads])
        return f"You have {len(active_threads)} active thread(s):\n{thread_list}\n\nWould you like to continue any of these?"

    return None
```

#### Key Files to Create/Modify
- `/repository/threads/` - New module
  - `operations.py` - Thread CRUD
  - `tools.py` - Tool definitions
  - `queries.py` - Thread queries
- `/db/db_models.py` - Add ConversationThread model
- `/messenger/messenger.py` - Session start integration
- Create Alembic migration

### Technical Challenges
- **Thread boundary definition** - When does a thread end vs pause?
  - Mitigation: User-driven status changes, no automatic thread closure
- **Context loading** - Old threads may have large context
  - Mitigation: Load summary instead of full messages
  - Option: Smart context selection (most relevant messages)
- **Interaction with context management** - How do thread messages fit with current context window?
  - Mitigation: Treat as background context, similar to memories
- **Thread-memory relationship** - Should threads create memories automatically?
  - Consideration: Threads might be more ephemeral than memories
- **Tag system** - Need consistent tagging vocabulary
  - Mitigation: Free-form tags, optional autocomplete from existing

### Estimated Effort
- **LOC:** ~400 new lines
- **DB Changes:** Moderate (1 new table, possible FK to messages)
- **Risk Level:** Medium (complex context management interaction)

---

## 6. Smart Reminder Completion

### Complexity: 🟡 Medium
### Current State: ❌ Doesn't Exist

### Problem Statement
Reminders require manual completion even when the conversation clearly indicates the task was addressed. Smart detection could suggest completions and expire stale reminders.

### What Already Exists
- **Manual completion** via `complete_reminder()` tool
  - Location: `/repository/reminders/tools.py`
  - Marks status as "completed"
  - Accepts optional comment
- **Contextual triggering** via semantic search
  - Location: `/repository/recall/recall.py`
  - Surfaces reminders when conversation matches context
- **Status tracking** in Reminder model

### What's Missing
- Auto-detection of completion from conversation
- Suggestion engine for marking complete
- Stale reminder expiry
- Confidence-based completion recommendations

### Implementation Approach

#### New Component
```python
class ReminderCompletionDetector:
    """Analyzes conversation for potential reminder completions."""

    def __init__(self, config: ReminderCompletionConfig):
        self.enabled = config.enabled
        self.auto_complete_threshold = config.auto_complete_threshold
        self.suggest_threshold = config.suggest_threshold
        self.staleness_days = config.staleness_days

    async def analyze_for_completion(
        self,
        reminder: Reminder,
        recent_messages: list[Message],
        context: ElroyContext
    ) -> Optional[CompletionSuggestion]:
        """Check if reminder was addressed in recent conversation."""

        # Build prompt for LLM
        prompt = f"""Based on this conversation:
{format_messages(recent_messages)}

Was this reminder addressed or completed?
Reminder: {reminder.name}
Context: {reminder.text}

Respond with:
- completed: true/false
- confidence: 0.0-1.0
- reasoning: brief explanation
"""

        # Call LLM (use fast model)
        response = await context.llm_client.complete(prompt, model="fast")
        suggestion = parse_completion_suggestion(response)

        return suggestion if suggestion.confidence > self.suggest_threshold else None

    async def check_stale_reminders(
        self,
        context: ElroyContext
    ) -> list[Reminder]:
        """Find reminders that haven't been discussed in a long time."""
        cutoff_date = context.clock.now() - timedelta(days=self.staleness_days)

        active_reminders = get_active_reminders(context)
        stale = []

        for reminder in active_reminders:
            # Check if reminder mentioned recently
            last_mention = get_last_reminder_mention(reminder.id, cutoff_date)
            if not last_mention:
                stale.append(reminder)

        return stale
```

#### Configuration
```python
class ReminderCompletionConfig:
    enabled: bool = False  # Opt-in
    suggest_threshold: float = 0.7  # Suggest if confidence > 0.7
    auto_complete_threshold: float = 0.95  # Auto-complete if > 0.95
    staleness_days: int = 90  # Consider stale after 90 days
    check_frequency_messages: int = 5  # Check every N messages
```

#### Integration Points
```python
# In messenger/messenger.py after each assistant response:
async def chat(self, user_input: str):
    # ... existing chat logic ...

    if self.message_count % self.completion_check_frequency == 0:
        await self.check_reminder_completions()

async def check_reminder_completions(self):
    """Check if any active reminders should be completed."""
    active_reminders = get_active_reminders(self.context)
    recent_messages = get_recent_messages(self.context, limit=10)

    for reminder in active_reminders:
        suggestion = await self.completion_detector.analyze_for_completion(
            reminder,
            recent_messages,
            self.context
        )

        if not suggestion:
            continue

        if suggestion.confidence > self.auto_complete_threshold:
            # Auto-complete with high confidence
            complete_reminder(
                self.context,
                reminder.name,
                comment=f"Auto-completed: {suggestion.reasoning}"
            )
            self.notify_user(f"Marked '{reminder.name}' as complete (high confidence)")

        elif suggestion.confidence > self.suggest_threshold:
            # Suggest to user
            self.offer_completion_suggestion(reminder, suggestion)
```

#### New Tools
```python
@tool
def suggest_reminder_completions(ctx: ElroyContext) -> str:
    """Analyze active reminders and suggest which might be completed."""
    detector = ReminderCompletionDetector(ctx.config.reminder_completion)
    recent_messages = get_recent_messages(ctx, limit=20)

    suggestions = []
    for reminder in get_active_reminders(ctx):
        suggestion = await detector.analyze_for_completion(
            reminder, recent_messages, ctx
        )
        if suggestion:
            suggestions.append((reminder, suggestion))

    # Format output
    if not suggestions:
        return "No completion suggestions found."

    output = "Suggested completions:\n\n"
    for reminder, suggestion in suggestions:
        output += f"- {reminder.name}\n"
        output += f"  Confidence: {suggestion.confidence:.0%}\n"
        output += f"  Reason: {suggestion.reasoning}\n\n"

    return output

@tool
def expire_stale_reminders(
    ctx: ElroyContext,
    days_old: int = 90,
    auto_delete: bool = False
) -> str:
    """Find and optionally delete reminders not discussed in N days."""
    detector = ReminderCompletionDetector(ctx.config.reminder_completion)
    detector.staleness_days = days_old

    stale = await detector.check_stale_reminders(ctx)

    if auto_delete:
        for reminder in stale:
            delete_reminder(ctx, reminder.name, reason="Expired due to staleness")
        return f"Deleted {len(stale)} stale reminder(s)."
    else:
        reminder_list = "\n".join([f"- {r.name}" for r in stale])
        return f"Found {len(stale)} stale reminder(s):\n{reminder_list}"
```

#### Key Files to Create/Modify
- `/repository/reminders/completion_detector.py` - New module
- `/repository/reminders/tools.py` - Add new tools
- `/messenger/messenger.py` - Integration for auto-checking
- `/core/configs.py` - Add ReminderCompletionConfig

### Technical Challenges
- **False positives** - Marking incomplete reminders as done
  - Mitigation: High confidence threshold for auto-complete, lower for suggestions
  - User confirmation for borderline cases
- **LLM inference cost** - Checking every reminder on every Nth message
  - Mitigation: Only check contextually triggered reminders
  - Use fast/cheap model for detection
  - Cache recent analyses
- **Staleness definition** - What counts as "discussed"?
  - Option 1: Semantic similarity to reminder
  - Option 2: Explicit reminder mentions in context
  - Option 3: User tagging
- **User annoyance** - Over-suggesting completions
  - Mitigation: Configurable thresholds, check frequency
  - Batch suggestions rather than interrupting

### Estimated Effort
- **LOC:** ~250 new lines
- **DB Changes:** None (uses existing tables)
- **Risk Level:** Medium (false positive risk, UX sensitivity)

---

## Summary Comparison

| Feature | Complexity | Foundation | New LOC | DB Changes | Risk | Value |
|---------|-----------|------------|---------|-----------|------|-------|
| **1. Memory Consolidation** | 🟡 Medium | Strong (auto-consolidation exists) | ~200 | Minor (1-2 fields) | Low | High |
| **2. Proactive Recall** | 🟠 Med-High | Moderate (search exists) | ~300 | None | Medium | High |
| **3. Goal Tracking** | 🔴 High | Weak (only reminders) | ~500 | Major (3 tables) | High | Very High |
| **4. Update/Correction Flow** | 🟢 Low-Med | Good (update exists) | ~150 | Minor (1 table) | Low | Medium |
| **5. Conversation Threading** | 🟠 Med-High | Moderate (context sets) | ~400 | Moderate (1 table) | Medium | Medium-High |
| **6. Smart Completion** | 🟡 Medium | Weak (manual only) | ~250 | None | Medium | Medium |

### Complexity Legend
- 🟢 **Low** - Straightforward enhancement to existing systems
- 🟡 **Medium** - New component with moderate integration
- 🟠 **Medium-High** - Significant new functionality with complex integration
- 🔴 **High** - Major new subsystem requiring extensive changes

### Risk Factors
- **Low Risk** - Well-defined scope, minimal user-facing changes
- **Medium Risk** - UX sensitivity, performance considerations, or moderate architectural impact
- **High Risk** - Significant architectural changes, complex migrations, or unproven UX patterns

---

## Recommended Implementation Order

Based on **value-to-effort ratio** and **dependency analysis**:

### Phase 1: Quick Wins (Low-hanging fruit)
1. **#4: Better Update/Correction Flow**
   - **Why first:** Low complexity, addresses immediate pain point (Bernadette correction example)
   - **Effort:** 1-2 weeks
   - **Deliverables:** Replace mode, change history tracking
   - **Dependencies:** None

2. **#1: Memory Consolidation/Cleanup**
   - **Why second:** Builds on existing consolidation system, clear user need
   - **Effort:** 2-3 weeks
   - **Deliverables:** Manual consolidation, conflict detection, archive viewing
   - **Dependencies:** Benefits from #4 (history tracking can be reused)

### Phase 2: Enhanced Intelligence (Medium complexity)
3. **#6: Smart Reminder Completion**
   - **Why third:** Standalone feature, no DB changes, high utility
   - **Effort:** 2-3 weeks
   - **Deliverables:** Completion suggestions, staleness detection
   - **Dependencies:** None

4. **#2: Proactive Context Surfacing**
   - **Why fourth:** High UX impact, but needs careful tuning (benefit from user feedback on #6)
   - **Effort:** 3-4 weeks
   - **Deliverables:** Association detection, proactive recall injection
   - **Dependencies:** Can learn from #6's LLM-based inference patterns

### Phase 3: Major Features (High complexity)
5. **#5: Conversation Threading**
   - **Why fifth:** More complex, but synergizes with goal tracking
   - **Effort:** 4-5 weeks
   - **Deliverables:** Thread creation, resumption, follow-up scheduling
   - **Dependencies:** None, but informs goal tracking design

6. **#3: Goal/Project Tracking**
   - **Why last:** Highest complexity, essentially a new subsystem
   - **Effort:** 6-8 weeks
   - **Deliverables:** Goal hierarchy, progress tracking, check-ins
   - **Dependencies:** Benefits from threading patterns (#5), reminder patterns (#6)

### Alternative Approach: User-Driven Prioritization
If specific pain points are more acute, consider this order:
- **If memory management is the biggest issue:** #1 → #4 → #2
- **If reminders are underutilized:** #6 → #1 → #5
- **If goal tracking is urgent:** #3 first (despite complexity)

---

## Next Steps

1. **Validate assumptions** - Confirm these features address real user needs
2. **Choose starting point** - Select #4 or #1 for Phase 1
3. **Create detailed spec** - Expand chosen feature into implementation plan
4. **Prototype and test** - Build MVP, gather feedback before full implementation
5. **Iterate** - Refine based on actual usage patterns

## Questions for Consideration

- **Feature toggles:** Should all new features be opt-in initially?
- **Migration strategy:** How to handle existing data when adding structured systems?
- **Performance budget:** What's acceptable latency for LLM-based features (#2, #6)?
- **UI paradigm:** How to surface these features in a CLI environment?
- **Backwards compatibility:** Support older clients/versions?
