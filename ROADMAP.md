# Elroy Roadmap

This document tracks planned improvements and features for Elroy.

## Current Priorities

### User Interface
- **System status in live panel** (Issue #475)
  - PRD: `prds/system-status-panel.md`
  - Expand the "Relevant Context" panel to show system execution info
  - Display memory consolidation status and background tasks
  - Show counters for messages/memories until next operation
  - Configurable toggle for showing system status

## Future Items

(Items will be added here as they are identified)

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
- **Create Claude Code skills for memory tools** (Completed: 2025-01)
  - Built complete set of 6 Claude Code skills in `claude-skills/` directory
  - `/remember` - Create long-term memories
  - `/recall` - Search through memories
  - `/list-memories` - List all active memories
  - `/remind` - Create reminders
  - `/list-reminders` - List active reminders
  - `/ingest` - Ingest documents into memory
  - Includes installation script with help documentation
