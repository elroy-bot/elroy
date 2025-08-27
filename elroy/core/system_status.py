"""
System status tracking for live panel display.

This module provides infrastructure for tracking and displaying system execution
information in the live panel, including memory consolidation progress and other
background operations.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from ..core.logging import get_logger

logger = get_logger()


class SystemStatusType(Enum):
    """Types of system status operations that can be tracked."""
    MEMORY_CONSOLIDATION = "memory_consolidation"
    MEMORY_CREATION = "memory_creation"
    DOCUMENT_INGESTION = "document_ingestion"
    CONTEXT_REFRESH = "context_refresh"


class StatusState(Enum):
    """Status of a tracked operation."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SystemStatusEntry:
    """A single system status entry for tracking operations."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    status_type: SystemStatusType = SystemStatusType.MEMORY_CONSOLIDATION
    operation_name: str = ""
    state: StatusState = StatusState.STARTED
    progress: Optional[float] = None  # 0.0 to 1.0 for percentage
    details: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update(self, state: Optional[StatusState] = None, progress: Optional[float] = None, details: Optional[str] = None):
        """Update the status entry with new information."""
        if state is not None:
            self.state = state
        if progress is not None:
            self.progress = progress
        if details is not None:
            self.details = details
        self.updated_at = datetime.now()


class SystemStatusTracker:
    """Thread-safe tracker for system status information."""
    
    def __init__(self):
        self._entries: Dict[str, SystemStatusEntry] = {}
        self._lock = Lock()
        self._max_entries = 10  # Keep last 10 operations
    
    def start_operation(
        self, 
        status_type: SystemStatusType, 
        operation_name: str, 
        details: str = ""
    ) -> str:
        """Start tracking a new operation and return its ID."""
        entry = SystemStatusEntry(
            status_type=status_type,
            operation_name=operation_name,
            details=details,
            state=StatusState.STARTED
        )
        
        with self._lock:
            self._entries[entry.id] = entry
            self._cleanup_old_entries()
            logger.debug(f"Started tracking operation: {operation_name} ({entry.id})")
        
        return entry.id
    
    def update_operation(
        self, 
        operation_id: str, 
        state: Optional[StatusState] = None,
        progress: Optional[float] = None,
        details: Optional[str] = None
    ):
        """Update an existing operation."""
        with self._lock:
            if operation_id in self._entries:
                self._entries[operation_id].update(state=state, progress=progress, details=details)
                logger.debug(f"Updated operation {operation_id}: state={state}, progress={progress}")
            else:
                logger.warning(f"Attempted to update unknown operation ID: {operation_id}")
    
    def complete_operation(self, operation_id: str, success: bool = True, details: str = ""):
        """Mark an operation as completed or failed."""
        state = StatusState.COMPLETED if success else StatusState.FAILED
        self.update_operation(operation_id, state=state, progress=1.0 if success else None, details=details)
    
    def get_active_operations(self) -> List[SystemStatusEntry]:
        """Get all currently active (non-completed/failed) operations."""
        with self._lock:
            return [
                entry for entry in self._entries.values() 
                if entry.state in [StatusState.STARTED, StatusState.IN_PROGRESS]
            ]
    
    def get_recent_operations(self, limit: int = 5) -> List[SystemStatusEntry]:
        """Get recent operations, sorted by update time (most recent first)."""
        with self._lock:
            sorted_entries = sorted(
                self._entries.values(), 
                key=lambda x: x.updated_at, 
                reverse=True
            )
            return sorted_entries[:limit]
    
    def clear_completed_operations(self):
        """Remove completed and failed operations from tracking."""
        with self._lock:
            self._entries = {
                k: v for k, v in self._entries.items()
                if v.state in [StatusState.STARTED, StatusState.IN_PROGRESS]
            }
    
    def _cleanup_old_entries(self):
        """Remove old entries if we exceed the maximum limit."""
        if len(self._entries) <= self._max_entries:
            return
        
        # Keep the most recently updated entries
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda x: x[1].updated_at,
            reverse=True
        )
        
        entries_to_keep = dict(sorted_entries[:self._max_entries])
        self._entries = entries_to_keep


# Global system status tracker instance
_system_status_tracker = SystemStatusTracker()


def get_system_status_tracker() -> SystemStatusTracker:
    """Get the global system status tracker instance."""
    return _system_status_tracker


def track_system_operation(status_type: SystemStatusType, operation_name: str, details: str = "") -> str:
    """Convenience function to start tracking a system operation."""
    return get_system_status_tracker().start_operation(status_type, operation_name, details)


def update_system_operation(operation_id: str, **kwargs):
    """Convenience function to update a system operation."""
    get_system_status_tracker().update_operation(operation_id, **kwargs)


def complete_system_operation(operation_id: str, success: bool = True, details: str = ""):
    """Convenience function to complete a system operation."""
    get_system_status_tracker().complete_operation(operation_id, success, details)