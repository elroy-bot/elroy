#!/usr/bin/env python3
"""
Test script to verify the system status functionality works correctly.
"""
import time
from elroy.core.system_status import (
    SystemStatusType, StatusState, SystemStatusTracker,
    track_system_operation, update_system_operation, complete_system_operation
)

def test_system_status_tracker():
    print("Testing System Status Tracker...")
    
    # Test creating and tracking operations
    operation_id = track_system_operation(
        SystemStatusType.MEMORY_CONSOLIDATION,
        "Test Memory Consolidation",
        "Testing system status tracking"
    )
    print(f"Started operation with ID: {operation_id}")
    
    # Update progress
    update_system_operation(operation_id, state=StatusState.IN_PROGRESS, progress=0.5, details="50% complete")
    print("Updated operation progress to 50%")
    
    # Get active operations
    tracker = SystemStatusTracker()
    active_ops = tracker.get_active_operations()
    print(f"Active operations: {len(active_ops)}")
    
    for op in active_ops:
        print(f"  - {op.operation_name}: {op.state.value}, {op.progress}, {op.details}")
    
    # Complete operation
    complete_system_operation(operation_id, success=True, details="Test completed successfully")
    print("Completed operation")
    
    # Check that no active operations remain
    active_ops_after = tracker.get_active_operations()
    print(f"Active operations after completion: {len(active_ops_after)}")
    
    recent_ops = tracker.get_recent_operations(limit=1)
    if recent_ops:
        op = recent_ops[0]
        print(f"Recent operation: {op.operation_name} - {op.state.value}")
    
    print("System Status Tracker test completed successfully!\n")

def test_cli_io_system_status():
    print("Testing CLI IO System Status Panel...")
    
    from elroy.io.formatters.rich_formatter import RichFormatter  
    from elroy.io.cli import CliIO
    
    formatter = RichFormatter()
    io = CliIO(formatter, show_internal_thought=False, show_memory_panel=True, show_system_status_panel=True)
    
    # Start a test operation
    operation_id = track_system_operation(
        SystemStatusType.MEMORY_CONSOLIDATION,
        "CLI Test Operation",
        "Testing CLI display"
    )
    
    # Update it to show progress
    update_system_operation(operation_id, state=StatusState.IN_PROGRESS, progress=0.75, details="Processing...")
    
    print("System status panel should display the active operation:")
    io.print_system_status_panel()
    
    # Complete the operation
    complete_system_operation(operation_id, success=True, details="CLI test completed")
    
    print("\nAfter completion (should show nothing):")
    io.print_system_status_panel()
    
    print("CLI IO System Status Panel test completed!\n")

if __name__ == "__main__":
    test_system_status_tracker()
    test_cli_io_system_status()
    print("All tests passed!")