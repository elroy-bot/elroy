# Tools Schema Reference

Elroy tool calls are orchestrated via the `litellm` package. Tool schemas are listed below. Note that any argument `context` refers to the `ElroyContext` instance for the user. Where relevant, it is added to tool calls invisibly to the assistant.

## Tool schemas
```json
[
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
      "name": "complete_reminder",
      "description": "Marks a reminder as completed.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "The name of the reminder to mark complete"
          },
          "closing_comment": {
            "type": "string",
            "description": "Optional comment on why the reminder was completed"
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
      "name": "create_reminder",
      "description": "Creates a reminder that can be triggered by time and/or context.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the reminder (must be unique)"
          },
          "text": {
            "type": "string",
            "description": "The reminder message to display when triggered"
          },
          "trigger_time": {
            "type": "string",
            "description": "When the reminder should trigger in format \"YYYY-MM-DD HH:MM\" (e.g., \"2024-12-25 09:00\"). If provided, creates a timed reminder."
          },
          "reminder_context": {
            "type": "string",
            "description": "Description of the context/situation when this reminder should be triggered (e.g., \"when user mentions work stress\", \"when user asks about exercise\"). If provided, creates a contextual reminder."
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
      "name": "delete_reminder",
      "description": "Permanently deletes a reminder (timed, contextual, or hybrid).",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "The name of the reminder to delete"
          },
          "closing_comment": {
            "type": "string",
            "description": "Optional comment on why the reminder was deleted"
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
      "name": "get_document_excerpt",
      "description": "Gets text of document excerpt by address and chunk index (0-indexed). Use get_source_doc_metadata to get available chunk indices.",
      "parameters": {
        "type": "object",
        "properties": {
          "address": {
            "type": "string",
            "description": "The address/path of the document"
          },
          "chunk_index": {
            "type": "integer",
            "description": "The 0-based index of the chunk to retrieve"
          }
        },
        "required": [
          "address",
          "chunk_index"
        ]
      }
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
      "name": "get_source_doc_metadata",
      "description": "Gets metadata about a source document including extraction time and available chunks.",
      "parameters": {
        "type": "object",
        "properties": {
          "address": {
            "type": "string",
            "description": "The address/path of the document"
          }
        },
        "required": [
          "address"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_source_documents",
      "description": "Gets the list of ingested source documents."
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
      "name": "print_reminder",
      "description": "Prints the reminder with the given name.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the reminder to retrieve"
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
      "name": "rename_reminder",
      "description": "Renames an existing reminder.",
      "parameters": {
        "type": "object",
        "properties": {
          "old_name": {
            "type": "string",
            "description": "The current name of the reminder"
          },
          "new_name": {
            "type": "string",
            "description": "The new name for the reminder"
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
      "name": "search_documents",
      "description": "Search through document excerpts using semantic similarity.",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "The search query string"
          }
        },
        "required": [
          "query"
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
  },
  {
    "type": "function",
    "function": {
      "name": "update_reminder_text",
      "description": "Updates the text of an existing reminder.",
      "parameters": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the reminder to update"
          },
          "new_text": {
            "type": "string",
            "description": "The new reminder text"
          }
        },
        "required": [
          "name",
          "new_text"
        ]
      }
    }
  }
]
```
