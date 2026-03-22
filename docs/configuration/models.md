# Model Selection and Configuration

Elroy supports various AI models for chat and embedding functionality.

## Automatic Model Selection

Elroy will automatically select appropriate models based on available API keys:

| API Key | Chat Model | Embedding Model |
|---------|------------|----------------|
| `ANTHROPIC_API_KEY` | Claude 4.5 Sonnet (`claude-sonnet-4-5-20250929`) | text-embedding-3-small |
| `OPENAI_API_KEY` | GPT-5 (`gpt-5`) | text-embedding-3-small |
| `GEMINI_API_KEY` | Gemini 2.0 Flash (`gemini/gemini-2.0-flash`) | text-embedding-3-small |

## Model Configuration Options

Set via environment variable or config file:

| Config Key | Env Variable | Description | Default |
|---|---|---|---|
| `chat_model` | `ELROY_CHAT_MODEL` | The model to use for chat completions | *Inferred from API keys* |
| `chat_model_api_base` | `ELROY_CHAT_MODEL_API_BASE` | Base URL for OpenAI compatible chat model API | - |
| `chat_model_api_key` | `ELROY_CHAT_MODEL_API_KEY` | API key for OpenAI compatible chat model API | - |
| `embedding_model` | `ELROY_EMBEDDING_MODEL` | The model to use for text embeddings | `text-embedding-3-small` |
| `embedding_model_size` | `ELROY_EMBEDDING_MODEL_SIZE` | The size of the embedding model | `1536` |
| `embedding_model_api_base` | `ELROY_EMBEDDING_MODEL_API_BASE` | Base URL for OpenAI compatible embedding model API | - |
| `embedding_model_api_key` | `ELROY_EMBEDDING_MODEL_API_KEY` | API key for OpenAI compatible embedding model API | - |
| `enable_caching` | `ELROY_ENABLE_CACHING` | Whether to enable caching for the LLM | `true` |

## Model Aliases

The following aliases can be used as the value of `chat_model` (via `ELROY_CHAT_MODEL` or config file):

| Alias | Model |
|-------|-------|
| `sonnet` | Claude 4.5 Sonnet (`claude-sonnet-4-5-20250929`) |
| `opus` | Claude 4.5 Opus (`claude-opus-4-5-20251101`) |
| `haiku` | Claude 3.5 Haiku (`claude-3-5-haiku-20241022`) |
| `o1` | OpenAI o1 (`openai/o1`) |

Example:

```bash
ELROY_CHAT_MODEL=sonnet elroy
```

Or in config file:

```yaml
# ~/.elroy/elroy.conf.yaml
chat_model: sonnet
```
