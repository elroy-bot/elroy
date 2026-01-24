# Elroy Roadmap

This document tracks planned improvements and features for Elroy.

## Current Priorities

### Performance
- **Improve latency**: Response times are still poor and it's unclear from logs what is causing the slowdowns. Need to:
  - Add more detailed performance instrumentation
  - Profile critical paths (memory processing, context building, LLM calls)
  - Identify and optimize bottlenecks
  - Consider caching strategies where appropriate

### Developer Experience
- **Create Claude skills for memory tools**: Build a set of Claude Code skills that provide easy access to memory operations:
  - Skill for searching/querying memories
  - Skill for creating/updating memories
  - Skill for managing memory contexts
  - Skill for debugging memory-related issues

## Future Items

(Items will be added here as they are identified)

## Completed

(Items will be moved here when completed)
