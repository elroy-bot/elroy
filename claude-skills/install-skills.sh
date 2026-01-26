#!/usr/bin/env bash
# Install Elroy skills for Claude Code
# This script installs Elroy memory management skills into Claude Code's skills directory

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine Claude Code skills directory
# Claude Code typically uses ~/.claude/skills or can be specified via CLAUDE_SKILLS_DIR
SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

show_help() {
    cat << EOF
Install Elroy Skills for Claude Code

USAGE:
    ./install-skills.sh [OPTIONS]

DESCRIPTION:
    Installs Elroy memory management skills into Claude Code's skills directory.
    These skills allow you to use Elroy's memory tools directly from Claude Code
    using slash commands like /remember and /recall.

OPTIONS:
    --skills-dir DIR  Install to custom skills directory (default: ~/.claude/skills)
    --uninstall       Remove installed Elroy skills
    --help, -h        Show this help message

INSTALLED SKILLS:
    /remember        - Create a long-term memory
    /recall          - Search through memories
    /list-memories   - List all memories
    /remind          - Create a reminder
    /list-reminders  - List active reminders
    /ingest          - Ingest documents into memory
    /introspect      - Ask questions about Elroy's implementation
    /make-improvement - Implement a feature or improvement and submit a PR

REQUIREMENTS:
    - Elroy must be installed and available in PATH
    - Claude Code installed

EXAMPLES:
    # Install to default location
    ./install-skills.sh

    # Install to custom directory
    ./install-skills.sh --skills-dir ~/.custom/skills

    # Uninstall
    ./install-skills.sh --uninstall
EOF
}

error() {
    echo -e "${RED}Error: $1${NC}" >&2
    exit 1
}

info() {
    echo -e "${GREEN}$1${NC}"
}

warn() {
    echo -e "${YELLOW}$1${NC}"
}

# Parse arguments
UNINSTALL=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skills-dir)
            SKILLS_DIR="$2"
            shift 2
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            error "Unknown option: $1\nUse --help for usage information"
            ;;
    esac
done

# List of skills to install
SKILLS=(
    "remember"
    "recall"
    "list-memories"
    "remind"
    "list-reminders"
    "ingest"
    "introspect"
    "make-improvement"
)

# Uninstall if requested
if [ "$UNINSTALL" = true ]; then
    info "Uninstalling Elroy skills from: $SKILLS_DIR"

    for skill in "${SKILLS[@]}"; do
        skill_path="$SKILLS_DIR/$skill"
        if [ -e "$skill_path" ]; then
            rm -rf "$skill_path"
            info "  Removed: $skill"
        else
            warn "  Not found: $skill"
        fi
    done

    info "\nElroy skills uninstalled successfully!"
    exit 0
fi

# Check if elroy is installed
if ! command -v elroy &> /dev/null; then
    error "Elroy is not installed or not in PATH.\nPlease install Elroy first: pip install elroy-ai"
fi

# Create skills directory if it doesn't exist
if [ ! -d "$SKILLS_DIR" ]; then
    info "Creating skills directory: $SKILLS_DIR"
    mkdir -p "$SKILLS_DIR"
fi

# Install skills
info "Installing Elroy skills to: $SKILLS_DIR\n"

for skill in "${SKILLS[@]}"; do
    source_path="$SCRIPT_DIR/$skill"
    dest_path="$SKILLS_DIR/$skill"

    if [ ! -e "$source_path" ]; then
        warn "  Skipping $skill (source not found)"
        continue
    fi

    # Remove existing skill if present
    if [ -e "$dest_path" ]; then
        rm -rf "$dest_path"
    fi

    # Copy the skill directory
    if [ -d "$source_path" ]; then
        cp -r "$source_path" "$dest_path"
    else
        # Fallback for old-style single file skills
        cp "$source_path" "$dest_path"
        chmod +x "$dest_path"
    fi

    info "  Installed: $skill"
done

info "\nElroy skills installed successfully!"
info "\nAvailable commands:"
for skill in "${SKILLS[@]}"; do
    echo "  /$skill"
done

info "\nTip: Restart your Claude Code session to see the new skills"
info "Then try using: /$skill in your conversation"
