# Tools Schema Reference

Elroy tool calls are orchestrated via the `litellm` package. Tool schemas are listed below. Note that any argument `context` refers to the `ElroyContext` instance for the user. Where relevant, it is added to tool calls invisibly to the assistant.

## Tool schemas
```json
[
  {
    "type": "function",
    "function": {
      "name": "add_goal_status_update",
      "description": "Captures either a progress update or note relevant to the goal.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "Name of the goal"
          },
          "status_update_or_note": {
            "type": "string",
            "description": "A brief status update or note about either progress or learnings relevant to the goal. Limit to 100 words."
          }
        },
        "required": [
          "goal_name",
          "status_update_or_note"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "add_goal_to_current_context",
      "description": "Adds goal with the given name to the current conversation context.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "The name of the goal to add to context"
          }
        },
        "required": [
          "goal_name"
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
      "name": "contemplate",
      "description": "Contemplate the current context and return a response.",
      "parameters": {
        "type": "object",
        "properties": {
          "contemplation_prompt": {
            "type": "string",
            "description": "Custom prompt to guide the contemplation.
If not provided, will contemplate the current conversation context."
          }
        },
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "create_goal",
      "description": "Creates a goal. The goal can be for the AI user, or for the assistant in relation to helping the user somehow.
Goals should be *specific* and *measurable*. They should be based on the user's needs and desires, and should
be achievable within a reasonable timeframe.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "Name of the goal"
          },
          "strategy": {
            "type": "string",
            "description": "The strategy to achieve the goal. Your strategy should detail either how you (the personal assistant) will achieve the goal, or how you will assist your user to solve the goal. Limit to 100 words."
          },
          "description": {
            "type": "string",
            "description": "A brief description of the goal. Limit to 100 words."
          },
          "end_condition": {
            "type": "string",
            "description": "The condition that indicate to you (the personal assistant) that the goal is achieved or terminated. It is critical that this end condition be OBSERVABLE BY YOU (the assistant). For example, the end_condition may be that you've asked the user about the goal status."
          },
          "time_to_completion": {
            "type": "string",
            "description": "The amount of time from now until the goal can be completed. Should be in the form of NUMBER TIME_UNIT, where TIME_UNIT is one of HOURS, DAYS, WEEKS, MONTHS. For example, \"1 DAYS\" would be a goal that should be completed within 1 day."
          },
          "priority": {
            "type": "integer",
            "description": "The priority of the goal, from 0-4. Priority 0 is the highest priority, and 4 is the lowest."
          }
        },
        "required": [
          "goal_name"
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
      "name": "delete_goal_permanently",
      "description": "Permanently deletes a goal.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "The name of the goal to delete"
          }
        },
        "required": [
          "goal_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "drop_goal_from_current_context",
      "description": "Drops the goal with the given name from current context. Does NOT delete or mark the goal completed.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "Name of the goal to remove from context"
          }
        },
        "required": [
          "goal_name"
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
      "name": "run_shell_command",
      "description": "Run a shell command and return the output.",
      "parameters": {
        "type": "object",
        "properties": {
          "command": {
            "type": "string",
            "description": "The shell command to run."
          }
        },
        "required": [
          "command"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "make_coding_edit",
      "description": "Makes an edit to code using a delegated coding LLM. Requires complete context in the instruction.",
      "parameters": {
        "type": "object",
        "properties": {
          "working_dir": {
            "type": "string",
            "description": "Directory containing the file to edit"
          },
          "instruction": {
            "type": "string",
            "description": "Complete edit instructions including any necessary context or raw data"
          },
          "file_name": {
            "type": "string",
            "description": "Name of the file to edit"
          }
        },
        "required": [
          "working_dir",
          "instruction",
          "file_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "mark_goal_completed",
      "description": "Marks a goal as completed, with closing comments.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "The name of the goal"
          },
          "closing_comments": {
            "type": "string",
            "description": "Updated status with a short account of how the goal was completed and what was learned"
          }
        },
        "required": [
          "goal_name"
        ]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "print_goal",
      "description": "Prints the goal with the given name. This does NOT create a goal, it only prints the existing goal with the given name if it has been created already.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "Name of the goal to retrieve"
          }
        },
        "required": [
          "goal_name"
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
      "name": "rename_goal",
      "description": "Renames an existing active goal.",
      "parameters": {
        "type": "object",
        "properties": {
          "old_goal_name": {
            "type": "string",
            "description": "The current name of the goal"
          },
          "new_goal_name": {
            "type": "string",
            "description": "The new name for the goal"
          }
        },
        "required": [
          "old_goal_name",
          "new_goal_name"
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
      "name": "tail_elroy_logs",
      "description": "Returns the last `lines` of the Elroy logs.
Useful for troubleshooting in cases where errors occur (especially with tool calling).",
      "parameters": {
        "type": "object",
        "properties": {
          "lines": {
            "type": "integer",
            "description": "Number of lines to return from the end of the log file. Defaults to 10."
          }
        },
        "required": []
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
