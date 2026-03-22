# Scripting

Elroy is primarily a terminal UI application. For automation and scripting use cases, configure Elroy via environment variables and use the background ingestion feature.

## Configuration via Environment Variables

All Elroy settings can be set through environment variables prefixed with `ELROY_`:

```bash
# Set the model
export ELROY_CHAT_MODEL=gpt-5

# Set user token for separate memory namespaces in scripts
export ELROY_USER_TOKEN=my_script_user

# Launch elroy
elroy
```

## Background Document Ingestion

For workflows that need Elroy to process documents automatically, use background ingestion:

```yaml
# ~/.elroy/elroy.conf.yaml
background_ingest_enabled: true
background_ingest_paths:
  - ~/documents/
  - ~/notes/
background_ingest_interval_minutes: 60
```

## Shell Scripting

Elroy's terminal UI reads from stdin when it is not a TTY, allowing basic piped input. However, interactive scripting workflows are best handled via the slash commands inside the TUI.

For more examples, see the [examples directory](https://github.com/elroy-bot/elroy/tree/main/examples) in the Elroy repository.
