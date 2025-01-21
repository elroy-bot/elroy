# Tools Schema Reference

Elroy tool calls are orchestrated via the `litellm` package. Tool schemas are listed below. Note that any argument `context` refers to the `ElroyContext` instance for the user. Where relevant, it is add to tool calls invisibly to the assistant.

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
      "description": "Adds goal with the given name to the current conversation context",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "The name of the goal to add"
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
      "description": "Adds memory with the given name to the current conversation context",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "The name of the memory to add"
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
      "description": "Contemplate the current context and return a response",
      "parameters": {
        "type": "object",
        "properties": {
          "contemplation_prompt": {
            "type": "string",
            "description": "The prompt to contemplate. Can be about the immediate conversation or a general topic. Default wil be a prompt about the current conversation."
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
      "description": "Creates a goal. The goal can be for the AI user, or for the assistant in relation to helping the user somehow.",
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
      "description": "Creates a new memory for the assistant.",
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
      "description": "Closes the goal.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "The name of the goal"
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
      "description": "Drops the goal with the given name. Does NOT delete or mark the goal completed.",
      "parameters": {
        "type": "object",
        "properties": {
          "goal_name": {
            "type": "string",
            "description": "Name of the goal"
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
      "description": "Drops the memory with the given name. Does NOT delete the memory.",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "Name of the memory"
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
      "description": "Returns the user's full name.",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_user_preferred_name",
      "description": "Returns the user's preferred name.",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "make_coding_edit",
      "description": "Instructs a delegated coding LLM to make an edit to code. As context is being passed transferred to the assistant, care must be taken to ensure the assistant has all necessary context.",
      "parameters": {
        "type": "object",
        "properties": {
          "working_dir": {
            "type": "string",
            "description": "Directory to work in"
          },
          "instruction": {
            "type": "string",
            "description": "The edit instruction. This should be exhaustive, and include any raw data needed to make the edit. It should also include any instructions based on memory or feedback as relevant."
          },
          "file_name": {
            "type": "string",
            "description": "File to edit"
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
            "description": "Updated status with a short account of how the goal was completed and what was learned."
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
            "description": "Name of the goal"
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
      "description": "Prints the memory with the given name",
      "parameters": {
        "type": "object",
        "properties": {
          "memory_name": {
            "type": "string",
            "description": "Name of the memory"
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
            "description": "The current name of the goal."
          },
          "new_goal_name": {
            "type": "string",
            "description": "The new name for the goal."
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
      "name": "set_user_full_name",
      "description": "Sets the user's full name.",
      "parameters": {
        "type": "object",
        "properties": {
          "full_name": {
            "type": "string",
            "description": "The full name of the user"
          },
          "override_existing": {
            "type": "boolean",
            "description": "Whether to override the an existing full name, if it is already set. Override existing should only be used if a known full name has been found to be incorrect."
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
            "description": "Whether to override the an existing preferred name, if it is already set. Override existing should only be used if a known preferred name has been found to be incorrect."
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
      "description": "Returns the last `lines` of the Elroy logs.",
      "parameters": {
        "type": "object",
        "properties": {
          "lines": {
            "type": "integer",
            "description": "Number of lines to return. Defaults to 10."
          }
        },
        "required": []
      }
    }
  }
]
```
