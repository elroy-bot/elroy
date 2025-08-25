# Background Document Ingestion

## Overview

This feature allows CLI users to specify a directory for automatic document ingestion. Instead of manually running `elroy ingest` each time, Elroy will automatically monitor and ingest documents while the application is open.

## Core Requirements

### Configuration
- **Storage**: Background ingestion configuration is stored per-user in the database
- **Directory Setting**: Users can specify a watch directory via CLI tool/slash command
- **Patterns**: Support include/exclude glob patterns (same as manual ingestion)
- **Recursion**: Support recursive directory watching (enabled by default)

### Change Detection
- **File System Watching**: Use `watchdog` library for real-time file system events
- **Periodic Full Scans**: Full directory scan approximately once per day to catch any missed changes
- **Duplicate Handling**: Leverage existing MD5 hash-based duplicate detection
- **File Operations**: Detect new files, modified files, and moved files (deleted file handling via existing inactive marking)

### Technical Implementation
- **Scheduler Integration**: Use existing APScheduler system for periodic tasks
- **Multi-instance**: Handle multiple CLI instances gracefully (duplicate processing is acceptable due to existing deduplication)
- **Error Handling**: Log errors when ingestion fails, watch directory becomes inaccessible, etc.
- **Resource Management**: Handle thousands of files efficiently with infrequent changes

### User Experience
- **Silent Operation**: Run in background without interrupting user workflow
- **Status Tracking**: Track last scan time and status in database
- **Configuration**: Simple CLI tool/slash command to enable/disable and configure

## Frequency Configuration
- **Watchdog**: Real-time file system event monitoring while application is open
- **Full Scan**: Daily comprehensive directory scan (hard-coded interval)
- **Configuration Variable**: Hard-coded frequency setting for full scans

## Database Schema
New `BackgroundIngestionConfig` table with:
- `user_id`: Foreign key to user
- `watch_directory`: Path to monitor
- `is_active`: Enable/disable flag
- `recursive`: Recursive monitoring flag
- `include_patterns`: Comma-separated glob patterns
- `exclude_patterns`: Comma-separated glob patterns  
- `last_full_scan`: Timestamp of last full scan
- `last_scan_status`: Status tracking ('success', 'error', 'pending')
