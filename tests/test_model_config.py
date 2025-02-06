"""all params follow generic resolution hierchy: passed in param > env var > config val > defaults

# params that should work for all models
chat-model # model name (unchanged) (if model-base-url is set, prefix with openai (for litellm))
chat-model-api-base
chat-model-api-key

embeddings-model # embeddings model name (unchanged)
embeddings-model-base-url (if none and chat-model-base-url is set, use chat-model-base-url)
embeddings-api-key (if none and chat-model-api-key is set, use chat-model-api-key)

# extra params that will also be recognized
openai-api-key # if chat-model-api-key is null, and model is either an openai model or unrecognized, will be used for chat-model-api-key (same logic for embeddings-api-key)

openai-api-base # if chat-model-base-url is not set, and model is either an openai model or unrecognized, will be used for api-base (same for embeddings base)

anthropic_api_key: used if model is recognized as anthropic model
gemini_api_key: used if models is recognized as google model"""
