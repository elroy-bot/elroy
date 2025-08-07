# Scripting

Elroy can be scripted and automated, making it a powerful tool for integrating AI capabilities into your workflows and applications.

## Python API

Elroy provides a Python API that allows you to integrate it into your Python scripts and applications:

```python
from elroy import Elroy

ai = Elroy()

# Create a memory
ai.remember("Important project context")

# Process a message with memory augmentation
response = ai.message("What should I do next on the project?")
print(response)
```

## Example: Automating Release Notes

Here's an example of using Elroy to automate the creation of release notes:

```python
from elroy import Elroy

def generate_release_notes(version, changes):
    ai = Elroy()

    # Provide context about the changes
    ai.remember(f"Changes for version {version}: {changes}")

    # Ask Elroy to generate release notes
    prompt = f"Generate release notes for version {version} based on the changes I've shared."
    release_notes = ai.message(prompt)

    return release_notes

# Usage
changes = """
- Fixed bug in memory consolidation
- Added support for new models
- Improved CLI interface
"""

notes = generate_release_notes("1.2.0", changes)
print(notes)
```

## Shell Scripting

The chat interface accepts input from stdin, so you can pipe text to Elroy:

```bash
# Process a single question
echo "What is 2+2?" | elroy chat

# Create a memory from file content
cat meeting_notes.txt | elroy remember

# Use a specific tool with piped input
echo "Buy groceries" | elroy message --tool create_reminder
```

For more examples, see the [examples directory](https://github.com/elroy-bot/elroy/tree/main/examples) in the Elroy repository.
