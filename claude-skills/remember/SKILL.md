---
name: remember
description: Create a long-term memory in Elroy
disable-model-invocation: false
---

Create a new long-term memory in Elroy.

When the user invokes this skill with `/remember [TEXT]`, create a memory by running:

```bash
elroy remember "$ARGUMENTS"
```

If no arguments are provided, prompt the user for what they want to remember.

Examples:
- `/remember "User prefers TypeScript over JavaScript"`
- `/remember "Project uses React with functional components"`
