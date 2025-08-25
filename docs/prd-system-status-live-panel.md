# PRD: System Status in Live Panel

## Overview

This PRD outlines the expansion of Elroy's live panel feature to include system execution information alongside the existing memory context display. The current live panel only shows relevant memories during conversations. This enhancement will provide users with visibility into system operations, particularly memory consolidation processes and other background tasks.

## Current State

### Existing Live Panel Implementation
- **Location**: `elroy/cli/ui.py:print_memory_panel()`
- **Functionality**: Displays relevant memory context in a Rich panel titled "Relevant Context"
- **Configuration**: Controlled by `show_memory_panel` boolean option in user preferences
- **Integration**: Called during chat sessions via `elroy/cli/chat.py` at conversation start and after memory updates
- **Display**: Shows memory titles in a bordered panel using Rich console library

### Current Memory Consolidation System
- **Location**: `elroy/repository/memories/consolidation.py`
- **Features**: 
  - DBSCAN clustering of similar memories based on cosine similarity
  - Progress tracking with Rich progress bars
  - Detailed logging of consolidation operations
  - Configurable thresholds and cluster sizes

## Problem Statement

Users currently have limited visibility into Elroy's background operations, particularly:
1. Memory consolidation processes that affect their memory store
2. System execution status and performance metrics  
3. Long-running operations that may impact responsiveness
4. Background tasks that provide value but operate silently

This lack of transparency can lead to:
- User confusion about system behavior
- Uncertainty about when operations complete
- Missed opportunities to understand system performance
- Reduced trust in system reliability

## Goals

### Primary Goals
1. **System Transparency**: Provide users with real-time visibility into system operations
2. **Memory Operation Awareness**: Surface memory consolidation activities and outcomes
3. **Performance Insight**: Show system execution metrics and status information
4. **User Control**: Allow users to toggle system status display on/off
5. **Non-Intrusive Design**: Maintain current user experience while adding optional visibility

### Secondary Goals
1. **Extensibility**: Create a framework for adding new system status types
2. **Performance**: Ensure status display doesn't impact system performance
3. **Consistency**: Maintain visual consistency with existing live panel design

## Success Metrics

1. **User Engagement**: Track usage of system status panel toggle
2. **User Feedback**: Collect feedback on usefulness and intrusiveness
3. **Performance Impact**: Measure any performance overhead from status display
4. **Feature Adoption**: Monitor percentage of users who enable system status display

## User Stories

### Core User Stories
1. **As a user**, I want to see when memory consolidation is running so I understand system activity
2. **As a user**, I want to see completion status of memory consolidation so I know when it's finished
3. **As a user**, I want to optionally hide system status to maintain clean interface
4. **As a user**, I want to see system execution metrics to understand performance

### Advanced User Stories
1. **As a power user**, I want to see detailed consolidation statistics (clusters found, memories processed)
2. **As a developer**, I want to see system execution logs for debugging
3. **As a user**, I want to see background task queues and completion status

## Technical Requirements

### Core Requirements

#### 1. System Status Display Framework
- Extend existing live panel infrastructure to support multiple content types
- Create `print_system_status_panel()` function alongside existing `print_memory_panel()`
- Implement status data collection and formatting system
- Add configuration option `show_system_status_panel` (default: false)

#### 2. Memory Consolidation Status Integration
- Integrate with existing consolidation process in `consolidation.py`
- Track consolidation state: idle, running, completed, error
- Display cluster count, memory count, and progress information
- Show completion statistics (memories consolidated, time taken)

#### 3. Configuration Integration
- Add `show_system_status_panel` to `defaults.yml`
- Integrate with existing CLI options system
- Support runtime toggling via user preferences

#### 4. UI/UX Design
- Create separate "System Status" panel below existing "Relevant Context" panel
- Use consistent Rich panel styling with existing memory panel
- Implement collapsible/expandable sections for detailed information
- Ensure graceful handling when no system activity is present

### Technical Architecture

#### Status Data Model
```python
@dataclass
class SystemStatus:
    consolidation_status: ConsolidationStatus
    background_tasks: List[BackgroundTask]
    performance_metrics: Optional[PerformanceMetrics]
    
@dataclass  
class ConsolidationStatus:
    state: Literal["idle", "running", "completed", "error"]
    clusters_found: Optional[int]
    memories_processed: Optional[int]
    progress_percent: Optional[float]
    completion_time: Optional[datetime]
    error_message: Optional[str]
```

#### Integration Points
1. **CLI Integration**: Extend `elroy/cli/chat.py` to call system status display
2. **Memory Operations**: Hook into consolidation process to capture status
3. **Configuration**: Add system status options to user preference system
4. **Display Logic**: Implement conditional display based on user preferences and data availability

### Non-Functional Requirements

#### Performance
- System status collection must not impact core functionality performance
- Status display rendering should complete in <50ms
- Memory overhead for status tracking should be <10MB

#### Usability
- System status panel should not interfere with existing memory panel
- Panel should be visually distinct but consistent with existing design
- Information should be presented in user-friendly language

#### Reliability
- System status display failures must not impact core chat functionality
- Status information should gracefully handle missing or stale data
- Error states should be clearly communicated to users

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
1. Create system status data models and collection framework
2. Add configuration options for system status display
3. Implement basic status panel display infrastructure
4. Unit tests for status data collection and formatting

### Phase 2: Memory Consolidation Integration (Week 3-4)
1. Integrate status tracking with existing consolidation process
2. Implement consolidation status display in system panel
3. Add progress tracking and completion notifications
4. Integration tests for consolidation status display

### Phase 3: Enhancement and Polish (Week 5-6)  
1. Add background task tracking framework
2. Implement performance metrics collection
3. Add user preference controls and runtime toggling
4. Comprehensive testing and performance validation

### Phase 4: Future Enhancements (Future Releases)
1. Add more system operations to status display
2. Implement historical status logging and trends
3. Add system health monitoring and alerts
4. Create API endpoints for programmatic status access

## Risks and Mitigations

### Technical Risks
1. **Performance Impact**: Status collection could slow system → Implement lazy loading and caching
2. **UI Clutter**: Too much information could overwhelm users → Provide granular control and sensible defaults
3. **Race Conditions**: Status updates during operations → Implement thread-safe status tracking

### User Experience Risks  
1. **Information Overload**: System status might distract from core functionality → Make feature opt-in with minimal default display
2. **Inconsistent Updates**: Status might show stale information → Implement proper refresh mechanisms
3. **Visual Noise**: Additional panels might clutter interface → Use collapsible sections and consistent styling

## Future Considerations

### Extensibility
- Design status framework to support additional system operations
- Consider plugin architecture for third-party status providers
- Plan for historical status data and trend analysis

### Advanced Features
- Real-time status updates via WebSocket for web interface
- Mobile/web interface adaptations
- Integration with external monitoring systems
- Export capabilities for system status data

## Success Criteria

### Functional Success
- [ ] System status panel displays alongside memory panel when enabled
- [ ] Memory consolidation status accurately reflects current operations
- [ ] User can toggle system status display on/off
- [ ] Status display does not impact core functionality performance

### User Experience Success
- [ ] Users report increased understanding of system operations
- [ ] System status information is perceived as helpful, not intrusive
- [ ] Visual design maintains consistency with existing interface
- [ ] Feature adoption rate among active users exceeds 25%

---

**Document Status**: Draft v1.0  
**Created**: 2025-08-25  
**Author**: Claude Code  
**Stakeholders**: Elroy development team, user community