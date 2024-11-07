#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def get_latest_version_tag() -> str:
    """Get the most recent version tag."""
    result = subprocess.run(["git", "tag", "--list", "v*", "--sort=-v:refname"], capture_output=True, text=True)
    tags = result.stdout.strip().split("\n")
    return tags[0]


def get_next_version(current: str) -> str:
    """Calculate the next version based on bump2version config."""
    # For now just return the current version as placeholder
    # TODO: Actually parse .bumpversion.cfg and calculate next version
    return current.replace("v", "")


def get_changes_since_tag(tag: str) -> Tuple[List[str], List[str]]:
    """Get commit messages and diffs since the last tag."""
    # Get commit messages
    result = subprocess.run(["git", "log", f"{tag}..HEAD", "--pretty=format:%s"], capture_output=True, text=True)
    commits = result.stdout.strip().split("\n")

    # Get diff stats
    result = subprocess.run(["git", "diff", f"{tag}..HEAD", "--stat"], capture_output=True, text=True)
    diffs = result.stdout.strip().split("\n")

    return commits, diffs


def generate_notes(commits: List[str], diffs: List[str]) -> str:
    """Generate formatted release notes from commits and diffs."""
    # TODO: Implement smart release notes generation
    # For now just return a basic template with raw data
    return f"""
## What's Changed

### Commits
{chr(10).join(f"- {commit}" for commit in commits if commit)}

### Files Changed
{chr(10).join(f"- {diff}" for diff in diffs if diff)}
"""


def main():
    latest_tag = get_latest_version_tag()
    if not latest_tag:
        print("No version tags found")
        sys.exit(1)

    next_version = get_next_version(latest_tag)
    commits, diffs = get_changes_since_tag(latest_tag)
    notes = generate_notes(commits, diffs)

    release_notes = f"# Release v{next_version}\n{notes}"

    release_notes_path = Path(".release-notes")
    release_notes_path.write_text(release_notes)
    print(f"Release notes generated in {release_notes_path}")


if __name__ == "__main__":
    main()
