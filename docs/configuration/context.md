# Context Management

These settings control how Elroy manages the conversation context window.

## Options

* `--max-assistant-loops INTEGER`: Maximum number of loops the assistant can run before tools are temporarily made unavailable (returning for the next user message). [default: 4]
* `--max-tokens INTEGER`: Number of tokens that triggers a context refresh and compression of messages in the context window. [default: 10000]
* `--max-context-age-minutes FLOAT`: Maximum age in minutes to keep. Messages older than this will be dropped from context, regardless of token limits. [default: 720]
* `--min-convo-age-for-greeting-minutes FLOAT`: Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set --first=True (This will override any value for min_convo_age_for_greeting_minutes). [default: 120]
* `--first`: If true, assistant will not send the first message.

## Context Window Management

Elroy automatically manages the conversation context window to prevent token limits from being exceeded. When the number of tokens in the context window exceeds `max-tokens`, Elroy will compress older messages to reduce the token count while preserving the conversation's meaning.

Messages older than `max-context-age-minutes` will be automatically dropped from the context window, regardless of token count.
