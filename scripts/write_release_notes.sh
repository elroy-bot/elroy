#!/bin/bash

# Dedicated script for writing release notes using claude CLI
# Extracted from release_patch.py to be a standalone utility

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
RELEASE_TYPE="patch"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --type|--release-type)
            RELEASE_TYPE="$2"
            if [[ ! "$RELEASE_TYPE" =~ ^(patch|minor|major)$ ]]; then
                echo "Error: Release type must be one of: patch, minor, major"
                exit 1
            fi
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--type RELEASE_TYPE]"
            echo "  --type       Type of release: patch, minor, or major (default: patch)"
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

# Change to repo root
cd "$REPO_ROOT"

# Get current version from __init__.py
CURRENT_VERSION=$(grep -E '^__version__' elroy/__init__.py | cut -d'"' -f2)
if [[ -z "$CURRENT_VERSION" ]]; then
    echo "Error: Could not find version in elroy/__init__.py"
    exit 1
fi

# Calculate next version based on release type
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

case "$RELEASE_TYPE" in
    "major")
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    "minor")
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    "patch")
        PATCH=$((PATCH + 1))
        ;;
esac

VERSION="${MAJOR}.${MINOR}.${PATCH}"

echo "Writing release notes for version $VERSION"

# Get last tag
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

# Get commits since last tag
if [[ -z "$LAST_TAG" ]]; then
    echo "No previous tags found, getting all commits"
    COMMITS=$(git log --name-only --pretty=format:"- %s%n%b%nFiles changed:")
else
    echo "Found commits since $LAST_TAG"
    COMMITS=$(git log "${LAST_TAG}..HEAD" --name-only --pretty=format:"- %s%n%b%nFiles changed:")
fi

# Current date
CURRENT_DATE=$(date +%Y-%m-%d)

# Create instruction for claude
INSTRUCTION="Find and update the changelog file to add version $VERSION. Here are the commits since the last release:

$COMMITS

Please:
1. Locate the changelog file (it might be CHANGELOG.md, CHANGELOG.rst, HISTORY.md, or similar)
2. Add a new entry at the top of the changelog for version $VERSION dated $CURRENT_DATE. Note that changelog header should be of format: ## [MAJOR.MINOR.PATCH] - YYYY-MM-DD. There should be an empty line before and after the version header.
3. Group the commits into appropriate sections (Added, Fixed, Improved, Infrastructure, etc.) based on their content. These should all be ### headers.
4. Clean up and standardize the commit messages to be more readable
5. Maintain the existing changelog format

Do NOT remove any existing entries.

Note that not all housekeeping updates need to be mentioned. Only those changes that a user would be interested in should be included.

Elements that should be more included and described:
- API endpoints
- Changes in memory behavior
- User facing improvements
- Major documentation updates

When describing these, think about why a user might care about the change, what they might expect as a result of the change.

Elements that should be excluded:
- Housekeeping items, minor documentation improvements
- Blog posts (these are released to docs ahead of release)
- pre-commit changes
"

# Create temporary instruction file
TEMP_INSTRUCTION_FILE="$REPO_ROOT/.temp_release_instruction.txt"
echo "$INSTRUCTION" > "$TEMP_INSTRUCTION_FILE"

# Function to cleanup temp file
cleanup() {
    rm -f "$TEMP_INSTRUCTION_FILE"
}
trap cleanup EXIT

# Use claude CLI to make the edit
echo "Running claude to update changelog..."
if claude --dangerously-skip-permissions "@$TEMP_INSTRUCTION_FILE"; then
    echo "Successfully updated changelog with claude CLI"
    echo "Release notes for version $VERSION have been written"
else
    echo "Error: Failed to update changelog with claude CLI"
    exit 1
fi
