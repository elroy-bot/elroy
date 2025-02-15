# Tools Guide

Elroy provides a set of tools that can be used by typing a forward slash (/) followed by the command name. These tools are organized into the following categories:

### Goal Management
- `/create_goal` - Creates a goal for either the AI or to help the user
- `/rename_goal` - Change a goal's name while preserving its history
- `/print_goal` - Display details of an existing goal and its status
- `/add_goal_to_current_context` - Include a goal in the current conversation
- `/drop_goal_from_current_context` - Remove a goal from current context (does not delete)
- `/add_goal_status_update` - Add progress updates or notes to a goal
- `/mark_goal_completed` - Mark a goal as finished with closing comments
- `/delete_goal_permanently` - Permanently remove a goal and its history

### Memory Management
- `/create_memory` - Store new information as a long-term memory
- `/print_memory` - Retrieve and display a specific memory by exact name
- `/add_memory_to_current_context` - Include a memory in the current conversation
- `/drop_memory_from_current_context` - Remove a memory from context (does not delete)
- `/examine_memories` - Search and synthesize information from memories and goals

### User Preferences
- `/get_user_full_name` - Retrieve stored full name
- `/set_user_full_name` - Update full name
- `/get_user_preferred_name` - Retrieve stored preferred name/nickname
- `/set_user_preferred_name` - Set preferred name for casual interaction

### Utility Tools
- `/contemplate` - Request analysis or reflection on current context
- `/tail_elroy_logs` - Display recent log output for debugging
- `/make_coding_edit` - Make changes to code using a specialized coding LLM

## Adding Custom Tools

Custom tools can be added by specifying directories or Python files via the `--custom-tools-path` parameter. Tools should be annotated with either:
- The `@tool` decorator from Elroy
- The langchain `@tool` decorator

Both decorators are supported and will work identically.
