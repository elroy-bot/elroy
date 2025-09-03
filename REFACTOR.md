# ElroyContext Refactoring

This document outlines the ongoing refactoring of the `ElroyContext` class to address growing complexity and improve maintainability.

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
- ✅ **Foundation for Next Phase**: Ready for service layer extraction

### Phase 2: Service Layer (Planned)

**Goal**: Replace direct context passing with injected services.

```python
# Instead of passing entire context
def process_message(ctx: ElroyContext, msg: str) -> Iterator[BaseModel]:
    llm_response = ctx.llm.generate_completion(...)
    memories = get_relevant_memories(ctx, ...)

# Use focused services  
def process_message(
    llm_service: LlmService, 
    memory_service: MemoryService,
    msg: str
) -> Iterator[BaseModel]:
    llm_response = llm_service.generate_completion(...)
    memories = memory_service.get_relevant_memories(...)
```

**Planned Service Classes:**
- `LlmService`: Model interactions, completions
- `MemoryService`: Memory storage, retrieval, clustering
- `DatabaseService`: Session management, transactions
- `ToolService`: Tool registry, execution
- `UIService`: Display formatting, colors

### Phase 3: Dependency Injection (Future)

**Goal**: Use dependency injection framework for cleaner service management.

```python
# Service container setup
container = Container()
container.bind(DatabaseService, to=DatabaseService, config=db_config)
container.bind(LlmService, to=LlmService, config=model_config)
container.bind(MemoryService, to=MemoryService, 
               deps=[DatabaseService, LlmService], config=memory_config)

# Function signatures become cleaner
@inject
def process_message(
    msg: str,
    llm_service: LlmService = Depends(),
    memory_service: MemoryService = Depends()
) -> Iterator[BaseModel]:
    # Implementation uses injected services
```

## Migration Guidelines

### For Developers

**Current (Phase 1)**: Both patterns work
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

**Future (Phase 2)**: Function signatures will change
```python
# Current
def my_function(ctx: ElroyContext) -> Result:
    return process_with_llm(ctx.llm, ctx.memory_service, ...)

# Future  
def my_function(
    llm_service: LlmService,
    memory_service: MemoryService
) -> Result:
    return process_with_llm(llm_service, memory_service, ...)
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

**Future Phases**: Can mock individual services
```python
def test_message_processing():
    mock_llm = Mock(spec=LlmService)
    mock_memory = Mock(spec=MemoryService) 
    
    result = process_message("Hello", mock_llm, mock_memory)
    
    mock_llm.generate_completion.assert_called_once()
```

## Implementation Status

- ✅ **Phase 1**: Configuration extraction (Completed)
  - Created domain-specific config classes
  - Updated ElroyContext to use config objects
  - Maintained full backward compatibility
  - All tests passing

- 🔄 **Phase 2**: Service layer extraction (Planned)
  - Extract services from ElroyContext
  - Update function signatures to use services
  - Maintain ElroyContext as facade during transition

- 📅 **Phase 3**: Dependency injection (Future)
  - Implement DI container
  - Clean up remaining context passing
  - Full separation of concerns achieved

## Files Changed

### Phase 1
- `elroy/core/configs.py` - New config dataclasses
- `elroy/core/ctx.py` - Updated to use config objects
- Tests verified functionality preserved

### Future Phases
- Service classes in `elroy/services/`
- Function signature updates across codebase
- DI container setup

## Functional Programming Considerations

This refactoring respects the codebase's functional programming preferences:

1. **Immutable Config Objects**: Dataclasses are immutable by default
2. **Composition over Inheritance**: Services compose config objects
3. **Pure Functions**: Services can be designed as pure functions
4. **Partial Application**: Can use `functools.partial` to reduce parameter passing

```python
# Functional approach with services
from functools import partial

# Create specialized functions
process_user_message = partial(process_message, enable_tools=True)
get_user_memories = partial(get_memories, user_id=user_id)
```

## Conclusion

This refactoring maintains the functional programming style while providing better organization and separation of concerns. The phased approach ensures no breaking changes while progressively improving the codebase architecture.

Each phase provides immediate benefits while preparing for the next level of improvement, ultimately resulting in a more maintainable, testable, and understandable codebase.