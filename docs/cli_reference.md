
# CLI Reference

These commands can be run directly from your terminal:

- `elroy chat` - Opens an interactive chat session (default command)
- `elroy message TEXT` - Process a single message and exit
  - Usage: `elroy message "Your message" [--tool TOOL_NAME]`
  - Example: `elroy message "Create a goal" --tool create_goal`

- `elroy remember [TEXT]` - Create a new memory from text or interactively
  - Usage: `elroy remember "Memory text"` or just `elroy remember` for interactive mode
  - Examples:
    - Interactive: `elroy remember` then type your memory
    - Direct: `elroy remember "Important meeting notes"`
    - From file: `cat notes.txt | elroy remember`

- `elroy list-models` - Lists supported chat models and exits
- `elroy print-config` - Shows current configuration and exits
  - `elroy print-config --show-secrets` to include API keys
  - Shows:
    - Current model settings
    - Database configuration
    - Memory management settings
    - Context management settings

- `elroy version` - Show version and exit

- `elroy set-persona TEXT` - Set a custom persona for the assistant
  - Example: `elroy set-persona "You are a helpful coding assistant"`
- `elroy reset-persona` - Removes any custom persona, reverting to the default
- `elroy show-persona` - Print the system persona and exit
- `elroy print-tools` - Display available tools and their schemas


### Shell Integration
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

Note: Running just `elroy` without any command will default to `elroy chat`.
