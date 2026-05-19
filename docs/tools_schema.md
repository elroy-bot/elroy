# Tools Schema Reference

Elroy tool calls are orchestrated via the `litellm` package. Tool schemas are listed below. Note that any argument `context` refers to the `ElroyConfig` instance for the user. Where relevant, it is added to tool calls invisibly to the assistant.

## Tool schemas
```json
[
  {
    "type": "function",
    "function": {
      "name": "add_agenda_checklist_item",
      "description": "Add a checklist sub-task to an agenda item.",
      "parameters": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "Agenda item stem or a unique substring match."
          },
          "text": {
            "type": "string",
            "description": "Checklist item text."
          },
          "due_date": {
            "type": "string",
            "description": "Optional ISO date string (YYYY-MM-DD)."
          }
        },
        "required": [
          "item_name",
          "text"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "add_agenda_item",
      "description": "Add a new agenda item for a given date (defaults to today).",
      "parameters": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "description": "The agenda item text."
          },
          "item_date": {
            "type": "string",
            "description": "ISO 8601 date string (YYYY-MM-DD). Defaults to today."
          }
        },
        "required": [
          "text"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "add_agenda_item_update",
      "description": "Append a timestamped progress note to an agenda item.",
      "parameters": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "Agenda item stem or a unique substring match."
          },
          "note": {
            "type": "string",
            "description": "Update text to append."
          }
        },
        "required": [
          "item_name",
          "note"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "add_memory_to_current_context",
      "description": "Adds memory with the given name to the current conversation context.",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "The name of the memory to add to context"
          }
        },
        "required": [
          "memory_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "complete_agenda_checklist_item",
      "description": "Mark a single checklist sub-task as completed.",
      "parameters": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "Agenda item stem or a unique substring match."
          },
          "checklist_item_id": {
            "type": "integer",
            "description": "Checklist entry id to complete."
          }
        },
        "required": [
          "item_name",
          "checklist_item_id"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "complete_agenda_item",
      "description": "Mark an agenda item as completed.",
      "parameters": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "The file stem (name without .md) of the agenda item, or a substring of it."
          }
        },
        "required": [
          "item_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "complete_due_item",
      "description": "Mark a due item as completed.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the due item to complete."
          },
          "closing_comment": {
            "type": "string",
            "description": "Optional note explaining why it was completed."
          }
        },
        "required": [
          "name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "create_due_item",
      "description": "Create a due item that can be triggered by time and/or context.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the due item. Must be unique."
          },
          "text": {
            "type": "string",
            "description": "The item text to display when triggered."
          },
          "trigger_time": {
            "type": "string",
            "description": "Trigger time in ``YYYY-MM-DD HH:MM`` format."
          },
          "trigger_context": {
            "type": "string",
            "description": "Description of the triggering context or situation."
          }
        },
        "required": [
          "name",
          "text"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "create_memory",
      "description": "Creates a new memory for the assistant.

Examples of good and bad memory titles are below. Note that in the BETTER examples, some titles have been split into two:

BAD:
- [User Name]'s project progress and personal goals: 'Personal goals' is too vague, and the title describes two different topics.

BETTER:
- [User Name]'s project on building a treehouse: More specific, and describes a single topic.
- [User Name]'s goal to be more thoughtful in conversation: Describes a specific goal.

BAD:
- [User Name]'s weekend plans: 'Weekend plans' is too vague, and dates must be referenced in ISO 8601 format.

BETTER:
- [User Name]'s plan to attend a concert on 2022-02-11: More specific, and includes a specific date.

BAD:
- [User Name]'s preferred name and well being: Two different topics, and 'well being' is too vague.

BETTER:
- [User Name]'s preferred name: Describes a specific topic.
- [User Name]'s feeling of rejuvenation after rest: Describes a specific topic.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "The name of the memory. Should be specific and discuss one topic."
          },
          "text": {
            "type": "string",
            "description": "The text of the memory."
          }
        },
        "required": [
          "name",
          "text"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "delete_agenda_item",
      "description": "Delete an agenda item permanently.",
      "parameters": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "The file stem (name without .md) of the agenda item, or a substring of it."
          }
        },
        "required": [
          "item_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "delete_due_item",
      "description": "Delete a due item permanently.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the due item to delete."
          },
          "closing_comment": {
            "type": "string",
            "description": "Optional note explaining why it was deleted."
          }
        },
        "required": [
          "name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "dispatch_codex_session",
      "description": "Run a Codex coding session against a repository inside the Elroy development workspace.

Use this when you want Codex to work in another repository or to perform a bounded coding task
in the current repo. Elroy will capture the Codex session id, summarize repository changes, and
remember the session for later resumption.",
      "parameters": {
        "type": "object",
        "properties": {
          "prompt": {
            "type": "string",
            "description": "Instructions to send to Codex."
          },
          "repo_path": {
            "type": "string",
            "description": "Repository path relative to the workspace containing this Elroy checkout, or an absolute path inside it."
          },
          "model": {
            "type": "string",
            "description": "Optional Codex model override."
          }
        },
        "required": [
          "prompt"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "drop_memory_from_current_context",
      "description": "Drops the memory with the given name from current context. Does NOT delete the memory.",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "Name of the memory to remove from context"
          }
        },
        "required": [
          "memory_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "edit_agenda_checklist_item",
      "description": "Update the text of an agenda checklist item.",
      "parameters": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "Agenda item stem or a unique substring match."
          },
          "checklist_item_id": {
            "type": "integer",
            "description": "Checklist entry id to edit."
          },
          "new_text": {
            "type": "string",
            "description": "Replacement text."
          }
        },
        "required": [
          "item_name",
          "checklist_item_id",
          "new_text"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "edit_feature_request",
      "description": "Edit an existing markdown feature request.

Use this when a feature request already exists and needs a better title,
refined summary, updated rationale, or status change. Prefer this over creating
a duplicate request for the same product need.",
      "parameters": {
        "type": "object",
        "properties": {
          "identifier": {
            "type": "string",
            "description": "Existing request id, title, alias, or filename stem to update."
          },
          "title": {
            "type": "string",
            "description": "Replacement canonical title."
          },
          "description": {
            "type": "string",
            "description": "Replacement summary of the request."
          },
          "rationale": {
            "type": "string",
            "description": "Replacement rationale for why it matters."
          },
          "status": {
            "type": "string",
            "description": "Replacement status value such as `open` or `closed`."
          }
        },
        "required": [
          "identifier"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "examine_memories",
      "description": "Search through memories for the answer to a question.

This function searches summarized memories and goals. Each memory also contains source information.

If a retrieved memory is relevant but lacks detail to answer the question, use the get_source_content_for_memory tool. This can be useful in cases where broad information about a topic is provided, but more exact recollection is necessary.",
      "parameters": {
        "type": "object",
        "properties": {
          "question": {
            "type": "string",
            "description": "Question to examine memories for. Should be a full sentence, with any relevant context that might make the query more specific."
          }
        },
        "required": [
          "question"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_current_date",
      "description": "Returns the current date and time."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_fast_recall",
      "description": "No-op tool used to acknowledge synthetic recall context."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_source_content_for_memory",
      "description": "Retrieves content of the source for a memory, by source type and name.

For a given memory, there can be multiple sources.",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "Type of the source"
          },
          "index": {
            "type": "integer",
            "description": "0-indexed index of which source to retrieve."
          }
        },
        "required": [
          "memory_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_user_full_name",
      "description": "Returns the user's full name."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_user_preferred_name",
      "description": "Returns the user's preferred name."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "list_agenda_items",
      "description": "List agenda items for a given date (defaults to today).",
      "parameters": {
        "type": "object",
        "properties": {
          "item_date": {
            "type": "string",
            "description": "ISO 8601 date string (YYYY-MM-DD). Defaults to today."
          }
        },
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "list_codex_sessions",
      "description": "List recently recorded Codex sessions and their latest change summaries.

Use this to discover resumable Codex sessions, inspect which repository each session targeted,
and review the latest summary before deciding whether to resume one. Session listings include
the isolated worktree and branch metadata so concurrent runs can be distinguished safely.",
      "parameters": {
        "type": "object",
        "properties": {
          "repo_path": {
            "type": "string",
            "description": "Optional repository path filter relative to the workspace containing this Elroy checkout."
          },
          "limit": {
            "type": "integer",
            "description": "Maximum number of sessions to return."
          }
        },
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "list_feature_requests",
      "description": "List the current markdown-backed feature requests.

Use this before creating a new feature request when you suspect the request may
already exist. This helps avoid duplicate backlog entries by surfacing the
canonical titles, aliases, statuses, and brief summaries of existing requests."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "ls",
      "description": "List a file or directory, with bounded recursive expansion for directories.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "File or directory path to inspect. Relative paths are resolved from the current working directory."
          },
          "recursive": {
            "type": "boolean",
            "description": "Whether to recursively expand directories."
          },
          "max_entries": {
            "type": "integer",
            "description": "Maximum number of entries to include in the listing."
          },
          "max_depth": {
            "type": "integer",
            "description": "Maximum directory depth to recurse into when recursive is true."
          }
        },
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "make_feature_request",
      "description": "Create or merge a markdown feature request for future product work.

Use this when the user asks for a net new capability, workflow, or product behavior
that Elroy does not currently support. First consider calling `list_feature_requests`
to inspect the existing backlog. This tool will also try to merge into an existing
feature request when the request appears duplicative, to avoid backlog bloat.",
      "parameters": {
        "type": "object",
        "properties": {
          "title": {
            "type": "string",
            "description": "Short title describing the requested feature."
          },
          "description": {
            "type": "string",
            "description": "What the new feature should do."
          },
          "rationale": {
            "type": "string",
            "description": "Optional explanation of why the feature matters."
          }
        },
        "required": [
          "title",
          "description"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "print_due_item",
      "description": "Print the details for a due item by name.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the due item to retrieve."
          }
        },
        "required": [
          "name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "print_memory",
      "description": "Retrieve and return a memory by its exact name.",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "Name of the memory to retrieve"
          }
        },
        "required": [
          "memory_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "pwd",
      "description": "Return the current working directory for filesystem tool calls."
    }
  },
  {
    "type": "function",
    "function": {
      "name": "read_file",
      "description": "Read a text file, optionally constrained to a line range.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "File path to read. Relative paths are resolved from the current working directory."
          },
          "start_line": {
            "type": "integer",
            "description": "One-based starting line number to read from."
          },
          "end_line": {
            "type": "integer",
            "description": "One-based ending line number to read through. Defaults to start_line + 199."
          }
        },
        "required": [
          "path"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "rename_due_item",
      "description": "Rename an existing due item.",
      "parameters": {
        "type": "object",
        "properties": {
          "old_name": {
            "type": "string",
            "description": "Current due item name."
          },
          "new_name": {
            "type": "string",
            "description": "Replacement due item name."
          }
        },
        "required": [
          "old_name",
          "new_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "restart_session",
      "description": "Restart the active Elroy session after the current response completes.",
      "parameters": {
        "type": "object",
        "properties": {
          "resume_message": {
            "type": "string",
            "description": "Hidden prompt injected after restart to trigger the assistant's first reply"
          }
        },
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "resume_codex_session",
      "description": "Resume a previously recorded Codex session with a follow-up prompt.

Use this after `dispatch_codex_session` when you want Codex to continue earlier work while
preserving its own session context. Elroy resumes the same Codex thread id and returns an
updated repository-change summary.",
      "parameters": {
        "type": "object",
        "properties": {
          "session_id": {
            "type": "string",
            "description": "Existing Codex thread/session id returned by Elroy."
          },
          "prompt": {
            "type": "string",
            "description": "Follow-up prompt to send to the existing Codex session."
          },
          "model": {
            "type": "string",
            "description": "Optional Codex model override."
          }
        },
        "required": [
          "session_id",
          "prompt"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "set_user_full_name",
      "description": "Sets the user's full name.

Guidance for usage:
- Should predominantly be used relatively in the user journey. However, ensure to not be pushy in getting personal information early.
- For existing users, this should be used relatively rarely.",
      "parameters": {
        "type": "object",
        "properties": {
          "full_name": {
            "type": "string",
            "description": "The full name of the user"
          },
          "override_existing": {
            "type": "boolean",
            "description": "Whether to override an existing full name, if it is already set. Override existing should only be used if a known full name has been found to be incorrect."
          }
        },
        "required": [
          "full_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "set_user_preferred_name",
      "description": "Set the user's preferred name. Should predominantly be used relatively early in first conversations, and relatively rarely afterward.",
      "parameters": {
        "type": "object",
        "properties": {
          "preferred_name": {
            "type": "string",
            "description": "The user's preferred name."
          },
          "override_existing": {
            "type": "boolean",
            "description": "Whether to override an existing preferred name, if it is already set. Override existing should only be used if a known preferred name has been found to be incorrect."
          }
        },
        "required": [
          "preferred_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "update_due_item_text",
      "description": "Update the text of an existing due item.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the due item to update."
          },
          "new_text": {
            "type": "string",
            "description": "Replacement text for the due item."
          }
        },
        "required": [
          "name",
          "new_text"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "update_outdated_or_incorrect_memory",
      "description": "Updates an existing memory with new information.
In general, when new information arises, new memories should be created rather than updating.
Reserve use of this tool for cases in which the information in a memory changes or becomes out of date.",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "Name of the existing memory to update"
          },
          "update_text": {
            "type": "string",
            "description": "The new information to append to the memory"
          }
        },
        "required": [
          "memory_name",
          "update_text"
        ]
      }
    }
  }
]
```
