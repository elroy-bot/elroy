# UI Configuration

These settings control the appearance and behavior of Elroy's user interface.

## Options

* `--show-internal-thought / --no-show-internal-thought`: Show the assistant's internal thought monologue. [default: true]
* `--system-message-color TEXT`: Color for system messages. [default: #9ACD32]
* `--user-input-color TEXT`: Color for user input. [default: #FFE377]
* `--assistant-color TEXT`: Color for assistant output. [default: #77DFD8]
* `--warning-color TEXT`: Color for warning messages. [default: yellow]
* `--internal-thought-color TEXT`: Color for internal thought messages. [default: #708090]

## Internal Thought Display

When `show-internal-thought` is enabled, Elroy will display its internal thought process, including:

- Memory consolidation reasoning
- Tool selection logic
- Reflection on recalled memories
- Decision-making processes

This can be helpful for understanding how Elroy is processing information and making decisions. Disable this option for a cleaner interface focused only on the assistant's responses.

## Color Customization

You can customize the colors used in the terminal interface to match your preferences or terminal theme. Colors can be specified as:

- Named colors (e.g., "red", "blue", "yellow")
- Hexadecimal values (e.g., "#FF0000", "#0000FF")
- RGB values (e.g., "rgb(255,0,0)", "rgb(0,0,255)")

Example:
```bash
elroy --assistant-color "#4287f5" --user-input-color "yellow"
