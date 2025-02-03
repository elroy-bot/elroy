# Tools Guide

### In-Chat Commands
While chatting with Elroy, commands can be used by typing a forward slash (/) followed by the command name. The user or assistant can invoke some commands, while others are available only to the user.


#### Assistant and User Commands
These commands can be used by both users and Elroy:

##### Goal Management
- `/create_goal` - Create a new goal with name, description and optional deadline
- `/rename_goal` - Change a goal's name while preserving its history and status
- `/print_goal` - Display details of a specific goal including status updates
- `/add_goal_to_current_context` - Include a goal in the current conversation
- `/drop_goal_from_current_context` - Remove a goal from the current conversation
- `/add_goal_status_update` - Add progress updates or notes to a goal
- `/mark_goal_completed` - Mark a goal as finished with final status
- `/delete_goal_permanently` - Remove a goal and its entire history
- `/get_active_goal_names` - Show a list of all current active goals

##### Memory Management
- `/create_memory` - Store new information as a long-term memory
- `/print_memory` - Display a specific memory's complete content
- `/add_memory_to_current_context` - Include a memory in the current conversation
- `/drop_memory_from_current_context` - Remove a memory from the current conversation
- `/query_memory` - Search through memories and goals using semantic search

##### Reflection & Contemplation
- `/contemplate [prompt]` - Request Elroy to reflect on the conversation or analyze a specific topic

##### User Preferences
- `/get_user_full_name` - Retrieve your stored full name
- `/set_user_full_name` - Update your full name for personalization
- `/get_user_preferred_name` - Retrieve your stored preferred name/nickname
- `/set_user_preferred_name` - Set your preferred name for casual interaction

##### Development Tools
- `/tail_elroy_logs` - Display Elroy's log output for debugging purposes
- `/make_coding_edit` - Make and manage changes to code files in the repository


#### User-Only Commands
These commands can only be used by human users:

- `/help` - Show all available commands and their descriptions
- `/print_system_instruction` - View the current system instructions that guide Elroy's behavior
- `/refresh_system_instructions` - Refresh and update the system instructions
- `/reset_messages` - Clear the conversation context and start fresh
- `/print_context_messages` - Display the current conversation context and history
- `/add_internal_thought` - Insert a guiding thought for the assistant's reasoning
- `/print_config` - Show current configuration settings and parameters
- `/create_bug_report` - Generate a detailed bug report with current context
- `/set_assistant_name` - Customize the assistant's name
- `/exit` - End the chat session

## Adding your own Tools

You can add your own tools by specifying a directory or Python file via the `--custom-tools-path` parameter.

Tools should be annotated with the either the `@tool` decorator that comes with Elroy, or langchains `@tool` decorator.
