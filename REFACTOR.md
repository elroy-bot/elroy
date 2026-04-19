# ElroyContext Refactoring

This document records the `ElroyContext` refactor and the follow-on dependency cleanup that reduced generic service usage across the repository.

## Problem Statement

The original `ElroyContext` class had grown to 85+ parameters and handled multiple concerns:

- **API Configuration**: OpenAI keys, model endpoints
- **Database Management**: Connection strings, session handling
- **Memory/Context Settings**: Clustering, consolidation parameters
- **UI Configuration**: Colors, display preferences
- **Tool Management**: Registry settings, shell commands
- **Runtime Behavior**: Threading, debugging, performance tuning

**Issues Identified:**
- 🔴 **Large Monolithic Class**: 85+ initialization parameters
- 🔴 **Mixed Concerns**: Single class handling unrelated responsibilities
- 🔴 **Parameter Passing Duplication**: 346+ `ctx.` references across 58 files
- 🔴 **Poor Separation**: Configuration, behavior, and state mixed together
- 🔴 **Testing Complexity**: Difficult to test individual concerns in isolation

## Refactoring Approach

### Phase 1: Configuration Extraction ✅

**Completed**: Split monolithic configuration into domain-specific classes while maintaining backward compatibility.

#### Created Config Classes

```python
@dataclass
class DatabaseConfig:
    """Database connection and session configuration."""
    database_url: str

@dataclass  
class ModelConfig:
    """LLM and embedding model configuration."""
    openai_api_key: Optional[str] = None
    chat_model: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    max_tokens: int = 4000
    enable_caching: bool = True
    # ... other model-related settings

@dataclass
class UIConfig:
    """User interface and display configuration."""
    show_internal_thought: bool = False
    system_message_color: str = "bright_blue"
    assistant_color: str = "bright_green"
    # ... other UI settings

@dataclass
class MemoryConfig:
    """Memory management and context configuration."""
    max_context_age_minutes: float = 60.0
    memory_cluster_similarity_threshold: float = 0.85
    l2_memory_relevance_distance_threshold: float = 0.7
    # ... other memory settings

@dataclass
class ToolConfig:
    """Tool and command configuration."""
    custom_tools_path: List[str]
    exclude_tools: List[str] 
    include_base_tools: bool = True
    shell_commands: bool = True
    # ... other tool settings

@dataclass
class RuntimeConfig:
    """Runtime behavior and performance configuration."""
    user_token: str
    debug: bool = False
    use_background_threads: bool = True
    max_assistant_loops: int = 5
    # ... other runtime settings
```

#### Updated ElroyContext

```python
class ElroyContext:
    def __init__(self, **kwargs):
        # Create structured config objects
        self.database_config = DatabaseConfig(database_url=database_url)
        self.model_config = ModelConfig(chat_model=chat_model, ...)
        self.ui_config = UIConfig(show_internal_thought=show_internal_thought, ...)
        self.memory_config = MemoryConfig(max_context_age_minutes=max_context_age_minutes, ...)
        self.tool_config = ToolConfig(custom_tools_path=custom_tools_path, ...)
        self.runtime_config = RuntimeConfig(user_token=user_token, ...)
        
        # Maintain backward compatibility
        self.user_token = user_token
        self.max_tokens = max_tokens
        # ... all existing attributes preserved
```

**Key Benefits Achieved:**
- ✅ **Separation of Concerns**: Each config class handles specific domain
- ✅ **Better Organization**: Related settings grouped logically
- ✅ **Type Safety**: Dataclasses provide better type hints
- ✅ **Zero Breaking Changes**: Full backward compatibility maintained
- ✅ **Foundation for Next Phase**: Ready for dependency narrowing

### Phase 2: Role-Based Repository Extraction ✅

**Goal**: Replace generic `*Service` and `*OperationService` concepts with role-specific components and explicit factories.

```python
# Explicit role objects built from context
def process_message(ctx: ElroyContext, msg: str) -> Iterator[BaseModel]:
    conversation = build_conversation_orchestrator(ctx)
    return conversation.process_message(msg)
```

**Implemented role categories:**
- `Store`: persistence and domain-scoped retrieval
- `Orchestrator`: multi-step workflows and side-effect ordering
- `Indexer`: derived retrieval/index state
- `Builder`: prompt construction and transformation-heavy read logic

**Representative migrations completed:**
- `ConversationService` -> `ConversationOrchestrator`
- `ContextMessageOperationService` -> `ContextMessageStore` + `ContextRefreshOrchestrator` + `SystemPromptBuilder`
- `MemoryOperationService` -> `MemoryStore` + `MemoryLifecycleOrchestrator` + `MemorySummarizer`
- `RecallOperationService` -> `RecallIndexer` + `RecallContextBridge`
- `TaskOperationService` -> `TaskStore`
- `ReminderOperationService` -> `ReminderOrchestrator`
- Remaining generic helper/query names were aligned with the same vocabulary

**Compatibility cleanup completed:**
- Repository `operations.py` facade modules were removed
- Internal and test imports now target the role-specific modules directly

### Phase 3: Dependency Narrowing (Ongoing / Optional)

**Goal**: Reduce broad function-level `ElroyContext` dependencies where explicit role objects improve ownership, testability, and clarity.

```python
def create_due_item(ctx: ElroyContext, name: str, due: datetime | None) -> str:
    reminder_orchestrator = build_reminder_orchestrator(ctx)
    return reminder_orchestrator.do_create_due_item(name, due)

def do_create_due_item(reminder_orchestrator: ReminderOrchestrator, name: str, due: datetime | None) -> str:
    return reminder_orchestrator.do_create_due_item(name, due)
```

This is not a commitment to introduce a DI container. The current direction is to prefer explicit construction and narrow dependencies over framework-heavy injection unless the repo develops a concrete need for it.

## Migration Guidelines

### For Developers

**Current**: Both patterns work
```python
# New structured approach (preferred)
database_url = ctx.database_config.database_url
max_tokens = ctx.model_config.max_tokens
show_thought = ctx.ui_config.show_internal_thought

# Legacy approach (still works)  
database_url = ctx.params.database_url
max_tokens = ctx.max_tokens
show_thought = ctx.show_internal_thought
```

**When narrowing dependencies**: Prefer explicit role objects for code that does not need the whole context
```python
# Broad context dependency
def my_function(ctx: ElroyContext) -> Result:
    memory_store = build_memory_store(ctx)
    return use_memory_store(memory_store)

# Narrow explicit dependency
def my_function(memory_store: MemoryStore) -> Result:
    return use_memory_store(memory_store)
```

### Testing Benefits

**Phase 1**: Can now test config groups in isolation
```python
def test_model_config():
    config = ModelConfig(
        chat_model="gpt-4",
        max_tokens=2000,
        enable_caching=False
    )
    assert config.chat_model == "gpt-4"
    assert config.max_tokens == 2000
```

**Current follow-on work**: Can mock individual role objects
```python
def test_message_processing():
    mock_memory_store = Mock(spec=MemoryStore)
    mock_recall_indexer = Mock(spec=RecallIndexer)
    
    result = process_message("Hello", mock_memory_store, mock_recall_indexer)
    
    mock_recall_indexer.activate_memory.assert_called_once()
```

## Implementation Status

- ✅ **Phase 1**: Configuration extraction (Completed)
  - Created domain-specific config classes
  - Updated ElroyContext to use config objects
  - Maintained full backward compatibility
  - All tests passing

- ✅ **Phase 2**: Role-based repository extraction (Completed)
  - Replaced generic service-style names with `Store`, `Orchestrator`, `Indexer`, and `Builder`
  - Added explicit factories for role construction from `ElroyContext`
  - Removed repository `operations.py` facades after migrating callers
  - Updated internal and test imports to target role-specific modules directly

- 🔄 **Phase 3**: Dependency narrowing (Optional ongoing work)
  - Reduce broad `ElroyContext` function dependencies where beneficial
  - Prefer passing explicit role objects into leaf functions and tests
  - Keep construction simple and local unless stronger abstraction pressure emerges

## Files Changed

### Phase 1
- `elroy/core/configs.py` - New config dataclasses
- `elroy/core/ctx.py` - Updated to use config objects
- Tests verified functionality preserved

### Phase 2 / 3
- Repository role modules under `elroy/repository/**`
- Factory helpers that build role objects from `ElroyContext`
- Continued function signature narrowing where whole-context access is unnecessary

## Functional Programming Considerations

This refactoring respects the codebase's functional programming preferences:

1. **Immutable Config Objects**: Dataclasses are immutable by default
2. **Composition over Inheritance**: Role objects compose focused collaborators
3. **Pure Functions**: Builders and many query helpers can stay pure or read-only
4. **Partial Application**: Can use `functools.partial` to reduce parameter passing

```python
# Functional approach with explicit dependencies
from functools import partial

# Create specialized functions
process_user_message = partial(process_message, enable_tools=True)
get_user_memories = partial(get_memories, user_id=user_id)
```

## Conclusion

This refactoring maintains the functional programming style while providing better organization and separation of concerns. The completed migration replaced generic service abstractions with role-specific components and removed the temporary facade layer once callers were updated.

The remaining work is narrower: continue reducing `ElroyContext` usage only where explicit role dependencies materially improve ownership, testability, or readability.
