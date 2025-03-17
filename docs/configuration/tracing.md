# Tracing Configuration

Elroy supports tracing with Arize-Phoenix for monitoring and debugging.

## Overview

Tracing allows you to visualize and analyze the assistant's operations, including:
- Tool calls and their results
- Memory operations
- Context management
- Model interactions

## Configuration Options

* Set the environment variable `ELROY_ENABLE_TRACING=1` to enable tracing
* `ELROY_TRACING_APP_NAME`: Optional name for the tracing application [default: elroy]

## Using Arize-Phoenix

When tracing is enabled, Elroy will send trace data to Arize-Phoenix. To view the traces:

1. Install Arize-Phoenix if you haven't already:
   ```bash
   pip install arize-phoenix
   ```

2. Start the Phoenix UI:
   ```bash
   phoenix ui
   ```

3. Open the Phoenix UI in your browser (typically at http://localhost:6006)

4. View the traces for your Elroy application

## Example Configuration

```bash
# Enable tracing
export ELROY_ENABLE_TRACING=1

# Set a custom application name
export ELROY_TRACING_APP_NAME="my-elroy-assistant"

# Run Elroy
elroy
```

This configuration will send trace data to Arize-Phoenix with the application name "my-elroy-assistant".
