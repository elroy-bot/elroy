---
name: remind
description: Create a reminder in Elroy
disable-model-invocation: false
---

Create a time-based or context-based reminder in Elroy.

When the user invokes this skill with `/remind [TEXT]`, create a reminder by running:

```bash
elroy message "/create_reminder $ARGUMENTS"
```

If no arguments are provided, prompt the user for what they want to be reminded about.

Examples:
- `/remind "Review the new feature branch tomorrow at 2pm"`
- `/remind "Ask about test coverage when discussing testing strategy"`
