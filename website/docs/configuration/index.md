# Configuration

Elroy offers flexible configuration options to customize its behavior to your needs.

## Configuration Methods

Elroy's configuration can be specified in three ways, in order of precedence:

1. **Command Line Flags**: Highest priority, overrides all other settings
   ```bash
   elroy --chat-model claude-sonnet-4-5-20250929
   ```

2. **Environment Variables**: Second priority, overridden by CLI flags. All environment variables are prefixed with `ELROY_` and use uppercase with underscores:
   ```bash
   export ELROY_CHAT_MODEL=gpt-4o
   export ELROY_DEBUG=1
   ```

3. **Configuration File**: Lowest priority, overridden by both CLI flags and environment variables
   ```yaml
   # ~/.config/elroy/config.yaml
   chat_model: gpt-4o
   debug: true
   ```

The configuration file location can be specified with the `--config` flag or defaults to `~/.config/elroy/config.yaml`.

For default config values, see [defaults.yml](https://github.com/elroy-bot/elroy/blob/main/elroy/defaults.yml)

> **Note:** All configuration options can be set via environment variables with the prefix `ELROY_` (e.g.,`ELROY_CHAT_MODEL=gpt-4o`). The environment variable name is created by converting the option name to uppercase and adding the `ELROY_` prefix.
