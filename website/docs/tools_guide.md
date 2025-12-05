# Tools Guide

Elroy provides a set of tools that can be used by typing a forward slash (/) followed by the command name. These tools are organized into the following categories:

## Memory Management

| Tool/Command | Description |
|-------------|-------------|
| `/create_memory` | Creates a new memory for the assistant. |
| `/print_memory` | Retrieve and return a memory by its exact name. |
| `/add_memory_to_current_context` | Adds memory with the given name to the current conversation context. |
| `/drop_memory_from_current_context` | Drops the memory with the given name from current context. Does NOT delete the memory. |
| `/update_outdated_or_incorrect_memory` | Updates an existing memory with new information. |
| `/examine_memories` | Search through memories for the answer to a question. |

## Document Management

| Tool/Command | Description |
|-------------|-------------|
| `/get_source_content_for_memory` | Retrieves content of the source for a memory, by source type and name. |
| `/get_source_documents` | Gets the list of ingested source documents. |
| `/get_source_doc_metadata` | Gets metadata about a source document including extraction time and available chunks. |
| `/get_document_excerpt` | Gets text of document excerpt by address and chunk index (0-indexed). Use get_source_doc_metadata to get available chunk indices. |
| `/search_documents` | Search through document excerpts using semantic similarity. |

## User Preferences

| Tool/Command | Description |
|-------------|-------------|
| `/get_user_full_name` | Returns the user's full name. |
| `/set_user_full_name` | Sets the user's full name. |
| `/get_user_preferred_name` | Returns the user's preferred name. |
| `/set_user_preferred_name` | Set the user's preferred name. Should predominantly be used relatively early in first conversations, and relatively rarely afterward. |

## Utility Tools

| Tool/Command | Description |
|-------------|-------------|
| `/contemplate` | Contemplate the current context and return a response. |
| `/tail_elroy_logs` | Returns the last `lines` of the Elroy logs. |
| `/run_shell_command` | Run a shell command and return the output. |
| `/make_coding_edit` | Makes an edit to code using a delegated coding LLM. Requires complete context in the instruction. |

## Adding Custom Tools

Custom tools can be added by specifying directories or Python files via the `--custom-tools-path` parameter. Tools should be annotated with either:
- The `@tool` decorator from Elroy
- The langchain `@tool` decorator

Both decorators are supported and will work identically.
