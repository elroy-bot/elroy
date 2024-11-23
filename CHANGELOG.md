# Changelog

## [0.0.47] - 2024-11-22

### Added
- Added configurable LLM response caching: `enable_caching`, defaulting to true.
- New system commands for troubleshooting:
    - `/tail_elroy_logs`: View log Elroy logs from within the chat UI
    - `/print_elroy_config`: View Elroy config from within the chat UI
    - `/create_bug_report`: Open a pre-filled bug report in the browser (available to the user only, not the assistant)


## [0.0.46] - 2024-11-20

### Added
- Added expanded configuration options for better customization

### Fixed
- Improved CHANGELOG.md handling with better path resolution and error management

## [0.0.45] - 2024-11-19

### Added
- Added automated Discord announcements for new releases

### Infrastructure
- Improved CI workflow to prevent duplicate runs on branch pushes

## [0.0.44] - 2024-11-19

### Improved
- Enhanced release process with streaming subprocess output and progress logging
- Updated documentation for clarity and completeness

### Legal
- Changed project license to Apache 2.0

## [0.0.43] - 2024-11-18

Minor fixes

## [0.0.42] - 2024-11-17

### Added
- Updated README to document all startup options and system commands for better user guidance.
- Added more verbose error output for tool calls to improve debugging and error tracking.

### Fixed
- Improved autocomplete functionality by filtering goals and memories for more relevant options.
- Simplified demo recording script for easier demonstration creation.

### Improved
- Enhanced error handling for goal-related functions to better surface available goals.
- Added override parameters to name setting functions to discourage redundant calls.
- Provided additional context in login messages for a more informative user experience.

### Infrastructure
- Added a `wait-for-pypi` job to verify package availability before Docker publishing, ensuring smoother deployment processes.

## [0.0.41] - 2024-11-14

Updates to package publishing

## [0.0.40] - 2024-11-14
### Added
- Initial release of Elroy, a CLI AI personal assistant with long-term memory and goal tracking capabilities.
- Features include long-term memory, goal tracking, and a memory panel for relevant memories during conversations.
- Supports installation via Docker, pip, or from source.
- Includes commands for system management, goal management, memory management, user preferences, and conversation handling.
