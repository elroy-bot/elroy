# ElroyContext Refactoring Requirements

## Overview

This document outlines the requirements for refactoring the `ElroyContext` class into smaller, more focused components while preserving its key characteristics:

1. **Lazy initialization** - Services are only initialized when needed via `@cached_property`
2. **Singleton behavior** - The same context instance is passed around, ensuring services are initialized only once
3. **Configuration flexibility** - Parameters can be provided from various sources

The current `ElroyContext` class has grown too large with over 30 parameters in its constructor and multiple responsibilities. This refactoring aims to improve maintainability while ensuring backward compatibility.

## New Files to Create

1. `elroy/core/config.py` - Contains the `ElroyConfig` class for configuration management
2. `elroy/core/services/` - New directory for service classes
   - `__init__.py` - Package initialization
   - `database.py` - Contains `DatabaseService` class
   - `llm.py` - Contains `LLMService` class
   - `tools.py` - Contains `ToolService` class
   - `user.py` - Contains `UserService` class
   - `memory.py` - Contains `MemoryService` class

## Files to Modify

1. `elroy/core/ctx.py` - Refactor ElroyContext to use the new service classes
2. All files that import and use ElroyContext (36 files identified)

## Implementation Steps

### 1. Create Configuration Container

```python
# elroy/core/config.py
from functools import cached_property
from types import SimpleNamespace

class ElroyConfig:
    """Container for all configuration parameters"""
    def __init__(self, **kwargs):
        # Store all configuration parameters
        self._config = SimpleNamespace(**kwargs)

    def __getattr__(self, name):
        # Handle missing attributes gracefully
        return getattr(self._config, name, None)
```

### 2. Create Service Classes

Each service class should:
- Take ElroyConfig as a constructor parameter
- Use @cached_property for lazy initialization
- Implement the same interface as the corresponding methods in ElroyContext

#### Database Service

```python
# elroy/core/services/database.py
from functools import cached_property
from ...db.db_manager import get_db_manager, DbManager
from ...db.db_session import DbSession

class DatabaseService:
    """Provides database access with lazy initialization"""
    def __init__(self, config):
        self.config = config
        self._db = None

    @cached_property
    def db_manager(self) -> DbManager:
        assert self.config.database_url, "Database URL not set"
        return get_db_manager(self.config.database_url)

    @property
    def db(self) -> DbSession:
        if not self._db:
            raise ValueError("No db session open")
        return self._db

    def set_db_session(self, db: DbSession):
        self._db = db

    def unset_db_session(self):
        self._db = None
```

#### LLM Service

```python
# elroy/core/services/llm.py
from functools import cached_property
from ...config.llm import (
    ChatModel,
    EmbeddingModel,
    get_chat_model,
    get_embedding_model,
    infer_chat_model_name,
)

class LLMService:
    """Provides access to LLM models with lazy initialization"""
    def __init__(self, config):
        self.config = config

    @property
    def is_chat_model_inferred(self) -> bool:
        return self.config.chat_model is None

    @cached_property
    def chat_model(self) -> ChatModel:
        if not self.config.chat_model:
            chat_model_name = infer_chat_model_name()
        else:
            chat_model_name = self.config.chat_model

        return get_chat_model(
            model_name=chat_model_name,
            openai_api_key=self.config.openai_api_key,
            openai_api_base=self.config.openai_api_base,
            api_key=self.config.chat_model_api_key,
            api_base=self.config.chat_model_api_base,
            enable_caching=self.config.enable_caching,
            inline_tool_calls=self.config.inline_tool_calls,
        )

    @cached_property
    def embedding_model(self) -> EmbeddingModel:
        return get_embedding_model(
            model_name=self.config.embedding_model,
            embedding_size=self.config.embedding_model_size,
            api_key=self.config.embedding_model_api_key,
            api_base=self.config.embedding_model_api_base,
            openai_embedding_api_base=self.config.openai_embedding_api_base,
            openai_api_key=self.config.openai_api_key,
            openai_api_base=self.config.openai_api_base,
            enable_caching=self.config.enable_caching,
        )
```

#### Tool Service

```python
# elroy/core/services/tools.py
from functools import cached_property
import re
from typing import List
from ...tools.registry import ToolRegistry

class ToolService:
    """Provides access to tools with lazy initialization"""
    def __init__(self, config):
        self.config = config
        self.allowed_shell_command_prefixes = [
            re.compile(f"^{p}") for p in config.allowed_shell_command_prefixes
        ]

    @cached_property
    def tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry(
            self.config.include_base_tools,
            self.config.custom_tools_path,
            exclude_tools=self.config.exclude_tools,
            shell_commands=self.config.shell_commands,
            allowed_shell_command_prefixes=self.allowed_shell_command_prefixes,
        )
        registry.register_all()
        return registry
```

#### User Service

```python
# elroy/core/services/user.py
from functools import cached_property
from ...repository.user.operations import create_user_id
from ...repository.user.queries import get_user_id_if_exists

class UserService:
    """Provides user-related functionality with lazy initialization"""
    def __init__(self, config, db_service):
        self.config = config
        self.db_service = db_service

    @cached_property
    def user_id(self) -> int:
        return get_user_id_if_exists(self.db_service.db, self.config.user_token) or create_user_id(self.db_service.db, self.config.user_token)
```

#### Memory Service

```python
# elroy/core/services/memory.py
from functools import cached_property
from datetime import timedelta

class MemoryService:
    """Provides memory-related functionality with lazy initialization"""
    def __init__(self, config):
        self.config = config

    @property
    def max_in_context_message_age(self) -> timedelta:
        return timedelta(minutes=self.config.max_context_age_minutes)

    @property
    def min_convo_age_for_greeting(self) -> timedelta:
        return timedelta(minutes=self.config.min_convo_age_for_greeting_minutes)
```

### 3. Refactor ElroyContext

```python
# elroy/core/ctx.py
from functools import cached_property
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, List, Optional

from ..config.paths import get_default_config_path
from ..config.personas import PERSONA
from ..cli.options import DEPRECATED_KEYS, get_resolved_params, resolve_model_alias
from .config import ElroyConfig
from .services.database import DatabaseService
from .services.llm import LLMService
from .services.tools import ToolService
from .services.user import UserService
from .services.memory import MemoryService
from .logging import get_logger

logger = get_logger()

class ElroyContext:
    """Facade that provides access to all services and configuration"""
    _db = None  # Kept for backward compatibility

    def __init__(self, **kwargs):
        # Store all configuration in a single object
        self.config = ElroyConfig(**kwargs)
        self.params = self.config  # For backward compatibility

        # Copy frequently accessed config parameters to the top level for backward compatibility
        self.user_token = kwargs.get('user_token')
        self.show_internal_thought = kwargs.get('show_internal_thought', False)
        self.default_assistant_name = kwargs.get('default_assistant_name')
        self.default_persona = kwargs.get('default_persona') or PERSONA
        self.debug = kwargs.get('debug', False)
        self.max_tokens = kwargs.get('max_tokens')
        self.max_assistant_loops = kwargs.get('max_assistant_loops')
        self.l2_memory_relevance_distance_threshold = kwargs.get('l2_memory_relevance_distance_threshold')
        self.context_refresh_target_tokens = int(kwargs.get('max_tokens', 4000) / 3)
        self.memory_cluster_similarity_threshold = kwargs.get('memory_cluster_similarity_threshold')
        self.min_memory_cluster_size = kwargs.get('min_memory_cluster_size')
        self.max_memory_cluster_size = kwargs.get('max_memory_cluster_size')
        self.memories_between_consolidation = kwargs.get('memories_between_consolidation')
        self.messages_between_memory = kwargs.get('messages_between_memory')
        self.inline_tool_calls = kwargs.get('inline_tool_calls', False)
        self.use_background_threads = kwargs.get('use_background_threads', False)
        self.max_ingested_doc_lines = kwargs.get('max_ingested_doc_lines')
        self.reflect = kwargs.get('reflect', False)
        self.include_base_tools = kwargs.get('include_base_tools', True)
        self.shell_commands = kwargs.get('shell_commands', False)

        # Initialize service references (but not the services themselves)
        self._db_service = None
        self._llm_service = None
        self._tool_service = None
        self._user_service = None
        self._memory_service = None
        self._thread_pool = None

    @classmethod
    def init(cls, **kwargs):
        from ..cli.main import CLI_ONLY_PARAMS, MODEL_ALIASES

        for m in MODEL_ALIASES:
            if kwargs.get(m):
                logger.info(f"Model alias {m} selected")
                resolved = resolve_model_alias(m)
                if not resolved:
                    logger.warning("Model alias not found")
                else:
                    kwargs["chat_model"] = resolved
                del kwargs[m]

        params = get_resolved_params(**{k: v for k, v in kwargs.items() if k not in CLI_ONLY_PARAMS})

        invalid_params = set(params.keys()) - set(cls.__init__.__annotations__.keys()) - {'kwargs'}

        for k in invalid_params:
            if k in DEPRECATED_KEYS:
                logger.warning(f"Ignoring deprecated config (will be removed in future releases): '{k}'")
            else:
                logger.warning(f"Ignoring invalid parameter: {k}")

        return cls(**{k: v for k, v in params.items() if k not in invalid_params})

    # Service accessors with lazy initialization

    @cached_property
    def db_service(self):
        if not self._db_service:
            self._db_service = DatabaseService(self.config)
        return self._db_service

    @cached_property
    def llm_service(self):
        if not self._llm_service:
            self._llm_service = LLMService(self.config)
        return self._llm_service

    @cached_property
    def tool_service(self):
        if not self._tool_service:
            self._tool_service = ToolService(self.config)
        return self._tool_service

    @cached_property
    def user_service(self):
        if not self._user_service:
            self._user_service = UserService(self.config, self.db_service)
        return self._user_service

    @cached_property
    def memory_service(self):
        if not self._memory_service:
            self._memory_service = MemoryService(self.config)
        return self._memory_service

    # Delegate properties to maintain backward compatibility

    @property
    def db(self):
        return self.db_service.db

    @property
    def db_manager(self):
        return self.db_service.db_manager

    @property
    def is_chat_model_inferred(self):
        return self.llm_service.is_chat_model_inferred

    @property
    def chat_model(self):
        return self.llm_service.chat_model

    @property
    def embedding_model(self):
        return self.llm_service.embedding_model

    @property
    def tool_registry(self):
        return self.tool_service.tool_registry

    @property
    def user_id(self):
        return self.user_service.user_id

    @property
    def max_in_context_message_age(self):
        return self.memory_service.max_in_context_message_age

    @property
    def min_convo_age_for_greeting(self):
        return self.memory_service.min_convo_age_for_greeting

    @cached_property
    def thread_pool(self) -> ThreadPoolExecutor:
        if not self._thread_pool:
            self._thread_pool = ThreadPoolExecutor()
        return self._thread_pool

    @cached_property
    def config_path(self) -> Path:
        if self.config.config_path:
            return Path(self.config.config_path)
        else:
            return get_default_config_path()

    # Database session management (for backward compatibility)

    def is_db_connected(self) -> bool:
        return self.db_service.is_db_connected()

    def set_db_session(self, db):
        self._db = db  # For backward compatibility
        self.db_service.set_db_session(db)

    def unset_db_session(self):
        self._db = None  # For backward compatibility
        self.db_service.unset_db_session()
```

## Testing Requirements

### Existing Tests to Check

1. **Core Context Tests**:
   - `tests/test_config.py` - Verify configuration loading and parameter resolution
   - `tests/test_db.py` - Ensure database connections still work properly
   - `tests/test_command.py` - Check command execution with the refactored context

2. **Repository Tests**:
   - `tests/repository/context_messages/` - All tests that use ElroyContext for message handling
   - `tests/repository/memories/` - Tests for memory operations that depend on context
   - `tests/repository/goals/` - Tests for goal management that use context

3. **Messaging Tests**:
   - `tests/messaging/test_basic_messages.py` - Basic message flow tests
   - `tests/messaging/test_consolidate_context.py` - Context consolidation tests
   - `tests/messaging/test_context_refresh.py` - Context refresh functionality

4. **LLM Tests**:
   - `tests/llm/test_query_llm.py` - Verify LLM queries work with refactored context
   - `tests/llm/test_stream_parser.py` - Check stream parsing with new context structure

5. **API Tests**:
   - `tests/test_api.py` - Ensure API functionality works with refactored context

### New Tests to Add

1. **Service-Specific Unit Tests**:
   - `tests/core/services/test_database.py` - Test database service in isolation
     * Test connection management
     * Test session handling
     * Test error conditions

   - `tests/core/services/test_llm.py` - Test LLM service in isolation
     * Test model initialization
     * Test caching behavior
     * Test API key handling

   - `tests/core/services/test_tools.py` - Test tool service in isolation
     * Test registry initialization
     * Test tool registration
     * Test shell command handling

   - `tests/core/services/test_user.py` - Test user service in isolation
     * Test user ID resolution
     * Test user preference handling

   - `tests/core/services/test_memory.py` - Test memory service in isolation
     * Test memory configuration
     * Test time-based calculations

2. **Configuration Tests**:
   - `tests/core/test_config.py` - Test the new ElroyConfig class
     * Test parameter access
     * Test default values
     * Test missing parameter handling

3. **Integration Tests for Service Interactions**:
   - `tests/core/test_service_integration.py` - Test interactions between services
     * Test database and user service interaction
     * Test LLM and tool service interaction

### Test Coverage Requirements

1. **Coverage Targets**:
   - Aim for >90% test coverage for new service classes
   - Maintain existing coverage levels for refactored ElroyContext

2. **Edge Cases to Test**:
   - Configuration with missing parameters
   - Service initialization order dependencies
   - Error handling in service initialization
   - Thread safety of lazy initialization
   - Performance impact of the refactoring

### Test Fixtures

1. **Update Existing Fixtures**:
   - `tests/conftest.py` - Update fixtures that create ElroyContext instances
   - `tests/fixtures/test_config.yml` - Update test configuration if needed

2. **New Fixtures to Create**:
   - `tests/core/services/conftest.py` - Fixtures for service-specific tests
     * Mock configurations for each service
     * Mock dependencies for isolated testing

## Migration Strategy

### Phase 1: Core Implementation

1. Create the new configuration and service classes
2. Refactor ElroyContext to use these classes internally
3. Ensure all backward compatibility properties and methods are in place
4. Run all tests to verify functionality

### Phase 2: Caller Updates

1. Update all 36 files that import ElroyContext to use the new service classes directly where appropriate
2. For each file:
   - Identify which services are actually needed
   - Update function signatures to accept specific services instead of the entire context where possible
   - Update function bodies to use the service methods directly

### Phase 3: Documentation

1. Update documentation to reflect the new architecture:
   - `docs/configuration/context.md` - Document the new context structure
   - Any other relevant documentation

## Benefits

1. **Separation of concerns** - Each service class has a single responsibility
2. **Improved maintainability** - Smaller, focused classes are easier to understand
3. **Better testability** - Each component can be tested in isolation
4. **Preserved lazy initialization** - Services are still only created when first accessed
5. **Backward compatibility** - Existing code continues to work through delegation

## Potential Risks and Mitigations

1. **Risk**: Breaking changes to the ElroyContext API
   **Mitigation**: Thorough testing and ensuring all public methods and properties are preserved

2. **Risk**: Performance impact from additional object creation
   **Mitigation**: Benchmark before and after to ensure no significant performance regression

3. **Risk**: Increased complexity from more classes
   **Mitigation**: Clear documentation and consistent naming conventions
