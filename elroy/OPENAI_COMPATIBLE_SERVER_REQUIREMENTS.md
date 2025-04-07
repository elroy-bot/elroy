# OpenAI-Compatible Server Requirements

## Overview

This document outlines the technical requirements for implementing an OpenAI-compatible endpoint in Elroy that augments chat completion requests with memories. This feature will allow developers to use Elroy's memory capabilities through a familiar API interface that matches OpenAI's chat completion endpoints.

## Functional Requirements

### 1. API Compatibility

1.1. The server MUST implement an endpoint that is compatible with OpenAI's chat completion API:
   - POST `/v1/chat/completions`
   - Accept the same request format as OpenAI's API
   - Return responses in the same format as OpenAI's API

1.2. The server MUST support the following request parameters:
   - `messages`: Array of message objects with `role` and `content`
   - `model`: String identifier for the model to use
   - `stream`: Boolean flag for streaming responses
   - `temperature`, `top_p`, `frequency_penalty`, `presence_penalty`, and other standard OpenAI parameters

1.3. The server MUST support the following response formats:
   - Non-streaming: Complete JSON response
   - Streaming: Server-sent events (SSE) with JSON chunks

### 2. Memory Augmentation

2.1. The server MUST augment chat completion requests with relevant memories:
   - Retrieve memories relevant to the current conversation
   - Include these memories in the context sent to the underlying LLM
   - Ensure the augmentation is transparent to the client

2.2. The server MUST NOT redundantly store messages it has already seen:
   - Implement a message deduplication mechanism
   - Track message IDs or compute hashes of message content
   - Skip storage for messages that have already been processed

2.3. The server MUST preserve system instructions passed to it:
   - Maintain any system message provided in the request
   - Ensure system instructions are not overridden by memory augmentation

### 3. Local Deployment

3.1. The server MUST be runnable locally:
   - Provide a simple command to start the server
   - Support configuration via environment variables and/or config files
   - Document all configuration options

3.2. The server MUST integrate with Elroy's existing configuration system:
   - Use the same database connection
   - Respect model configuration settings
   - Share memory storage with the CLI application

## Technical Requirements

### 4. Server Implementation

4.1. The server SHOULD be implemented using FastAPI:
   - Leverage FastAPI's OpenAPI documentation capabilities
   - Use async handlers for improved performance
   - Implement proper error handling and status codes

4.2. The server MUST support both streaming and non-streaming requests:
   - For non-streaming: Return complete responses
   - For streaming: Implement SSE protocol with proper chunking

4.3. The server SHOULD implement basic authentication (optional for MVP):
   - Support API key authentication as an optional feature
   - When enabled, validate API keys against configured values
   - When disabled, allow all requests without authentication
   - Return appropriate error responses for invalid authentication when enabled

4.4. The server MUST implement the AI client via the Litellm custom handler: https://docs.litellm.ai/docs/providers/custom_llm_server#custom-handler-spec

   The custom handler implementation MUST:
   - Create a class that inherits from `litellm.llms.base.BaseLLM`
   - Implement the following required methods with their correct signatures:
     - `completion(self, *args, **kwargs) -> ModelResponse` - For non-streaming completions
     - `streaming(self, *args, **kwargs) -> Iterator[GenericStreamingChunk]` - For streaming completions
     - `acompletion(self, *args, **kwargs) -> ModelResponse` - Async version of completion
     - `astreaming(self, *args, **kwargs) -> AsyncIterator[GenericStreamingChunk]` - Async version of streaming

   - The implementation SHOULD handle the following parameters in these methods:
     - `model`: The model identifier string
     - `messages`: The array of message objects
     - `temperature`, `top_p`, and other model parameters
     - Any custom parameters needed for memory integration

   - The implementation MUST properly format responses according to the OpenAI API specification:
     - For non-streaming responses: Return a properly structured `ModelResponse` object
     - For streaming responses: Yield properly formatted `GenericStreamingChunk` objects

   - The implementation SHOULD include proper error handling:
     - Create a custom error class inheriting from `Exception`
     - Return appropriate HTTP status codes and error messages

### 5. Memory Integration

5.1. The server MUST integrate with Elroy's memory system:
   - Use existing memory retrieval mechanisms
   - Support semantic search for relevant memories
   - Include retrieved memories in the context

5.2. The server MUST implement conversation tracking and divergence handling:
   - Leverage the existing `Message` and `ContextMessageSet` database models
   - Implement a position-based message comparison approach:
      - Compare each incoming message to its corresponding stored message at the same position in the conversation
      - Use simple exact matching or basic hash comparison (MD5/SHA-256) for efficiency
      - Complex fuzzy matching is not necessary for this use case
      - When a message diverges from its stored counterpart:
          - Discard all subsequent messages in the stored conversation history
          - Store the new message and all following messages
          - This handles conversation branches and ensures context consistency

   - Focus on conversation flow rather than complex message deduplication
   - Skip storage only for exact duplicate messages to avoid unnecessary complexity

5.3. The server MUST support memory creation from conversations:
   - Implement two primary memory creation mechanisms:

       a. **Message-Count-Based Creation**:
       - Create memories after a configurable number of messages (default: 10 messages)
       - Track the number of messages since the last memory creation
       - Trigger memory creation when the threshold is reached
       - Similar to the existing CLI application's approach

       b. **Content-Based Memory Creation**:
       - Pass the conversation to a memory creation function after response generation
       - Include conversation history and the last created memory as context
       - The function determines if the new message warrants a new memory
       - Use the underlying LLM to make this determination

   - Important timing considerations:
       - Memory creation MUST happen *after* a message response has been given
       - This ensures the response is delivered quickly to the client
       - Memory creation should be handled asynchronously when possible

   - Reuse existing memory creation/summarization functionality:
       - Leverage the same memory creation logic used in the CLI application
       - Ensure consistency in memory format and quality across interfaces
       - Maintain compatibility with existing memory retrieval mechanisms

   - Support configuration to enable/disable automatic memory creation
   - Provide configuration options for memory creation thresholds and parameters

### 6. Performance and Scalability

6.1. The server MUST handle concurrent requests:
   - Implement proper connection pooling for database access
   - Use async handlers to prevent blocking
   - Ensure thread safety for shared resources


6.2. The server MAY implement caching as a future enhancement (not required for MVP):
   - Consider caching frequently accessed memories in future versions
   - Consider caching model responses when possible in future versions
   - Design with the possibility of adding caching later

### 7. Configuration
   - The feature MUST reuse model and user configuration as implemented by the `get_resolved_params` function, and the CLI parameters made available in main.py.

## API Specification

### Request Format

```json
{
  "model": "string",
  "messages": [
    {
      "role": "system|user|assistant",
      "content": "string"
    }
  ],
  "temperature": 0.7,
  "top_p": 1,
  "stream": false,
  "max_tokens": 1024,
  "presence_penalty": 0,
  "frequency_penalty": 0
}
```

### Response Format (Non-Streaming)

```json
{
  "id": "string",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "string",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "string"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 456,
    "total_tokens": 579
  }
}
```

### Response Format (Streaming)

```
data: {"id":"string","object":"chat.completion.chunk","created":1234567890,"model":"string","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"string","object":"chat.completion.chunk","created":1234567890,"model":"string","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"string","object":"chat.completion.chunk","created":1234567890,"model":"string","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"string","object":"chat.completion.chunk","created":1234567890,"model":"string","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

## Implementation Plan

### Phase 0: LiteLLM Integration

1. **Create Custom LiteLLM Provider**
   - Create a new module `elroy/web_api/openai_compatible/litellm_provider.py`
   - Implement a custom LiteLLM provider by subclassing `BaseLLM`
   - Integrate with Elroy's memory system
   - **Tests**: Verify the provider correctly augments requests with memories
   - **Command**: `pytest tests/web_api/test_litellm_provider.py`

### Phase 1: Core Server Implementation

1. **Setup Project Structure**
   - Create a new module `elroy/web_api/openai_compatible`
   - Set up FastAPI application structure
   - Implement configuration loading from environment variables
   - **Tests**: Verify configuration loading from different sources
   - **Command**: `pytest tests/web_api/test_openai_config.py`

2. **Basic Endpoint Implementation**
   - Implement the `/v1/chat/completions` endpoint
   - Add request validation using Pydantic models
   - Implement basic response formatting
   - **Tests**: Verify endpoint accepts valid requests and rejects invalid ones
   - **Command**: `pytest tests/web_api/test_openai_endpoints.py`

### Phase 2: Memory Integration

3. **Memory System Integration**
   - Connect to Elroy's existing memory system
   - Implement memory retrieval based on conversation context
   - Add memory augmentation to the prompt
   - **Tests**: Verify memories are correctly retrieved and included in context
   - **Command**: `pytest tests/web_api/test_openai_memory_integration.py`

4. **Conversation Tracking**
   - Implement position-based message comparison
   - Add conversation divergence handling
   - Implement message storage logic
   - **Tests**: Verify conversation branches are correctly handled
   - **Command**: `pytest tests/web_api/test_openai_conversation_tracking.py`

### Phase 3: Advanced Features

5. **Streaming Support**
   - Implement SSE protocol for streaming responses
   - Ensure memory augmentation works with streaming
   - **Tests**: Verify streaming responses match non-streaming in content
   - **Command**: `pytest tests/web_api/test_openai_streaming.py`

6. **Memory Creation**
   - Implement message-count-based memory creation
   - Implement content-based memory creation
   - Ensure memory creation happens after response generation
   - **Tests**: Verify memories are created correctly and asynchronously
   - **Command**: `pytest tests/web_api/test_openai_memory_creation.py`

7. **Authentication (Optional)**
   - Implement API key validation
   - Add configuration for enabling/disabling authentication
   - **Tests**: Verify authentication works when enabled and is bypassed when disabled
   - **Command**: `pytest tests/web_api/test_openai_auth.py`

### Phase 4: Testing and Documentation

8. **Integration Testing**
   - Create end-to-end tests with real LLM calls
   - Test with various conversation scenarios
   - Benchmark performance and optimize as needed
   - **Tests**: Verify complete system works as expected
   - **Command**: `pytest tests/web_api/test_openai_integration.py`

9. **Documentation and Examples**
   - Document API usage with examples
   - Create sample client implementations
   - Add OpenAPI documentation
   - **Tests**: Verify documentation examples work as described
   - **Command**: `pytest elroy/web_api/openai_compatible/tests/test_examples.py`

### Running the Server

The server can be run locally using the following command:

```bash
python -m elroy.web_api.openai_compatible.server
```

Or with specific configuration:

```bash
PORT=8080 ENABLE_MEMORY_CREATION=true python -m elroy.web_api.openai_compatible.server
```

### Development Workflow and Progress Tracking

To ensure smooth development and maintain visibility into progress, the following practices should be followed:

1. **Intermediate Commits**:
   - Make frequent, small commits with clear commit messages
   - Each commit should represent a logical unit of work
   - Use a consistent commit message format, e.g., "feat(openai): Implement basic endpoint structure"
   - Push commits regularly to allow for collaboration and review

2. **Progress Tracking**:
   - Create GitHub issues for each major component or phase
   - Use a project board to track the status of each issue (To Do, In Progress, Review, Done)
   - Link commits to relevant issues using issue numbers in commit messages
   - Update issue descriptions with implementation notes and decisions

3. **Pull Requests**:
   - Create pull requests for each major feature or phase
   - Include comprehensive descriptions of changes and implementation details
   - Reference relevant issues in the PR description
   - Request reviews from team members familiar with the affected components

4. **Documentation Updates**:
   - Update documentation as features are implemented
   - Include inline code comments for complex logic
   - Maintain a changelog of significant changes

This approach ensures that progress is visible, development is incremental, and the codebase remains stable throughout the implementation process.

### Running All Tests

To run all tests for the OpenAI-compatible server:

```bash
pytest tests/web_api/
```

To run tests with coverage reporting:

```bash
pytest --cov=elroy.web_api.openai_compatible tests/web_api/
```

To run a specific test file:

```bash
pytest tests/web_api/test_openai_endpoints.py
```

## Configuration Options

The server should support the following configuration options:

- `PORT`: Port to run the server on (default: 8000)
- `HOST`: Host to bind to (default: 127.0.0.1)
- `ENABLE_AUTH`: Whether to enable API key authentication (default: false)
- `API_KEYS`: Comma-separated list of valid API keys (used only when ENABLE_AUTH is true)
- `ENABLE_MEMORY_CREATION`: Whether to create memories from conversations (default: true)
- `MEMORY_CREATION_INTERVAL`: How often to create memories (default: 10 messages)
- `MAX_MEMORIES_PER_REQUEST`: Maximum number of memories to include (default: 5)
- `RELEVANCE_THRESHOLD`: Threshold for memory relevance (default: 0.7)

These options should be configurable via environment variables, command-line arguments, or a configuration file.

## Limitations and Constraints

- The server will only support the chat completions endpoint, not other OpenAI API endpoints
- Memory augmentation may increase token usage compared to standard OpenAI API calls
- The server requires access to Elroy's database for memory storage and retrieval
- Performance may be affected by the size of the memory database

## Appendix A: Implementation Considerations

### A.1 Message Deduplication Complexity

While complex fuzzy matching techniques for message deduplication were initially considered, they were deemed unnecessary for this use case for the following reasons:

1. **Focus on Conversation Flow**: The primary concern is handling conversation divergence rather than detecting near-duplicate messages
2. **Simplicity and Performance**: Simple exact matching or basic hash comparison provides sufficient functionality with better performance
3. **Memory-Based Context**: Since the system already has access to memories created from previous conversations, complex message deduplication adds limited value
4. **Implementation Complexity**: Advanced fuzzy matching algorithms add significant complexity with diminishing returns for this specific use case

### A.2 Alternative Techniques Considered

Several more complex techniques were evaluated but not selected:

#### A.2.1 Simhash
- Fingerprinting algorithm that preserves similarity
- Good for detecting near-duplicates with slight variations
- **Reason not selected**: Adds complexity without proportional benefit for this use case

#### A.2.2 Character-level n-gram Jaccard similarity
- Good balance between accuracy and speed
- **Reason not selected**: Unnecessary complexity for the primary use case

#### A.2.3 Word vector averaging
- Captures semantic similarity between messages
- **Reason not selected**: Computationally expensive with limited benefit for conversation tracking

#### A.2.4 Composite Key Comparison
- Creates a composite key using role + truncated content + timestamp
- **Reason not selected**: Simple exact matching is sufficient for the use case

#### A.2.5 Message ID Tracking
- Depends on client cooperation, which cannot be guaranteed in an OpenAI-compatible API
- **Reason not selected**: Not universally applicable to all clients

The simplified approach focuses on conversation divergence handling using position-based comparison with exact matching, which provides the necessary functionality while maintaining simplicity and performance.
