# Model Selection and Configuration

Elroy supports various AI models for chat and embedding functionality.

## Automatic Model Selection

Elroy will automatically select appropriate models based on available API keys:

| API Key | Chat Model | Embedding Model |
|---------|------------|----------------|
| `ANTHROPIC_API_KEY` | Claude 3 Sonnet | text-embedding-3-small |
| `OPENAI_API_KEY` | GPT-4o | text-embedding-3-small |
| `GEMINI_API_KEY` | Gemini 2.0 Flash | text-embedding-3-small |

## Model Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--chat-model TEXT` | The model to use for chat completions | *Inferred from API keys* |
| `--chat-model-api-base TEXT` | Base URL for OpenAI compatible chat model API | - |
| `--chat-model-api-key TEXT` | API key for OpenAI compatible chat model API | - |
| `--embedding-model TEXT` | The model to use for text embeddings | text-embedding-3-small |
| `--embedding-model-size INTEGER` | The size of the embedding model | 1536 |
| `--embedding-model-api-base TEXT` | Base URL for OpenAI compatible embedding model API | - |
| `--embedding-model-api-key TEXT` | API key for OpenAI compatible embedding model API | - |
| `--enable-caching / --no-enable-caching` | Whether to enable caching for the LLM | true |

## Model Aliases

Shortcuts for common models:

| Alias | Description |
|-------|-------------|
| `--sonnet` | Use Anthropic's Claude 3 Sonnet model |
| `--opus` | Use Anthropic's Claude 3 Opus model |
| `--4o` | Use OpenAI's GPT-4o model |
| `--4o-mini` | Use OpenAI's GPT-4o-mini model |
| `--o1` | Use OpenAI's o1 model |
| `--o1-mini` | Use OpenAI's o1-mini model |
