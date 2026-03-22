# Configuration

Elroy offers flexible configuration options to customize its behavior to your needs.

## Configuration Methods

Elroy's configuration can be specified in two ways, in order of precedence:

1. **Environment Variables**: Highest priority. All environment variables are prefixed with `ELROY_` and use uppercase with underscores:
   ```bash
   export ELROY_CHAT_MODEL=gpt-5
   export ELROY_DEBUG=1
   ```

2. **Configuration File**: Lowest priority, overridden by environment variables
   ```yaml
   # ~/.elroy/elroy.conf.yaml
   chat_model: gpt-5
   debug: true
   ```

The configuration file location defaults to `~/.elroy/elroy.conf.yaml` and can be overridden with the `ELROY_CONFIG_PATH` environment variable.

For default config values, see [defaults.yml](https://github.com/elroy-bot/elroy/blob/main/elroy/defaults.yml)

> **Note:** All configuration options can be set via environment variables with the prefix `ELROY_` (e.g., `ELROY_CHAT_MODEL=gpt-5`). The environment variable name is created by converting the option name to uppercase and adding the `ELROY_` prefix.
