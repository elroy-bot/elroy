# Elroy Roadmap

This document tracks planned improvements and features for Elroy.

## Current Priorities

(No active priorities at this time)

## Future Items

### Self-Improvement Framework (Partial)
Enable Elroy to actively participate in its own development:
- **Usage analytics tracking**: Capture interaction outcomes (success/failure/retry patterns)
- **Analysis tools**: Tools to query usage patterns, review roadmap
- **Improvement proposals**: System for agent to suggest and prioritize improvements based on observed data
- **Development session mode**: Special mode where agent works on implementing improvements

**Completed foundation**:
- ✅ `/introspect` skill - Agent can understand its own implementation
- ✅ `/make-improvement` skill - Agent can implement changes and submit PRs

## Completed

### Performance
- **Improve latency tracking and logging** (Completed: 2025-01)
  - Added comprehensive latency tracking module (`elroy/core/latency.py`)
  - Implemented `LatencyTracker` class for tracking operations across requests
  - Added context manager for measuring operations with automatic logging
  - Built summary functionality showing breakdown by operation type
  - Added decorators for tracking function latency
  - Configured automatic logging for slow operations (>100ms)

### Developer Experience
- **Create Claude Code skills for memory and development tools** (Completed: 2025-01)
  - Built complete set of 8 Claude Code skills in `claude-skills/` directory
  - Memory management:
    - `/remember` - Create long-term memories
    - `/recall` - Search through memories
    - `/list-memories` - List all active memories
    - `/remind` - Create reminders
    - `/list-reminders` - List active reminders
    - `/ingest` - Ingest documents into memory
  - Self-improvement capabilities:
    - `/introspect` - Ask questions about Elroy's implementation (enables self-awareness)
    - `/make-improvement` - Implement features/improvements and submit PRs (enables self-modification)
  - Includes installation script and comprehensive documentation
