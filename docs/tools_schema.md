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
      "name": "create_contrib_repo",
      "description": "Create a new contrib plugin repository that Elroy can load tools and UI panels from.\n\nSets up a minimal git repository at the given path with stub files for both\ntool functions and a sidebar UI plugin. After creation, point elroy's\n``contrib_tools_path`` config option at this directory so Elroy loads everything\non startup.\n\nEach ``.py`` file (except those starting with ``_``) is scanned for:\n- Functions decorated with ``@tool`` \u2192 registered as assistant tools.\n- A module-level ``ELROY_PLUGIN`` variable (``ElroyPlugin`` instance) \u2192 adds a\n  tab to the TUI sidebar with the widget returned by ``widget_factory``.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Filesystem path where the contrib repo should be created (will be created if absent)."
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
      "description": "Creates a new memory for the assistant.\n\nExamples of good and bad memory titles are below. Note that in the BETTER examples, some titles have been split into two:\n\nBAD:\n- [User Name]'s project progress and personal goals: 'Personal goals' is too vague, and the title describes two different topics.\n\nBETTER:\n- [User Name]'s project on building a treehouse: More specific, and describes a single topic.\n- [User Name]'s goal to be more thoughtful in conversation: Describes a specific goal.\n\nBAD:\n- [User Name]'s weekend plans: 'Weekend plans' is too vague, and dates must be referenced in ISO 8601 format.\n\nBETTER:\n- [User Name]'s plan to attend a concert on 2022-02-11: More specific, and includes a specific date.\n\nBAD:\n- [User Name]'s preferred name and well being: Two different topics, and 'well being' is too vague.\n\nBETTER:\n- [User Name]'s preferred name: Describes a specific topic.\n- [User Name]'s feeling of rejuvenation after rest: Describes a specific topic.",
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
      "name": "edit_contrib_with_codex",
      "description": "Run a Codex edit session directly in the Elroy-home contrib plugin directory.\n\nUse this for assistant self-improvements that should be loaded through the plugin system instead\nof changing core Elroy source code. Elroy ensures the contrib directory exists as a git repo,\nruns Codex directly in that directory, records the session, and commits completed changes.",
      "parameters": {
        "type": "object",
        "properties": {
          "prompt": {
            "type": "string",
            "description": "Plugin/tool edit request for Codex."
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
      "name": "edit_feature_request",
      "description": "Edit an existing markdown feature request.\n\nUse this when a feature request already exists and needs a better title,\nrefined summary, updated rationale, or status change. Prefer this over creating\na duplicate request for the same product need.",
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
      "description": "Search through memories for the answer to a question.\n\nThis function searches summarized memories and goals. Each memory also contains source information.\n\nIf a retrieved memory is relevant but lacks detail to answer the question, use the get_source_content_for_memory tool. This can be useful in cases where broad information about a topic is provided, but more exact recollection is necessary.",
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
      "name": "fetch_page",
      "description": "Fetch a web page and return its readable text content.",
      "parameters": {
        "type": "object",
        "properties": {
          "url": {
            "type": "string",
            "description": "The URL to fetch."
          },
          "max_chars": {
            "type": "integer",
            "description": "Maximum number of characters to return (default 8000)."
          }
        },
        "required": [
          "url"
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
      "description": "Retrieves content of the source for a memory, by source type and name.\n\nFor a given memory, there can be multiple sources.",
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
      "name": "inspect_elroy_with_codex",
      "description": "Run a read-only Codex inspection session against the running Elroy source tree and optional logs.\n\nUse this when you want a separate Codex session to investigate bugs, inspect code paths, or review\nrecent logs without making edits.",
      "parameters": {
        "type": "object",
        "properties": {
          "prompt": {
            "type": "string",
            "description": "Inspection question or task for Codex."
          },
          "include_logs": {
            "type": "boolean",
            "description": "Whether to include the Elroy log path and recent log excerpt in the Codex prompt."
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
      "description": "List recently recorded Codex sessions and their latest summaries.",
      "parameters": {
        "type": "object",
        "properties": {
          "scope": {
            "type": "string",
            "description": "Optional filter. Use \"contrib\" for plugin-directory sessions or \"elroy\" for running-code inspection sessions."
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
      "description": "List the current markdown-backed feature requests.\n\nUse this before creating a new feature request when you suspect the request may\nalready exist. This helps avoid duplicate backlog entries by surfacing the\ncanonical titles, aliases, statuses, and brief summaries of existing requests."
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
      "description": "Create or merge a markdown feature request for future product work.\n\nUse this when the user asks for a net new capability, workflow, or product behavior\nthat Elroy does not currently support. First consider calling `list_feature_requests`\nto inspect the existing backlog. This tool will also try to merge into an existing\nfeature request when the request appears duplicative, to avoid backlog bloat.",
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
      "name": "set_user_full_name",
      "description": "Sets the user's full name.\n\nGuidance for usage:\n- Should predominantly be used relatively in the user journey. However, ensure to not be pushy in getting personal information early.\n- For existing users, this should be used relatively rarely.",
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
      "description": "Updates an existing memory with new information.\nIn general, when new information arises, new memories should be created rather than updating.\nReserve use of this tool for cases in which the information in a memory changes or becomes out of date.",
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
  },
  {
    "type": "function",
    "function": {
      "name": "web_search",
      "description": "Search the web using DuckDuckGo and return a list of results.",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "The search query string."
          },
          "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (default 5, max 20)."
          }
        },
        "required": [
          "query"
        ]
      }
    }
  }
]
```
